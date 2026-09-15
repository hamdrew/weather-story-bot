# Story Updates and NWS Validation — Shaping Notes

## Scope

Three changes to how the bot handles what NWS sends, prompted by the first days of the MVP soak:

- **Updates repost.** When a story's image or description changes, post it again with "🔄 Updated:" and delete the old message, so every update sends a notification.
- **Ambiguous NWS content is rejected.** If active stories in one listing share an image ID, a title and start time, or identical image bytes, none of them are posted. The bot logs an error and an alarm emails me right away. Stories past their `endTime` are ignored.
- **The archive and records follow our story identity.** S3 keys and DynamoDB records are keyed by title + start time instead of image UUID, and a one-off script migrates the existing data.

## Decisions

- **A story is identified by its title + `startTime`.** They stayed fixed across every revision seen so far. The image UUID and `updateTime` don't: NWS re-issued stories under new UUIDs, and with `updateTime` set to the Unix epoch.
  - A title or start time change is treated as a new story. That risks a duplicate post. We'll handle it if it happens.
- **A change means a new image or description.** `endTime` is ignored because it doesn't change the Telegram message. `updateTime` and `altText` are ignored too.
- **`updateTime` isn't used at all.** Every active story's image is downloaded on every run, which the image-collision check needs anyway. Change detection compares the content fingerprint with the story's stored record, so an epoch `updateTime` can't hide or fake a change.
- **Updates post new, then delete the old message.** Order: post → record in DynamoDB → delete. A crash or a failed delete leaves an extra message, never a missing one.
  - Telegram only lets bots delete messages sent less than 48 hours ago (checked in the Bot API docs, 2026-09-15). Older ones stay. A failed delete is a WARNING, not a run failure.
  - A message that's already gone ("message to delete not found") counts as deleted.
- **No timestamp in the caption.** The "🔄 Updated:" prefix is enough.
- **Expired stories get no action.** A story with `endTime` at or before now isn't downloaded, validated, posted or deleted.
- **Ambiguity rule:** an active story is rejected if it shares its image ID, its title + `startTime`, or its image SHA-256 with any other active story in the same listing. Every story in the collision is rejected, not just the later one.
  - The check covers one listing at a time. The same content showing up under a new UUID after the old one is gone is an ordinary unchanged story, not an error.
  - A story whose image fails to download is counted as failed and left out of the image check. If it shares an image with another story, that other story can still post. Accepted as very unlikely.
- **Ambiguity is its own alarm, not a run failure.** The `errors` alarm needs two failing 15-minute periods, and NWS usually fixes these faster than that. Rejections log one `Ambiguous stories from NWS` ERROR line per office per run, and the `nws-ambiguous` alarm fires on the first one. It doesn't raise `ProcessingError`, so `errors` still means the bot itself is broken.
- **Archive layout: `stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title-slug}-{story_key[:8]}/{fingerprint[:16]}.{png,json}`**, with the date and time from the start in UTC.
  - The folder is one story. The slug and time are for reading the bucket; the `story_key` prefix makes it unique, since different titles can slug the same.
  - The file is one revision, named by its content fingerprint. The same content always lands on the same key (retries and re-issues are harmless) and different content never overwrites. The old `{image_id}/{updateTime}` layout could overwrite a real revision.
  - Revisions aren't time-ordered by name. S3's LastModified and the `story#` record's `archive_prefix` show which is current.
- **Existing data is migrated, not abandoned** (`scripts/migrate_story_keys.py`, one-off, dry run by default).
  - Old archive pairs are copied to the new layout. Identical re-issues collapse into one pair, keeping the earliest copy's JSON, as the Lambda would.
  - Each story gets a `story#` record from its latest post: message ID, `posted_at`, fingerprint and new archive prefix. Unchanged live stories are then skipped after deploy instead of reposted, and an update deletes the right message. Existing `story#` records are never overwritten.
  - `--delete-old` removes the old pairs and the per-image and `content#` items. Run it only once the new Lambda is working, since a rollback needs them. S3 versioning and PITR keep them 35 days.
  - Cutover: pause the EventBridge schedule outside Terraform, `--apply`, then `make deploy`, so no run of either version lands in between. Terraform doesn't set the schedule's `state`, so its default (`ENABLED`) makes the deploy turn the schedule back on.
  - Dry run against production on 2026-09-15: 13 pairs → 11 copies (both "High Swim Risk" re-issues collapse), 10 `story#` records, and "Thunderstorms early this Morning" gets one folder with two revisions.

## Context

- **Visuals:** None
- **References:** The uncommitted edit-in-place work from 2026-09-15 (never deployed), MVP spec Tasks 12 and 15, the 2026-09-14 and 2026-09-15 duplicate incidents
- **Product alignment:** Adds a principle to `agent-os/product/mission.md`: ambiguous NWS content is never posted, is ignored, and I'm notified. Roadmap Phase 1.1.

## Standards Applied

- backend/untrusted-nws-data (new) — the rule this spec introduces
- backend/client-errors — `TelegramClient.delete_message` raises only `TelegramError`; the handler catches it to keep the new post
- backend/injected-clients — the handler's clock is passed in by the caller so tests control expiry, and the migration takes its S3 and DynamoDB clients so moto tests drive it
- backend/retries — delete follows `_call`: a 429 retries once, transport errors don't
- backend/secrets-in-errors — the delete path goes through `_call`, which keeps the token out of errors and logs
