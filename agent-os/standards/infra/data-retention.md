# Data Retention

The S3 archive permanently records every story revision. The DynamoDB state table holds dedupe state and, from Phase 1.2, the ledger of what the bot did: both are kept forever with no TTL. All stores keep a 35-day window to undo bad writes or migrations.

| Store | Protection | Undo window |
|---|---|---|
| `aws_dynamodb_table.state` | `deletion_protection_enabled = true`, no TTL | PITR, `recovery_period_in_days = 35` |
| `aws_dynamodb_table.posted` (MVP, rollback until removed; production only) | `deletion_protection_enabled = true` | PITR, `recovery_period_in_days = 35` |
| `aws_s3_bucket.archive` | versioning, public access blocked | `noncurrent_days = 35` |

- The CI apply roles can't delete the tables or the archive, nor change PITR, the archive's
  versioning or its lifecycle rules (explicit Denies, `infra/iam`). Those changes are laptop-only, with MFA
- Every environment's table and bucket carry the same protections and undo windows as production's (`infra/environments`). Reset staging by deleting items, never the table
- The artifacts bucket (`infra/bootstrap/`) is the one place objects may expire: zips (90 days),
  saved plans (14) and noncurrent versions (7) are derived and rebuildable. It holds no story or
  record, and the CI roles can't delete from it (an explicit Deny), so expiry is by lifecycle rule only
- Never expire current archive objects. No `expiration { days/date }` in the lifecycle rule. Aborting
  incomplete multipart uploads (`abort_incomplete_multipart_upload`) is allowed: it removes no stored object
- Never add a `ttl` block to the state table. Records are permanent by decision
- If you change one undo window, change the others to match
- A change that force-replaces or destroys a table or the bucket (key schema, name) needs a stop. Don't disable protection or apply a replace yourself. Propose a migration (new resource + script like `scripts/migrate_story_keys.py`) and ask first
- Check `make plan ENV=<env>` for `must be replaced` / `destroy` on these resources before any `deploy`
- Put a comment next to each protection setting saying why it's there and how to remove it on purpose
