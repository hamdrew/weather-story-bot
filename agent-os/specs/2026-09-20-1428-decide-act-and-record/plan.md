# Phase 1.2: Decide, Act, and Record

Spec folder: `agent-os/specs/2026-09-20-1428-decide-act-and-record/`

## Context

The MVP has been live since 2026-09-13 and Phase 1.1 hardened it against what NWS actually
sends. Three problems are left, and they share a root cause.

**The code interleaves deciding with acting.** Expiry filtering, ambiguity rejection and the
new/updated/unchanged call are tangled up with archiving, sending and recording inside
`handler.run`. Nothing can ask "what would you do?" without doing it.

**So the dry run lies.** `__main__.py` lists stories and prints a caption for every one of them,
including stories the Lambda would drop as expired or reject as ambiguous. It also still posts
to Telegram with `--send-telegram`, which is the one local write path left in the project.

**And almost nothing is recorded.** DynamoDB keeps one record per story, overwritten on every
revision. The S3 archive keeps every revision but never says *when* anything was posted. Logs
expire after 30 days. So "which story was revised the most", "which were pulled early", "how
often did NWS send garbage" and "when was the bot blind" are unanswerable today, and the
2027 Year in Review needs a year of answers that cannot be backfilled — the NWS API lists only
*active* stories. Every day without recording is a day permanently lost.

The outcome: a pure planner both the Lambda and the CLI call, a CLI that cannot write anything,
a single concurrent run, a frozen identity hash, and three append-only writes that start saving
history — on a new table carrying Phase 2.2's key design, so Phase 2.2 needs no migration.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Spec scope | One spec for all of Phase 1.2, delivered in **four deploy stages** |
| Table | **New table** with Phase 2.2's full key design, migrated now while it holds 42 items |
| TTL | **None.** DynamoDB records stay permanent; the new table gets no `ttl` block |
| Day boundary | UTC day, 96 fixed UTC slots — no per-office timezone until Phase 2.2 |
| CLI | Kept, rewritten as a thin read-only printer over the shared planner; `--dry-run` stays required |
| Concurrency | **A per-office DynamoDB lease**, not reserved concurrency (reasoning below) |

### Evidence: the concurrency question

The roadmap asked for this to be settled with evidence, not memory. The evidence says reserved
concurrency *would* work today — and that we should skip it anyway.

**Why skip it.** Reserved concurrency cannot express the requirement. `= 1` gives exclusion, but
*global* exclusion: once Phase 2.2 makes each office its own invocation, MKX blocks GRB. `= 4`
allows four simultaneous runs without any guarantee they are four *different* offices, so two MKX
runs can both get a slot and double-post. There is no value that means "one run per office". It is
binary — global exclusion or none — so the moment the unit to protect is the office rather than
the function, the mechanism stops fitting. Building it now means shipping a guard, writing a
standard around it, and deleting both in Phase 2.2. **The lease moves up from Phase 2.2 instead.**

**Why we are not exposed while building it.** The Lambda timeout is 300s and the cadence is 900s,
so a slow run cannot overlap the next one. The only path to a double post is Scheduler's
at-least-once duplicate delivery, which is rare — that is why this has been survivable since launch.

**The evidence itself**, which still matters because it explains what happens to a *throttled*
invocation in any future design:

- EventBridge Scheduler **invokes Lambda asynchronously**
  ([docs](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html)), so once
  Lambda returns 202 the event is in Lambda's async queue and the schedule's
  `maximum_retry_attempts = 0` no longer governs it.
- In that queue, `MaximumRetryAttempts` covers **function errors only**. Throttles (429) and
  system errors are returned to the queue and retried with exponential backoff **for up to 6
  hours** ([docs](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)).
- So a throttled run is **delayed, not dropped**. `missed-runs` counts `Invocations` over an
  hour with four runs per hour and stays honest either way.
- Account check (`aws lambda get-account-settings`, us-east-2): 1000 concurrent, 1000
  unreserved — so reserved concurrency was available to us; we are declining it, not blocked.
- **Trap, recorded for the future:** reserved concurrency of **0** is an off switch, not "no
  limit", and it disables async retries entirely.

### Evidence: the table is small now and never will be again

