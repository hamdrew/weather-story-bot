# IAM

Grant only what the code calls, so a bug or a compromised dependency can't delete the archive or table, read other secrets or touch the rest of the account.

- Write policies as `data "aws_iam_policy_document"` blocks, not inline JSON
- One statement per need, each with a `sid` (`PostedState`, `Archive`, `TelegramToken`)
- List the exact actions the code calls, e.g. `dynamodb:GetItem`, `dynamodb:PutItem`. No `Delete*`, `Scan` or `service:*`
- Scope resources to the narrowest ARN or key prefix: `"${aws_s3_bucket.archive.arn}/stories/*"`, the one SSM parameter ARN
- Use `*` only where the API has no resource-level permissions, and add a comment saying so
- Add a new permission in the same change as the code that calls it
- Service trust policies (other than Lambda) add the confused-deputy guard:

```hcl
condition {
  test     = "StringEquals"
  variable = "aws:SourceAccount"
  values   = [data.aws_caller_identity.current.account_id]
}
```

- Scripts and backfills (e.g. `scripts/migrate_story_keys.py`) run with admin creds, never through the Lambda role
