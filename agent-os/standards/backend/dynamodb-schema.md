# DynamoDB Schema

## Keys (`aws_dynamodb_table.state`)

One table, generic key names, every item under its office's partition:

| Item | `PK` | `SK` |
|---|---|---|
| Current story | `OFFICE#<id>` | `STORY#<start_utc_iso>#<story_key>` |
| Ledger event | `OFFICE#<id>` | `EVENT#<start_utc_iso>#<story_key>#<at_utc_iso>` |
| Run record | `OFFICE#<id>` | `RUN#<at_utc_iso>` |
| Office lease | `OFFICE#<id>` | `LEASE` |

- Key attributes are named `PK` and `SK`, never after what they hold, so new item types need no schema change
- Sort-key values sort usefully: UTC ISO timestamps, so a `begins_with`/`BETWEEN` Query answers date ranges within one office
- Every item carries `schema_version` (a number). Bump it when an item type's attributes change shape
- Build keys and `schema_version` with `state.py`'s `office_pk`, `story_sk` and `SCHEMA_VERSION`, never by hand, so migration scripts write exactly what the Lambda reads
- Current-story items also carry `office_id` and `story_key` as ordinary attributes, so an S3 export reads them without parsing keys
- Mark each item type with its uppercase sort-key prefix. Any read that isn't an exact key (a Query on `PK`) filters on the prefix
- Global identity is `(office_id, story_key)` (`backend/story-identity`). `story_key` alone never appears as a key without its office
- Keys serve the bot's own access patterns only. Analytics never queries the table: it reads a native export to S3 (`ExportTableToPointInTime`, which uses the PITR already on) and runs downstream (`global/principles`)
- No secondary indexes today. Never add an LSI: it can only be created with the table and caps each partition at 10 GB for good. A GSI can be added any time and backfills every item that already has its key attributes, so no attribute is written "for a future index"
- Timestamp attributes carry item-specific names (`event_at` on events, `posted_at`, `last_seen_at`, `expires_at`), never a generic `at`, so an index on one of them stays sparse
- **No TTL.** Records are permanent and the ledger is a source of truth (`global/principles`). The lease expires through a conditional write on an ordinary `expires_at` attribute, not TTL
- Use the low-level client with typed attributes (`{"S": ...}`) and `ConsistentRead=True` on dedupe lookups
- Timestamps written by new code use `state.utc_timestamp` (fixed-width UTC, microseconds), so they compare and sort as strings. `STORY#` start times keep their existing format; they're in live keys

## History items (`history.py`)

Best-effort and append-only, outside the safety chain: a failed write logs WARNING `"History write failed"` and never blocks a post. `state.py` is the safety chain; `history.py` is not.

- **`EVENT#`**: one immutable item per action (`posted`, `updated`, `rejected`, `deleted`, `delete_failed`), written with `attribute_not_exists(PK)` so a key collision fails rather than overwrites. The event time is part of the key, so read the clock per event. It holds only the revision it's about: no `previous_*` fields or `changes`. What an update changed is derived from consecutive events at analysis time. The archive prefix isn't stored either; `archive_prefix(story, fingerprint)` rebuilds it
- **`last_seen_at`** on the `STORY#` item: rewritten only when the value read with the record is an hour stale, decided before any request, since a failed conditional write still bills. The condition `attribute_exists(PK)` keeps it from creating an item. `record_posted` replaces the item and clears it, so each repost starts unseen. A story pulled early shows `last_seen_at` well before `end_time`
- **`RUN#`**: one immutable item per office per run, written like events: `run_at`, `nws_failed`, `stories_seen`, the run's outcome counts (`backend/run-outcomes`) and `aws_request_id`. Raw runs, never daily totals: outages, days and per-office baselines are derived at analysis time, so the record doesn't depend on the schedule's cadence. A duplicate run is its own item

## Office lease (`state.OfficeLease`)

In the safety chain (step 0 of `backend/side-effect-order`), so it lives in `state.py`. One `LEASE` item per office: `office_id`, `holder` (a random token per take), `taken_at`, `expires_at`.

- **Take**: conditional `PutItem` on `attribute_not_exists(PK) OR expires_at < :now`. A condition failure means another run holds it; any other error raises
- **Release**: `DeleteItem` in a `finally`, conditional on `holder`, so a run whose lease expired can't delete the next run's
- `expires_at` is `taken_at + LEASE_DURATION` (360s: the 300s Lambda timeout plus a margin), shorter than the 900s schedule, so a crashed run's lease is gone before the next run. Raising the Lambda timeout means raising `LEASE_DURATION` with it

The MVP table `aws_dynamodb_table.posted` (`office_id` / `image_id = story#<story_key>`) was
copied here by `scripts/migrate_table_keys.py` in Phase 1.2's Stage 3. The Lambda no longer reads
or writes it. It stays untouched as the rollback and is removed deliberately after the new keys
have soaked.

## Migrations

Follow `scripts/migrate_story_keys.py`:

- Module docstring: date, before and after, steps, runbook (pause the schedule, dry run, `--apply`, deploy)
- Dry run by default, writes only with `--apply`, and every step idempotent
- Old data is deleted only after the new Lambda works. PITR and S3 versioning cover 35 days
  - Within one table or bucket: a separate flag (`--delete-old`), as `migrate_story_keys.py` does
  - To a new table (`scripts/migrate_table_keys.py`): no delete step. Drop the old table whole through Terraform in two applies, `deletion_protection_enabled = false` and then the resource. A table deleted with PITR on keeps a free 35-day SYSTEM backup
- Raise a `MigrationError` before any write if the data doesn't look as expected
- Test against moto with seeded old-shape data. Keep the script and tests in `scripts/` after running
- Run with admin creds, not the Lambda role (`infra/iam`)