Measured 2026-09-20: the table holds **42 items, 21,736 bytes**, all `story#` items in MKX —
about 6 new story items a day since the bot went live on 2026-09-13. At that rate it reaches a
few thousand items by Phase 2.2, on top of three months of ledger events that this phase starts
writing and that never expire. The migration is cheaper today than it will ever be again.

## Working agreement

**Stop after every task.** Each task ends with `make lint` and `make test` passing, then it goes
back for review and a commit before the next one starts.

**Four deploy gates.** Tasks are grouped into stages that each end in a deployable, revertible
state. Nothing from a later stage deploys early. **Each standard changes in the task that makes it
true**, not in a sweep at the end.

---

# Stage 1 — Behaviour-neutral refactor

Nothing about what reaches the channel changes. No infra change, no data change. This stage is
isolated precisely because it contains the riskiest change in the spec: a wrong hash encoding
reposts every active story, and the handler refactor has to preserve three alarm log contracts.

## Task 1: Save spec documentation

Create `agent-os/specs/2026-09-20-1428-decide-act-and-record/` with `plan.md` (this plan),
`shape.md`, `standards.md` and `references.md`. No `visuals/` — none provided.

Also in this task:

- `agent-os/product/roadmap.md`: the DynamoDB key redesign and the per-office lease both move
  **from Phase 2.2 into Phase 1.2**, leaving Phase 2.2's remaining DynamoDB work additive.
- `agent-os/standards/global/principles.md` (new) + its `index.yml` entry: local tools are
  read-only; decide purely, then act; sources of truth vs derived data; the office is the unit
  of isolation.

## Task 2: Pin the story identity hash (`state.py`)

Lands first — Stage 3 migrates data keyed by these hashes, so they must be frozen before anything
moves.

- Freeze the encoding explicitly in `_sha256_json`: `json.dumps(..., sort_keys=True,
  separators=(", ", ": "), ensure_ascii=True)` — `json.dumps`' own default separators, spelled
  out rather than left implicit, so every currently-stored digest still matches. **Do not**
  switch to compact separators (`(",", ":")`); that changes every digest and reposts every
  active story, with a comment saying why it can never change.
- Test pinning **known literal digests** for both `story_key` and `content_fingerprint` against
  a fixed story and image.
- Amend `backend/story-identity.md`: the frozen encoding, the pin test, and that global identity
  is `(office_id, story_key)`.

## Task 3: The pure planner (`planner.py`, new)

Two steps, because expired stories must never be downloaded:

1. `select_active(stories, now) -> tuple[list[Story], list[Decision]]` — splits the listing into
   stories to download and `expired` decisions.
2. `decide(office_id, downloaded, records, now) -> list[Decision]` — ambiguity rejection and the
   `post` / `update` / `unchanged` call over `(Story, image)` pairs plus the stored records.

`Decision` is a frozen dataclass: the story, an outcome (`post`, `update`, `unchanged`,
`expired`, `rejected`), `reasons` for rejections, the current `PostedRecord` when there is
one, and (on `update` only, added in Task 7b) `changes`. Move `_AMBIGUITY_CHECKS` and `_reject_ambiguous` here unchanged in behaviour.

**The planner is pure: no logging, no I/O, no clock of its own.** It returns data; the handler
logs. Tests are table-driven with no moto — listing + records + `now` in, decisions out. Amend
`testing/handler-tests.md`.

## Task 4: Handler becomes a thin apply step (`handler.py`)

`run` per office: list → `select_active` → download → `decide` → apply each decision in
`backend/side-effect-order` order. Counts stay exactly as `backend/run-outcomes` fixes them:
`posted`, `updated`, `skipped`, `rejected`, `failed`.

**Three log messages survive word for word**, or they move in the same commit as
`infra/monitoring.tf`:

| Message | Emitted by | Depended on by |
|---|---|---|
| `Ambiguous stories from NWS` | handler, from the planner's rejections | `nws-ambiguous` alarm metric filter |
| `Telegram message sent` | `telegram.py` (unchanged) | `StoriesPosted` → **both** `quiet` and `repost-loop` |
| `Story posted` | handler | `repost-loop` runbook text |

`Run complete` is named in the `quiet` alarm runbook and also stays.

