# Staging and Production — Shaping Notes

Shaped 2026-09-26. Roadmap Phase 2.0.

## Scope

Two named deployments from one `infra/`. **Production** keeps every resource name, state key and
behaviour it has today. **Staging** is a new, near-free copy: MKX only, a private test channel, its
own Telegram bot, the schedule off, started and paused by hand with `make start ENV=staging` / `make pause ENV=staging`. It replaces
"run it locally and watch it post", which Phase 1.2 removed on purpose when the CLI became
read-only, and it gives Phase 2.1's pipeline somewhere to apply before production.

Also in scope, per the roadmap: the new `infra/budget` standard, and the rule that staging is
where real posts get watched. Out of scope: CI/CD (Phase 2.1), more offices (Phase 2.2) and
separate AWS accounts.

## Decisions

### Shaped with the user

- **Separate state through per-environment files, not workspaces.** `infra/envs/<env>.backend.hcl`
  and `<env>.tfvars`, a `TF_DATA_DIR` per environment, and one `ENV` in the Makefile that selects
  the backend, var file, data dir and plan file together. Production's state key
  (`weather-story-bot/terraform.tfstate`) doesn't move, so there's no state migration. Staging's is
  `weather-story-bot/staging/terraform.tfstate`, with its own lock file. Workspaces were declined:
  the selected workspace is hidden, sticky state, and HashiCorp advises against using them as
  environment boundaries.
  - **Why a data dir per environment:** `.terraform/` remembers which backend it was initialized
    against. With a shared dir, switching environments needs `init -reconfigure`, and forgetting it
    points a staging plan at production's state. Separate dirs make that mistake unreachable.
- **`ENV` is required,** with no default. The dangerous environment shouldn't be the one you get
  by forgetting a word. The `environment` Terraform variable is passed by the Makefile as `-var`
  and never kept in a tfvars file, so it can't disagree with the backend.
- **A separate Telegram bot for staging** settles the roadmap's open question. Its token lives at
  `/weather-story-bot-staging/telegram-token`, and staging's Lambda role can read only that
  parameter. The staging bot is never made an admin of a public channel, so a wrong chat id in
  `staging.tfvars` fails at Telegram instead of posting publicly, and a leaked staging token is
  worthless. `telegram_token_param_name` is a required variable validated to sit under
  `/${local.name}/`, so a plan can't point at another environment's parameter (decided in Task 2:
  values that exist outside Terraform are variables, never hard-coded per environment).
- **Staging has production's five alarms,** on a `-staging` SNS topic, so alarm changes can be
  tested with `set-alarm-state` before they reach production. Every environment's alarms are
  created on, and their actions pause and start with the schedule (revised 2026-10-02; the
  first design dropped `missed-runs` and `quiet` while staging was idle).
- **Staging's data has production's protections:** deletion protection, 35-day PITR and bucket
  versioning. That keeps `storage.tf` free of environment branches, and staging then tests what
  production runs. It costs pennies at staging's size. Reset staging by deleting its `STORY#`
  items, never the table.
- **`make start` / `make pause`, with `ENV`.** They toggle the schedule and the alarm actions by
  API (both are in `ignore_changes`). The README's raw
  `aws lambda invoke` stays as production's break-glass smoke test.
- **A new `infra/environments` standard** holds the environment rules, next to the roadmap's
  `infra/budget`.
- **Terragrunt considered and declined.** It pays off with many modules that depend on each
  other, or environments multiplied across accounts and regions. This project has one root
  module, two environments, one account and one region, so it would replace a Makefile guard and
  two flags while adding a binary for local use and for CI, a restructure, and a layer between the
  user and the plain `terraform plan` the deploy gates rely on. Revisit it for dependent stacks
  (for example, an account-level stack for the budget) or an AWS account per environment. More
  offices never trigger it, because offices are variables inside one module. `envs/<env>.*` maps
  one-to-one onto Terragrunt's `remote_state` and `inputs` if that day comes.

### Found while shaping

- **Production stays unsuffixed; only staging takes `-staging`.** Threading the environment name
  into every resource name would rename the state table and the archive bucket. A rename is a
  replace, and `infra/data-retention` forbids replacing either one. So `local.name` stays
  `weather-story-bot` in production. Stage 1's gate is a production plan with nothing destroyed
  or replaced (originally 0 to add, change or destroy; see "Changed after shaping").
