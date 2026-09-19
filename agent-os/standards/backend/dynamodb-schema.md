# DynamoDB Schema

## Current keys (MVP only)

| Attribute | Role | Holds |
|---|---|---|
| `office_id` | partition key | `MKX` |
| `image_id` | sort key | `story#<story_key>`, **not** an image UUID |
| `posted_image_id` | attribute | the real image UUID |

- This is a lookup design. The hash sort key has no useful order, so there are no date-range queries and no cross-office listing without a Scan
- Don't rename or reshape the keys in regular work. A future spec (all offices, analytics) will design keys from access patterns and migrate
- Mark each item type with a sort-key prefix (`story#`). Old kinds (bare UUID, `content#`) are ignored, not read
- Any read that isn't an exact key (Scan, Query on `office_id`) filters on the prefix
- Use the low-level client with typed attributes (`{"S": ...}`) and `ConsistentRead=True` on dedupe lookups

## Migrations

Follow `scripts/migrate_story_keys.py`:

- Module docstring: date, before and after, steps, runbook (pause the schedule, dry run, `--apply`, deploy)
- Dry run by default, writes only with `--apply`, and every step idempotent
- Old data is deleted only with a separate flag (`--delete-old`), after the new Lambda works. PITR and S3 versioning cover 35 days
- Raise a `MigrationError` before any write if the data doesn't look as expected
- Test against moto with seeded old-shape data. Keep the script and tests in `scripts/` after running
- Run with admin creds, not the Lambda role (`infra/iam`)