## Task 5: Office and request id on every log line

A `logging.Filter` (or contextvar) set once per invocation adds `office` and `aws_request_id`,
rather than every caller passing them. `lambda_handler` takes `aws_request_id` from `context`.
Remove the now-redundant per-call `extra={"office": ...}` where the filter supplies it. Amend
`backend/structured-logging.md`.

## Task 6: CLI rewrite (`__main__.py`)

Local-only, zero deploy risk, and it depends only on the planner — so it belongs here rather than
after the migration.

- `--send-telegram` gone, with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` handling, the token exit-2
  path and the Telegram client.
- `--dry-run` **stays required** — the deliberate speed bump; a future write mode is a new flag.
- `--office` validated with `config.py`'s regex, so `--office ../x` exits 2.
- Calls `select_active` + `decide` and prints each story's decision beside its caption. Without
  DynamoDB it cannot tell new from updated, so it prints `new-or-updated (state not read)`.
- Exit codes: 0 success or no active stories, 1 NWS list or download failed, 2 usage.
- Tests assert with an empty respx router that **no Telegram host is ever called**. Move
  `TELEGRAM_*` clearing into the autouse fixture per `testing/offline-tests`.
- Rewrite `backend/cli.md`; amend `testing/offline-tests.md`; update the `--dry-run` line in
  **CLAUDE.md** in the same commit.

### 🚦 Deploy gate 1

`make build && make deploy`. No schedule pause needed.

- **Watch:** one clean run posting nothing new; `Run complete` summaries show only `skipped`;
  no unexpected Telegram sends; all four alarms quiet.
- **Prove the contracts:** confirm `Telegram message sent` and `Story posted` still appear on the
  next real post, and that `StoriesPosted` still increments.
- **Rollback:** redeploy the previous zip. No data has changed.

---

# Stage 2 — Create the table

## Task 7: New table with Phase 2.2's key design (`infra/`)

New `aws_dynamodb_table` resource (`${local.name}-state`) **beside** the existing one. The bot
keeps reading and writing the old table — `STATE_TABLE` does not move yet. The old table is never
touched; it is the rollback, and `infra/data-retention` forbids replacing it.

| Item | PK | SK |
|---|---|---|
| Current story | `OFFICE#<id>` | `STORY#<start_utc_iso>#<story_key>` |
| Ledger event | `OFFICE#<id>` | `EVENT#<start_utc_iso>#<story_key>#<at_utc_iso>` |
| Daily run record | `OFFICE#<id>` | `DAY#<YYYY-MM-DD>` (UTC) |
| Office lease | `OFFICE#<id>` | `LEASE` |

- Generic `PK`/`SK` attribute names, `schema_version` on every item.
- **No `ttl` block.** Records are permanent by decision; say so in the resource comment, because
  the Phase 2.2 sketch proposes one and someone will otherwise "restore" it. The lease expires by
  conditional write against an ordinary `expires_at` attribute, not by TTL.
- `deletion_protection_enabled = true` and 35-day PITR, same as today.
- **No secondary indexes, and no index attributes written in advance** (decided 2026-09-23,
  replacing the earlier `GSI1PK`/`GSI1SK` plan). Analytics reads a native export to S3, not the
  table. A GSI can be added later and backfills from ordinary attributes such as `event_at`; an
  LSI cannot, so the table never gets one.
- **No IAM change in this task.** `infra/iam` adds each permission in the same change as the code
  that calls it (decided 2026-09-23): `GetItem`/`PutItem` land in Task 9, `UpdateItem` in Task 10,
  `DeleteItem` in Task 11.
- Amend `backend/dynamodb-schema.md` to describe the new keys as current.

### 🚦 Deploy gate 2

`make plan` must show the new table **added** and **zero replacements**, then `make deploy`.

- Purely additive. The bot's behaviour is unchanged because `STATE_TABLE` still points at the old
  table.
- **Watch:** one clean run, unchanged behaviour. Confirm the new table exists and is empty.
- **Rollback:** the table is unused; nothing to undo.

## Task 7b: Name what an update changed (added 2026-09-24)

