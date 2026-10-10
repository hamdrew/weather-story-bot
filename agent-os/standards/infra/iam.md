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

## CI roles (`infra/bootstrap/`)

The pipeline's roles live in their own stack, applied by hand with MFA (`make bootstrap-plan` /
`bootstrap-deploy`), so the pipeline can never widen its own permissions. The rules above hold, with
these scoped exceptions and additions:

- **Trust:** `StringEquals` on `aud` (`sts.amazonaws.com`) and an exact `sub`, never `StringLike`.
  `ci-pr-plan` is `repo:<repo>:pull_request`, `ci-plan` is `...:ref:refs/heads/main`, and each
  `ci-apply-<env>` is `...:environment:<env>`
- **Plan roles may use `Get*`/`List*`/`Describe*` per service**, but only on the project's resource
  ARNs and never on objects, items or parameters: bucket ARNs and never `bucket/*`, no `GetItem`,
  `Query` or `Scan`, nothing in `ssm` or `kms`. `ReadOnlyAccess` would include `ssm:GetParameter`,
  and the `aws/ssm` key lets any principal in the account decrypt the Telegram token
- **Names:** staging matches by prefix (`weather-story-bot-staging*`). Production's names are a
  prefix of staging's, so production uses exact names, never a pattern. Bucket ARNs are exact in
  both: in IAM `*` also matches `/`, so a bucket pattern beside `s3:Get*` would read its objects
- **Tag conditions on apply roles:** `aws:ResourceTag/Environment` on existing resources and
  `aws:RequestTag/Environment` + `aws:TagKeys` on creates, where the action supports them. An apply
  role may hold a tag-write action only on its own environment's names, with `aws:RequestTag`
  pinning `Environment` to its own environment, so it can't retag a resource across environments.
  Never `aws:ResourceTag` on a tag write: creating a tagged resource also authorizes the tag action
  on it, and a resource that doesn't exist yet has no tags. No `Untag*` action: an untag request
  carries no `aws:RequestTag`, so removing a default tag goes through the laptop with MFA
- **`PutMetricAlarm` creates and updates**, so it is allowed both on `aws:RequestTag` (a new
  alarm) and on `aws:ResourceTag` (an existing one, whose update may send no tags)
- **Permissions boundary per environment** (`<env name>-boundary`, exact ARNs, never a pattern).
  `iam:CreateRole`, `PutRolePolicy` and `AttachRolePolicy` require `iam:PermissionsBoundary` to be
  the role's own environment's boundary, and no CI role can create, change or delete a policy or a
  boundary. `iam:PassRole` carries `iam:PassedToService`
- **Explicit Deny** on `dynamodb:DeleteTable`, `s3:DeleteBucket` and `s3:DeleteObject*` for the
  tables, the archive and the artifacts bucket (`infra/data-retention`, now enforced by IAM). A
  role's only delete is its own `.tflock` object. A second Deny covers what would undo it by other
  means: `dynamodb:UpdateContinuousBackups` (PITR), `s3:PutBucketVersioning` and
  `s3:PutLifecycleConfiguration` on the tables and archives. Those change from the laptop with MFA,
  so a new environment's table and archive are created there too. `UpdateTable` stays allowed and
  can turn off deletion protection, but `DeleteTable` is still denied
- **Size:** a role's inline policies total at most 10,240 characters and a managed policy 6,144, so
  an apply role is three managed policies grouped by what they do (`apply_group_of`). A statement
  that grows past a limit moves group; the plan fails on an unassigned statement. Nothing offline
  measures the size (the tests mock the policy JSON), so a statement over the limit fails at apply
- **Gaps (no tag condition keys, so only names scope them):** EventBridge Scheduler schedules,
  AWS Budgets, `sns:Subscribe` / `Unsubscribe` (a subscription carries no tags), and every read
  (`Describe*`, `Get*`, `List*`). The log group, SNS, CloudWatch alarm and S3 bucket conditions are
  unproven until the first pipeline plan and apply run under them (Phase 2.1 Gates 4a and 4b): an
  `AccessDenied` there is fixed in `infra/bootstrap` and applied by hand
