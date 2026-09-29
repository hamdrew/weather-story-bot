# Standards for Staging and Production

## Added by this spec

- **infra/environments** (Task 2, extended in Tasks 3 and 7) — Production keeps unsuffixed names,
  because a rename is a replace (`infra/data-retention`). Every other environment is
  `weather-story-bot-<env>`. Production-only resources, and why: the account-wide budget and the MVP
  `posted` rollback table. Per-environment differences are variables or `local.production`, never
  forked `.tf` files. What Terraform creates is derived from `environment`; what exists outside
  Terraform (the token parameter, chat ids, the alert email) is a required variable, never a
  hard-coded per-environment value. Metric namespaces are per environment, since metric filters without
  dimensions would otherwise merge environments. Every resource carries a lowercase `Environment`
  tag through `default_tags` (IAM tag conditions compare case-sensitively), things made by hand
  are tagged by hand, and every archive bucket has ABAC on, with the S3 Control tag actions that
  implies for whoever applies Terraform. Each environment has its own Telegram bot and
  SSM parameter, and a bot is never made an admin in another environment's channels. One `ENV` in
  the Makefile selects the backend config, var file, `TF_DATA_DIR` and plan file together. `ENV` is
  required and `environment` is never set in a tfvars file. **Staging is where real posts get
  watched.**
- **infra/budget** (Task 6) — Fixed monthly cost stays O(1) in offices. Per-office visibility comes
  from queries and reports, not per-office alarms or custom metrics. Prefer pay-per-use with no
  idle cost. Every spec carries a `cost.md` from `make cost`. Retention is a cost decision. The
  account budget rises deliberately, in the spec that raises expected spend.

## Amended by this spec

- **infra/data-retention** (Task 2) — The `posted` row becomes production-only. Staging's table
  and bucket carry the same protections and undo windows as production's. Resetting staging means
  deleting items, never the table.
- **infra/iam** (Task 2) — The `TelegramToken` statement is scoped to that environment's own
  parameter (`/weather-story-bot/telegram-token` in production,
  `/weather-story-bot-<env>/telegram-token` elsewhere), a required variable validated against
  `local.name`. No environment's role can read another's
  token.
- **infra/iam** (Task 5) — ABAC rules. Tag conditions (`aws:ResourceTag/Environment`) are added
  to exact ARNs, never used instead of them. Allow + `StringEquals` only, so a missing tag fails
  closed; never an Allow with `StringNotEquals`. A role constrained by tag conditions never holds
  tag-write actions, or it could retag its way into access. Everything a condition reads
  (resource tags, bucket ABAC, hand-tagged parameters) goes live at least one deploy before the
  condition. `State`, `TelegramToken` and `Archive` carry conditions; `Logs` doesn't, because
  it's unverified whether `PutLogEvents` reads log-group tags and a denial would silently lose
  the logs and the alarms built on them.
- **infra/alarms** (Task 4) — An alarm that treats missing data as `breaching` exists only while
  the schedule is enabled (`count = local.schedule_enabled ? 1 : 0`), or it sits in ALARM on an
  idle stack and trains you to ignore the inbox. Custom metrics use `local.metric_namespace`,
  which is per environment.
- **global/principles** (Task 7) — Under "Local tools are read-only", "to watch real behaviour,
  use a deployed environment" becomes "use staging (`infra/environments`)".

## Constraining, unchanged

- **testing/log-contracts** — Staging's metric filters match the same exact messages
  (`Telegram message sent`, `Ambiguous stories from NWS`) in its own namespace. No log message is
  renamed, so no test changes.
- **infra/data-retention** — Stage 1's production plan must show no `must be replaced` or
  `destroy`. Only moves, tag-only in-place updates and the `aws_s3_bucket_abac.archive` addition
  are allowed, checked by Task 3's plan check. Bucket ABAC doesn't touch versioning, lifecycle or
  public access, so the standard doesn't change for it.
- **infra/alarms** — Staging's alarm names carry `-staging`, and their descriptions stay
  runbooks with that environment's `logs_console_url`, which follows from `local.name` with no
  extra work.
- **backend/env-config** — Unchanged: the Lambda's settings don't know which environment
  they're in, and they don't need to.

Full text: `agent-os/standards/`.
