# Story Updates and NWS Validation

## Context

The MVP (spec `2026-09-13-0026-weather-story-mvp`) has been live since 2026-09-13. The soak turned up three NWS behaviors the design didn't expect:

- **2026-09-14:** "High Swim Risk" was re-issued under a new image UUID with identical bytes and metadata, and posted twice. MVP Task 12 added a content fingerprint.
- **2026-09-15:** "High Swim Risk" (`02e256d6…`, message 10 → `39e84a59…`, message 14) was re-issued again under a new UUID with `updateTime` at `1970-01-01T00:00:00+00:00` and a blank `altText`. The PNG (1,729,112 bytes), title, description, start and end were identical. The fingerprint included `updateTime`, so it posted twice again.
- **2026-09-15:** "Thunderstorms early this Morning" (`6cd6cee1…`, message 12, epoch → `e7769e6c…`, message 15, `07:08:51Z`) was really revised (new image, `endTime` 08:00 → 08:30, gusts 30 → 35 mph) under a new UUID, and posted as a second, unrelated message.

A fix that edited messages in place was written the same day but never deployed or committed. This spec replaces it. An edit doesn't send a notification, so updates now repost and delete the old message, and NWS data is treated as untrusted.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Story identity | Title + `startTime` (UTC). A title or start change is a new story |
| Change detection | SHA-256 of the image SHA-256 + description, compared with the story's stored record. `endTime`, `updateTime`, `altText` and the UUID are ignored |
| Update | Post with "🔄 Updated:" → record → delete the old message. A failed delete is a WARNING |
| Expired | `endTime <= now`: no action |
| Ambiguous | Active stories sharing an image ID, title + start, or image SHA-256 are all rejected: ERROR log, `rejected` count, `nws-ambiguous` alarm. No `ProcessingError` |
| Storage | One `story#<story_key>` item per story. Per-image items and `content#` items are no longer written or read |
| Archive | `stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title-slug}-{story_key[:8]}/{fingerprint[:16]}.{png,json}` (start in UTC): a folder per story, a pair per revision |
| Migration | `scripts/migrate_story_keys.py` copies old archive pairs to the new layout and backfills `story#` records from each story's latest post. Run with `--apply` just before deploy |

## Task 1: Save spec documentation

This folder, plus:

- `agent-os/product/mission.md`: a Principles section
- `agent-os/product/roadmap.md`: Phase 1.1
- `agent-os/standards/backend/untrusted-nws-data.md` and its `index.yml` entry
- MVP spec: remove the undeployed Task 15 and point Task 12 and the shaping notes here

## Task 2: State (`state.py`)

- `content_fingerprint(story, image)`: SHA-256 of canonical JSON `{"image_sha256", "description"}`.
- `image_sha256(image)`: hex digest, shared by the fingerprint and the handler's collision check.
- `story_key(story)`: unchanged (title + `startTime` in UTC).
- `Status`: `NEW`, `UPDATED`, `UNCHANGED`. Remove `classify` and `SEEN`/`DUPLICATE`.
- `PostedStore`:
  - `find_story(office_id, key) -> PostedRecord | None`
  - `record_posted(story, message_id, archive_prefix, fingerprint)`: one PutItem, sort key `story#<key>`, with `posted_image_id`, `title`, `start_time`, `end_time`, `update_time`, `posted_at`, `telegram_message_id`, `archive_prefix`, `fingerprint`.
  - Remove `get_update_time` and `record_duplicate`.
- **Tests:** fingerprint ignores UUID, order, `updateTime`, `altText`, title, start and `endTime`, and changes with image or description. Key tests unchanged. `record_posted` then `find_story`, a later revision overwrites, and an office is its own partition.

## Task 3: Telegram client (`telegram.py`)

- Remove `edit_photo` and `_NotModifiedError`.
- `delete_message(chat_id, message_id)`: `deleteMessage` through `_call`, and logs `Telegram message deleted`. "message to delete not found" is suppressed (already gone). Anything else raises `TelegramError`.
- `_call` returns the raw `result`, since `deleteMessage` returns `true`. The send path checks it's an object.
- **Tests:** request fields and log; not-found is success; "message can't be deleted" and other errors raise `TelegramError` without the token; a 429 retries once.

## Task 4: Handler (`handler.py`)

`run(offices, services, *, now=None)`. `now` defaults to `datetime.now(UTC)`, and tests pass it. Per office:

1. List stories. On failure: `failed`, next office.
2. Stories with `end_time <= now` count as `skipped`.
3. Download each active story's image. On failure: log, `failed`, and leave it out.
4. Reject collisions among the downloaded stories by image ID, `story_key` or `image_sha256`. One ERROR line `Ambiguous stories from NWS` with `office` and `stories: [{image_id, title, reasons}]`. Each rejected story counts once as `rejected`.
5. For each remaining story (errors → `failed`):
   - no record → archive, post, record, `Story posted` (status `new`)
   - same fingerprint → `skipped`
   - different fingerprint → archive, post with "🔄 Updated:", record the new message, `Story posted` (status `updated`), then `delete_message` on the old ID. A `TelegramError` there logs `Telegram delete failed, old message kept` at WARNING.

Summary counts: `posted`, `updated`, `skipped`, `rejected`, `failed`. `lambda_handler` still raises only on `failed`.

