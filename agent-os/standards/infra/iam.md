# IAM

Grant only what the code calls, so a bug or a compromised dependency can't delete the archive or table, read other secrets or touch the rest of the account.

- Write policies as `data "aws_iam_policy_document"` blocks, not inline JSON
- One statement per need, each with a `sid` (`State`, `Archive`, `TelegramToken`)
- List the exact actions the code calls, e.g. `dynamodb:GetItem`, `dynamodb:PutItem`. No `Scan`, `service:*` or wildcard `Delete*`
- The one delete is item-level `dynamodb:DeleteItem` on the state table, for the office lease's release. Never `DeleteTable`, `DeleteObject` or `DeleteBucket`: the table and archive are permanent (`infra/data-retention`)
- Scope resources to the narrowest ARN or key prefix: `"${aws_s3_bucket.archive.arn}/stories/*"`, the one SSM parameter ARN
- The `TelegramToken` statement names that environment's own parameter (`var.telegram_token_param_name`, validated to sit under `/${local.name}/`), so no environment's role can read another's token (`infra/environments`)
- Use `*` only where the API has no resource-level permissions, and add a comment saying so
- Add a new permission in the same change as the code that calls it
- Scripts and backfills (e.g. `scripts/migrate_story_keys.py`) run with admin creds, never through the Lambda role
- Service trust policies (other than Lambda) add the confused-deputy guard:

```hcl
condition {
  test     = "StringEquals"
  variable = "aws:SourceAccount"
  values   = [data.aws_caller_identity.current.account_id]
}
```

## Tag conditions (ABAC)

The `State`, `TelegramToken` and `Archive` statements add `aws:ResourceTag/Environment` = `[var.environment]`, so a role can only reach resources tagged for its own environment, even if an ARN is wrong.

- Add the condition to the exact ARN, never use it instead of the ARN
- Allow + `StringEquals` only, so a missing tag fails closed. Never an Allow with `StringNotEquals`
- A role constrained by tag conditions never holds tag-write actions (`TagResource`, `ssm:AddTagsToResource` and the like), or it could retag its way into access
- Everything a condition reads (resource tags, bucket ABAC, hand-tagged parameters) goes live at least one deploy before the condition does. The exception is a new environment, which is created with both at once: nothing depends on it yet, and its first run is the proof (staging at Phase 2.0 Gate 2)
- `Logs` has no condition: whether `PutLogEvents` evaluates log-group tags is unverified, and a wrong guess loses logs quietly (and the metric-filter alarms with them)
- Comment each condition with what it reads: DynamoDB needs the account's ABAC setting on (console Settings page only), SSM reads the parameter's own hand-made tags, S3 object actions read the bucket's tags and need bucket ABAC on
