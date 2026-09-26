# DynamoDB Schema

## Keys (`aws_dynamodb_table.state`)

One table, generic key names, every item under its office's partition:

| Item | `PK` | `SK` |
|---|---|---|
| Current story | `OFFICE#<id>` | `STORY#<start_utc_iso>#<story_key>` |
| Ledger event | `OFFICE#<id>` | `EVENT#<start_utc_iso>#<story_key>#<at_utc_iso>` |
| Daily run record | `OFFICE#<id>` | `DAY#<YYYY-MM-DD>` (UTC day) |
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