- **The metric namespace is shared unless we split it.** Both log metric filters write to
  `WeatherStoryBot` without dimensions, so staging's posts would count in production's
  `StoriesPosted`, which feeds `quiet` and `repost-loop`. Staging posts could hide a silent
  production or trip its repost-loop alarm. Production keeps `WeatherStoryBot`, and staging
  uses `WeatherStoryBot/staging`. Renaming production's namespace would reset its history, and
  `quiet` (missing data = breaching) could fire the day after the deploy.
- **The budget covers the whole account,** not the project. A staging copy would send a second
  email for the same spend, so it's production-only (`count`).
- **`infra/terraform.tfvars` is auto-loaded.** Anything missing from `staging.tfvars` would fall
  back silently to production's value, including `offices` and its public chat ids. It moves to
  `envs/production.tfvars`, which only loads when named.
- **The MVP `posted` table is production's rollback,** so it's production-only as well. Adding
  `count` to the budget and the MVP table moves each production
  object to `[0]` automatically, and removing `count` in a revert moves it back.
- **No `Environment` tag** (reversed below). The `Project` default tag is already `local.name`,
  which differs by environment. A new tag would put an in-place update on every production
  resource and bury the zero-diff gate.
- **No Python changes.** Nothing in `src/` names an AWS resource; the Lambda gets everything from
  its environment variables. Only `scripts/infracost_usage.py` and its test change.
- **Same bucket, same credentials.** Separate state doesn't mean separate permissions. Phase 2.1's
  OIDC roles can scope a staging role to the `weather-story-bot/staging/*` prefix, and separate
  AWS accounts would be the strongest isolation. That's out of scope for a single-user account.

### Changed after shaping

- **An `Environment` tag after all.** The user chose to scope the Lambda role with tag conditions,
  which need a tag to read. `Environment = var.environment` (always lowercase: tag conditions are
  case-sensitive) goes on everything through `default_tags`, next to `Project`. Gate 1's plan now
  carries a tag-only update on every taggable resource, so it's checked by a script over
  `terraform show -json` rather than by eye (Task 3): moves, tag-only updates and one allowed
  addition pass; anything else fails.
- **Bucket ABAC in Stage 1.** S3 ignores a general purpose bucket's tags in conditions until ABAC
  is on, so `aws_s3_bucket_abac` enables it on the archive: Gate 1's one addition. It changes no
  access by itself. Once it's on, bucket tags are written through S3 Control `TagResource`, so
  Phase 2.1's CI roles need `s3:TagResource`, `s3:UntagResource` and `s3:ListTagsForResource`.
- **Tag conditions on the Lambda role, in Stage 2 (Task 5).** `State`, `TelegramToken` and
  `Archive` add `aws:ResourceTag/Environment` to their exact ARNs, as Allow + `StringEquals`, so a
  missing tag fails closed. `Logs` doesn't: whether `PutLogEvents` reads log-group tags is
  unverified, and a denial would lose the logs and the alarms built on them without a sound.
  DynamoDB's account-level ABAC setting can't be read from the CLI, so staging's first run
  proves it before production takes the conditions.
- **What a condition reads goes live a deploy before the condition.** Tags and bucket ABAC deploy
  at Gate 1, production's token parameter is tagged by hand before it, and the conditions follow
  at Gate 3, after staging's Gate 2 has proved them. Rolling back the conditions is a policy
  revert; the tags and ABAC are harmless alone.

## Context

- **Visuals:** None.
- **References:** See `references.md`: all of `infra/`, the `Makefile`, `infracost.yml`,
  `scripts/infracost_usage.py`, and the README's Deploy and Alerts sections.
- **Product alignment:** Roadmap Phase 2.0, executed as written. It settles the open bot question
  (a separate bot) and adds the namespace, budget, tfvars and MVP-table findings above. It sets up
  Phase 2.1 ("staging applies before production") and follows the budget-first rule: staging's
  cost is estimated in Task 6, before anything is created.

## Standards Applied

New with this spec:

- `infra/environments` — naming, production-only resources, differences as variables, the
  `ENV`-driven Makefile, one bot per environment, the lowercase `Environment` tag and bucket
  ABAC, and "staging is where real posts get watched"
- `infra/budget` — fixed cost O(1) in offices, pay-per-use, a cost section in every spec, and the
  budget rises deliberately

Amended by this spec:

- `infra/data-retention` — the MVP table is production-only; staging keeps the same protections
- `infra/iam` — the Telegram token parameter is per environment; ABAC rules for tag conditions
  (Task 5)
- `infra/alarms` — every alarm is created on and its actions are toggled with the schedule; metric namespaces are per environment
- `global/principles` — "use a deployed environment" becomes "use staging"

Constraining but unchanged:

- `testing/log-contracts` — staging's metric filters match the same exact messages; nothing is
  renamed
