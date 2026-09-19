# Data Retention

The S3 archive permanently records every story revision. The DynamoDB table is dedupe state: protected, but not history. Both keep a 35-day window to undo bad writes or migrations.

| Store | Protection | Undo window |
|---|---|---|
| `aws_dynamodb_table.posted` | `deletion_protection_enabled = true` | PITR, `recovery_period_in_days = 35` |
| `aws_s3_bucket.archive` | versioning, public access blocked | `noncurrent_days = 35` |

- Never expire current archive objects. No `expiration { days/date }` in the lifecycle rule
- If you change one undo window, change the other to match
- A change that force-replaces or destroys the table or bucket (key schema, name) needs a stop. Don't disable protection or apply a replace yourself. Propose a migration (new resource + script like `scripts/migrate_story_keys.py`) and ask first
- Check `make plan` for `must be replaced` / `destroy` on these resources before any `deploy`
- Put a comment next to each protection setting saying why it's there and how to remove it on purpose