Came out of reviewing the 2026-09-24 17:10 CDT "Updated" post: the logs said *that* the story
changed, not *what*. That post changed everything (a new image UUID, new image bytes and a
trimmed description), but nothing in the logs said so.

- `state.py`: the record also stores the fingerprint's two inputs, `image_sha256` and
  `description_sha256`. `content_fingerprint` still makes every decision; these only explain one.
  `record_posted` takes `image_sha256` as an optional keyword so `scripts/migrate_story_keys.py`
  still runs.
- `planner.py`: `Decision.changes` on `update`: `image_id`, `image`, `description`, or `content`
  when the record predates the stored parts. Pure and table-tested.
- `handler.py`: `Story posted` gains `fingerprint` on every post and, on updates, `changes`,
  `previous_image_id`, `previous_fingerprint` and `previous_archive_prefix`. The message text is
  unchanged, so no metric filter or runbook moves.
- Amend `backend/story-identity.md`. Tasks 8 and 9 carry the two attributes to the new table.

### 🚦 Deploy gate 2b

`make build && make deploy`. No infra change; `PutItem` on the old table is already granted.

- **Watch:** the next update logs `changes: ["content"]` (plus `image_id` if the UUID moved),
  since every live record predates the parts. The one after that names `image` or `description`.
- **Rollback:** redeploy the previous zip. The extra attributes are ignored by the old code.

---

# Stage 3 — Migrate and flip

The only stage with manual work and a schedule pause.

## Task 8: Migration script (`scripts/migrate_table_keys.py`)

Follows `scripts/migrate_story_keys.py` exactly: dated module docstring with before/after and a
runbook, dry run by default, `--apply` to write, every step idempotent, `MigrationError` before
any write if the data looks wrong, `--delete-old` as a separate later step, moto-backed tests.

Copies each `story#<story_key>` item from the old table to `STORY#<start>#<story_key>` on the new
one, preserving `telegram_message_id`, `posted_at`, `fingerprint` and `archive_prefix` so live
stories are skipped after the flip rather than reposted. Also copy `image_sha256` and
`description_sha256` when present (added 2026-09-24 so `Story posted` can name what an update
changed); an item without them still migrates. Adds `schema_version`. Expect 42 items,
growing ~6/day — assert the count looks sane before writing.

## Task 9: Flip `STATE_TABLE` (`infra/lambda.tf`)

Not one line: `state.py` hard-codes the MVP keys (`office_id` / `image_id = story#<story_key>`),
so pointing `STATE_TABLE` at a `PK`/`SK` table alone fails every `GetItem` and silences the bot.

- `state.py`: read and write `PK = OFFICE#<id>`, `SK = STORY#<start_utc_iso>#<story_key>`, with
  `schema_version`, matching what Task 8 writes. Moto tests against the new key schema.
  Keep writing and reading `image_sha256` and `description_sha256`.
- `find_story` takes the `Story` (the sort key needs its start time) and builds the key the same
  way `record_posted` does, from `story.office_id`. Before, the lookup used the configured office
  and the write used NWS's `officeId`, so a mismatch would have reposted every run. Both now also
  write `office_id` and `story_key` as plain attributes, matching what Task 8 migrates.
- `scripts/migrate_story_keys.py` writes its MVP-shape items itself instead of through
  `PostedStore`, so it stays runnable. `image_sha256` becomes required on `record_posted`.
- `infra/lambda.tf`: point `STATE_TABLE` at the new table.
- `infra/iam.tf`: grant `GetItem`/`PutItem` on the new table's ARN and drop the old table's grants.

### 🚦 Deploy gate 3 — the pause

1. `aws login`, migration **dry run** against production; read the diff.
2. Pause the EventBridge schedule outside Terraform.
3. Migration `--apply`.
4. `make build && make deploy` (flips `STATE_TABLE`).
5. Re-enable the schedule — Terraform does not set `state`, so its default `ENABLED` does this
   on apply.

- **Watch:** the first run must post **nothing**. A repost here means the migration missed items.
- **Rollback:** point `STATE_TABLE` back at the old table and deploy. The old table is untouched
  and still current, so this is a clean revert. Do not run `--delete-old` until the soak is clean.

---

# Stage 4 — Recording and the lease

Needs Stage 3, because the lease is in the safety chain and would fail every run against the old
table's keys.

