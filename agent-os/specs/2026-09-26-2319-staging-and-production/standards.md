# Standards for Staging and Production

## Added by this spec

- **infra/environments** (Task 2, extended in Tasks 3 and 6) — Production keeps unsuffixed names,
  because a rename is a replace (`infra/data-retention`). Every other environment is
  `weather-story-bot-<env>`. Production-only resources, and why: the account-wide budget and the MVP
  `posted` rollback table. Per-environment differences are variables or `local.production`, never
  forked `.tf` files. Metric namespaces are per environment, since metric filters without
  dimensions would otherwise merge environments. Each environment has its own Telegram bot and
  SSM parameter, and a bot is never made an admin in another environment's channels. One `ENV` in
  the Makefile selects the backend config, var file, `TF_DATA_DIR` and plan file together. `ENV` is
  required and `environment` is never set in a tfvars file. **Staging is where real posts get
  watched.**
- **infra/budget** (Task 5) — Fixed monthly cost stays O(1) in offices. Per-office visibility comes
  from queries and reports, not per-office alarms or custom metrics. Prefer pay-per-use with no
  idle cost. Every spec carries a `cost.md` from `make cost`. Retention is a cost decision. The
  account budget rises deliberately, in the spec that raises expected spend.

## Amended by this spec

- **infra/data-retention** (Task 2) — The `posted` row becomes production-only. Staging's table
  and bucket carry the same protections and undo windows as production's. Resetting staging means
  deleting items, never the table.
- **infra/iam** (Task 2) — The `TelegramToken` statement is scoped to that environment's own
  parameter (`/weather-story-bot/telegram-token` in production,
  `/weather-story-bot/<env>/telegram-token` elsewhere). No environment's role can read another's
  token.
- **infra/alarms** (Task 4) — An alarm that treats missing data as `breaching` exists only while
  the schedule is enabled (`count = local.schedule_enabled ? 1 : 0`), or it sits in ALARM on an
  idle stack and trains you to ignore the inbox. Custom metrics use `local.metric_namespace`,
  which is per environment.
- **global/principles** (Task 6) — Under "Local tools are read-only", "to watch real behaviour,
  use a deployed environment" becomes "use staging (`infra/environments`)".

## Constraining, unchanged

- **testing/log-contracts** — Staging's metric filters match the same exact messages
  (`Telegram message sent`, `Ambiguous stories from NWS`) in its own namespace. No log message is
  renamed, so no test changes.
- **infra/data-retention** — Stage 1's production plan must show no `must be replaced` or
  `destroy`. Only "has moved to" lines are allowed.
- **infra/alarms** — Staging's alarm names carry `-staging`, and their descriptions stay
  runbooks with that environment's `logs_console_url`, which follows from `local.name` with no
  extra work.
- **backend/env-config** — Unchanged: the Lambda's settings don't know which environment
  they're in, and they don't need to.

Full text: `agent-os/standards/`.
