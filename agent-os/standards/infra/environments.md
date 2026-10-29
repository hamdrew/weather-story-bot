# Environments

One `infra/` deploys every environment. `var.environment` (`production` or `staging`, no default)
selects everything that differs, so the environments can't drift apart through forked files. The
locals it drives (`production`, `name`) live in `infra/locals.tf`.

## Environment-specific values

- **What Terraform creates is derived** from `var.environment` by one rule: names, tags, the metric
  namespace, production-only `count`s. Environments can't disagree about a convention
- **What exists outside Terraform is a required variable** with no default, set in that
  environment's tfvars: the Telegram token parameter, chat ids, the alert email. Never hard-code
  one environment's value in a local, a default or a conditional
- A variable whose value would print in a public log (`offices`, `alert_email`, `nws_user_agent`)
  is `sensitive = true`. The repo is public, and a plan prints variable values
- Validate such a variable against the environment where you can (the token parameter must sit
  under `/${local.name}/`), so one environment's value can't be pasted into another's tfvars

## Names

Production keeps the unsuffixed names it was created with (`weather-story-bot`). Every other
environment is `weather-story-bot-<env>`.

- Renaming the table or the bucket is a replace, which `infra/data-retention` forbids, so
  production never takes a suffix
- Everything named from `local.name` follows automatically: function, table, bucket, roles, topic,
  alarms, schedule, and the `Project` tag Cost Explorer splits on

```hcl
name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"
```

## Tags

- Every resource carries `Environment = var.environment` and `Project = local.name` through the
  provider's `default_tags` (`infra/providers.tf`). Never set either per resource
- `Environment` is always the lowercase `production` or `staging`. It's what IAM tag conditions
  (`aws:ResourceTag/Environment`) match, and they compare case-sensitively
- Things created by hand get the same tag by hand: each environment's token parameter is created
  with `--tags Key=Environment,Value=<env>` (README setup)
- Every environment's archive bucket has ABAC enabled (`aws_s3_bucket_abac`). Without it S3
  ignores bucket tags in policy conditions. With it, bucket tags are written through S3 Control
  `TagResource`, so whoever applies Terraform needs `s3:TagResource`, `s3:UntagResource` and
  `s3:ListTagsForResource`, or the provider falls back to `PutBucketTagging` and the tag change
  fails

## Differences are variables or `local.production`

- Express a per-environment difference as a variable or a `local.production` conditional, never
  as a forked `.tf` file or a copy of a resource
- A production-only resource takes `count = local.production ? 1 : 0` with a comment saying why,
  and outputs read it with `one(<resource>[*].<attr>)`
- Adding `count` to an existing resource moves it to `[0]`. The production plan shows
  "has moved to", not a replace, and anything that addresses it (`scripts/infracost_usage.py`)
  uses `[0]`

| Production only | Why |
|---|---|
| `aws_budgets_budget.monthly` | Covers the whole account; a copy per environment sends duplicate emails for the same spend |
| `aws_dynamodb_table.posted` | The MVP table is production's rollback; no other environment ever had MVP data |

## Staging

- **Staging is where real posts get watched.** Production is pipeline-only (`infra/pipeline`):
  `plan` and `deploy` refuse it unless they run in Actions or `BREAK_GLASS=1` is on the command line
- **Every environment's schedule is created `DISABLED` and its alarms are created on.** There is
  no `schedule_enabled` variable, so no environment differs by a flag. `mise run start <env>` and
  `mise run pause <env>` toggle the schedule and the alarm actions through the API
  (`scripts/set_run_state.py`), and `ignore_changes` on `state` and `actions_enabled` keeps an apply
  from undoing them. `lifecycle` can't be conditional, so production is ignored too: its schedule
  and alarms stay as they are, and `mise run pause production` is how you stop it. Terraform
  never will
- Alarms are created on, so a new environment emails (`missed-runs` and `quiet` breach on missing
  data) until it is started. That is deliberate: the first alert proves the alarms and the email
  path work, and an environment you forgot to start can't be silent
- Pausing turns the actions off and keeps the alarms, so the breaching ones sit in ALARM while
  paused, silently. Starting re-enables them, and the first runs bring them back to OK
- A new alarm goes in `local.alarm_names` (`infra/monitoring.tf`), or the toggle misses it

## Telegram

- Each environment has its own Telegram bot, and its token lives in its own SSM parameter under
  that environment's name: `/weather-story-bot/telegram-token` in production,
  `/weather-story-bot-<env>/telegram-token` elsewhere. `var.telegram_token_param_name` is required
  and validated to equal `/${local.name}/telegram-token`, the one name the boundary allows. The prefixes differ in the first path segment,
  so no environment's parameter (or IAM grant) can land inside another's
- A bot is never made an admin in another environment's channels, so a staging bug can't post
  to a public channel even with the wrong chat id

## Metrics

Custom metric namespaces are per environment (`local.metric_namespace`): `WeatherStoryBot` in
production, `WeatherStoryBot/<env>` elsewhere. The log metric filters have no dimensions, so a
shared namespace would merge staging's posts into production's `quiet` and `repost-loop` alarms.
Production keeps its original namespace so its metric history carries on.

## Tasks

The environment argument of the `plan`, `deploy`, `start` and `pause` tasks (`mise run plan <env>`) selects the backend config, the var file, the data dir and the plan file together, so
they can't disagree:

| `<env>` selects | Path (under `infra/`) |
|---|---|
| Backend config | `envs/<env>.backend.hcl` (its own state key) |
| Var file | `envs/<env>.tfvars` |
| Data dir | `.terraform-<env>/` (`TF_DATA_DIR`, relative to `-chdir`) |
| Plan file | `deploy-<env>.tfplan` |

- `plan` and `deploy` refuse `production` unless `GITHUB_ACTIONS=true` or `BREAK_GLASS=1` is set on
  the command line (`infra/pipeline`). `staging` has no such guard
- The environment is a required positional argument with `choices "staging" "production"`, so mise
  refuses anything else, and an exported variable can't stand in for it
- `plan` builds first and passes the zip's hash as `-var lambda_zip_sha256=<base64>`, so a plan is
  made for one exact build. `deploy` rebuilds and refuses to apply when the zip's hash isn't the
  planned one. The zip is reproducible (`scripts/build_zip.py`), so an unchanged build plans as
  No changes
- The Lambda's code comes from S3, never a local file in Terraform: `s3_key` is
  `<env>/lambda/<base64url of the zip's hash, unpadded>.zip` (`local.lambda_s3_key`, also an output).
  After the hash check, `deploy` reads the bucket and key from the saved plan and uploads with
  `If-None-Match: *`. A 412 means those bytes are already there, since the key is the content
- `artifacts_bucket` and `permissions_boundary_arn` are required variables (both created by
  `infra/bootstrap`). The boundary is validated to be this environment's own, and both the Lambda
  and Scheduler roles are created under it
- `environment` is passed as `-var environment=<env>`, never kept in a tfvars file, so it can't
  disagree with the backend
- A data dir per environment, because `.terraform/` remembers the backend it was initialized
  against: with a shared one, a forgotten `-reconfigure` points a staging plan at production's
  state
- Never an `infra/terraform.tfvars`: Terraform auto-loads it, so any variable missing from an
  environment's file would silently take its value (production's chat ids included)