Remove `has_sibling`, `_revise_post` and the duplicate path.

- **Tests:** new stories post; a second run skips without Telegram calls; a changed image or description (same or new UUID, including an epoch `updateTime`) posts "Updated" and deletes the old message; `updateTime`, `endTime`, `altText` or UUID-only changes skip; a later revision deletes the previous repost; a failed delete keeps the new post and warns; a new title or start posts new; expired stories aren't downloaded or posted; each ambiguity rejects all involved stories and logs one ERROR line while the others still post; rejection doesn't raise from `lambda_handler`; failed downloads count as failed; a DynamoDB failure after a post doesn't delete the old message; the existing metric-filter and office-isolation tests.

## Task 5: Monitoring (`infra/monitoring.tf`)

- Revert the uncommitted `stories_posted` comment. Updates are new sends again, so `quiet` and `repost-loop` count them.
- `aws_cloudwatch_log_metric_filter.nws_ambiguous`: `{ $.message = "Ambiguous stories from NWS" }` → `WeatherStoryBot/AmbiguousStories`.
- `aws_cloudwatch_metric_alarm.nws_ambiguous`: Sum ≥ 1 over one 900 s period, `notBreaching`, alarm + OK to SNS. The description says what to check.

## Task 6: Archive layout (`archive.py`)

- `archive_prefix(story, fingerprint)`: `stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{slug}-{story_key[:8]}/{fingerprint[:16]}`. The slug is ASCII, lowercase, hyphenated, at most 48 characters, and `story` if empty.
- `StoryArchive.save(story, image, fingerprint)`. The handler passes the fingerprint it already computed.
- **Tests:** the layout and UTC start; the image UUID, `updateTime`, `endTime` and `altText` don't change the prefix; titles with the same slug get different folders; the slug is ASCII and bounded; the same revision rewrites the same pair and new content adds a pair in the same folder.

## Task 7: Migration script (`scripts/migrate_story_keys.py`)

Reads everything and plans every change before writing. Prints the plan; writes only with `--apply`.

1. Every old pair (`…/{image_id}/{YYYYMMDDTHHMMSSZ}.json` + `.png`) → `Story.from_api` + image → fingerprint → new prefix. Copy the earliest pair (by LastModified) per new prefix, skipping prefixes that already exist.
2. Posts are per-image items with `posted_at` (not `content#`, `story#` or `duplicate_of` markers). Group them by `story_key`, and write a `story#` record from the latest post with `record_posted(..., posted_at=)`, unless the story already has one.
3. `--delete-old`: delete the old pairs and all non-`story#` items.

A JSON with no PNG, or a post whose archive pair is missing, raises `MigrationError` before anything is written.

- **Tests (moto):** a dry run changes nothing and reports counts; `--apply` copies each revision to its story folder and collapses the re-issue onto the earliest copy; each story is recorded from its latest post with a fingerprint the handler will match; a rerun changes nothing and keeps an existing record; `--delete-old` leaves only the new layout and records, and without `--apply` does nothing; missing PNG and missing archive pair fail before writing; collapse picks the earliest copy regardless of key order.

## Task 8: Docs

- README: "What it does" flow, the S3, Telegram and DynamoDB lines in the diagram, the archive bullet and the recovery note, the alert table row for `nws-ambiguous`, the metric filter note, the `Run complete` summary example, and the alarm count in the cost section.
- MVP references: the "`updateTime` isn't reliable" note points here.

## Verification

- `make lint`, `make test`
- `make plan`: adds one metric filter and one alarm, and updates the Lambda code. Nothing else.
- `uv run python scripts/migrate_story_keys.py`: review the dry run against production.
- Cutover (by the user, with the MFA admin profile):
  1. Pause the schedule. `update-schedule` replaces the whole schedule, so send its current definition back with only the state changed:
     ```sh
     aws scheduler get-schedule --region us-east-2 --name weather-story-bot \
       --query '{Name: Name, Description: Description, ScheduleExpression: ScheduleExpression, FlexibleTimeWindow: FlexibleTimeWindow, Target: Target}' \
       > "${TMPDIR:-/tmp}/weather-story-bot-schedule.json"
     aws scheduler update-schedule --region us-east-2 --cli-input-json "file://${TMPDIR:-/tmp}/weather-story-bot-schedule.json" --state DISABLED
     aws scheduler get-schedule --region us-east-2 --name weather-story-bot --query State   # "DISABLED"
     ```
  2. If a run was in progress, wait for its `Run complete` log line.
  3. `scripts/migrate_story_keys.py --apply`.
  4. `make build`, then `make deploy`. The plan also shows the schedule's `state` going `DISABLED` → `ENABLED`: that's the unpause.
  5. If the deploy fails, re-enable the schedule the same way with `--state ENABLED`. The old Lambda ignores `story#` items and the new archive keys, so it keeps working.
- After deploy: the first run skips the live stories (no reposts) and writes new archive objects only for changed stories. Force `weather-story-bot-nws-ambiguous` with `set-alarm-state` to check the email path.
- Once the new version has run cleanly: `scripts/migrate_story_keys.py --apply --delete-old`.

## Out of scope

- Linking a story whose title or start time changed
- Deleting messages older than 48 hours (Telegram doesn't allow it)
- Applying the ambiguity checks to the local `--dry-run` CLI