## Task 10: History writes (`history.py`, new)

Three best-effort, append-only writes. **None are in the safety chain** — each failure logs a
WARNING and never blocks a post.

- `record_event(...)` — one immutable item per action: `posted`, `updated`, `rejected`,
  `deleted`, `delete_failed`, with office, story, `event_at`, fingerprint, message id and reasons.
  Events record only the revision they are about: no `previous_*` fields and no `changes`
  (decided 2026-09-24). What an update changed is derived at analysis time from consecutive
  events for the same story, not stored in the ledger.
- `touch_last_seen(...)` — `UpdateItem` on the current-story item, **only when `last_seen_at` is
  at least an hour stale**, so a story pulled before its `endTime` is visible.
- `record_run(...)` — one `UpdateItem` with `ADD` per run: `runs`, `nws_failures`,
  `stories_seen`, `rejected`, plus a 96-bit UTC slot bitmap with the bit set when that run's NWS
  list failed. Outages read back as runs of consecutive set bits.

A separate module from `state.py` on purpose: `state.py` is the safety chain, `history.py` is not.

`infra/iam.tf`: add `UpdateItem` on the new table's ARN.

## Task 11: The office lease (`state.py`)

Step 0 of `backend/side-effect-order`, and deliberately **in** the safety chain — which is why it
lives in `state.py`.

- `take_lease(office_id, now, ttl)` — conditional `PutItem` on
  `attribute_not_exists(PK) OR expires_at < :now`, writing `expires_at = now + 300s + margin`.
- `release_lease(office_id)` — `DeleteItem` in a `finally`, so a clean run frees it immediately.
  A crashed run blocks at most the next 15-minute run.
- **Losing the lease counts as `skipped`** and logs INFO `Office run already in progress`. Not a
  failure; must not trip the `errors` alarm. Adds a case to `counts()` in `tests/test_handler.py`.
- **A DynamoDB error taking the lease counts as `failed`**, not "proceed anyway".
- **Tests:** two interleaved runs produce one send; an expired lease is taken; a clean run
  releases; a crashed run's lease expires; a throttled `PutItem` (monkeypatched per
  `testing/offline-tests`) counts as `failed`.
- Amend `backend/run-outcomes.md` for the two new cases.
- `infra/iam.tf`: add `DeleteItem` on the new table's ARN. Amend `infra/iam.md`, whose "No
  `Delete*`" rule then needs to allow exact item-level `DeleteItem` for the lease.

## Task 12: Wire the lease and history into the apply step

Take the lease first (step 0), then the existing side effects in order, with the three history
writes around them and never between them. Amend `backend/side-effect-order.md` with step 0 and
with where the best-effort writes sit — outside the chain — noting that Phase 2.2 deliberately
reverses the latter by making the ledger write atomic with the record.

## Task 13: Cost and index sweep

Refresh `agent-os/standards/index.yml` descriptions for every file touched across all four stages,
and update `infra/infracost-usage.yml` for the extra DynamoDB writes. Run `make cost` and record
the delta in the spec folder.

### 🚦 Deploy gate 4

`make build && make deploy`. No pause needed.

- **Watch:** a ledger event, a `last_seen_at` and a `DAY#` record appear for MKX within an hour.
  Two runs never post the same story. `Office run already in progress` appears only if a genuine
  overlap happens.
- **Rollback:** redeploy the previous zip. Ledger items already written are harmless — they are
  append-only and nothing reads them yet.

---

## Verification

- `make lint` and `make test` clean at every task. New coverage: pinned-hash digests, table-driven
  planner tests with no moto, the three log-contract assertions, best-effort write failures
  logging WARNING without failing a run, two interleaved runs producing one send, a CLI test
  proving no Telegram call, moto-backed migration tests.
- `make plan` at gates 2 and 3 shows **zero replacements** on the existing table and bucket
  (`infra/data-retention`).
- `make cost` before and after; the delta should be pennies (on-demand writes only).
- `uv run weather-story-bot --dry-run --office MKX` against live NWS prints a decision beside
  every caption, including expired and rejected ones.
- Leave the old table in place until Stage 4's soak is clean, then run `--delete-old` deliberately.
