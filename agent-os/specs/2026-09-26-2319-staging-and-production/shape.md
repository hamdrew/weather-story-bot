# Staging and Production — Shaping Notes

Shaped 2026-09-26. Roadmap Phase 2.0.

## Scope

Two named deployments from one `infra/`. **Production** keeps every resource name, state key and
behaviour it has today. **Staging** is a new, near-free copy: MKX only, a private test channel, its
own Telegram bot, the schedule off, invoked by hand with `make invoke-staging`. It replaces
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
  `/weather-story-bot/staging/telegram-token`, and staging's Lambda role can read only that
  parameter. The staging bot is never made an admin of a public channel, so a wrong chat id in
  `staging.tfvars` fails at Telegram instead of posting publicly, and a leaked staging token is
  worthless. A precondition refuses a non-production plan that points at production's parameter.
- **Staging's alarm set is the three that tolerate idleness:** `errors`, `repost-loop` and
  `nws-ambiguous`, which all treat missing data as not breaching, on a `-staging` SNS topic.
  `missed-runs` and `quiet` exist only while the schedule is enabled, a rule tied to the schedule
  rather than the environment name. This keeps staging useful for testing alarm changes with
  `set-alarm-state` before they reach production.
- **Staging's data has production's protections:** deletion protection, 35-day PITR and bucket
  versioning. That keeps `storage.tf` free of environment branches, and staging then tests what
  production runs. It costs pennies at staging's size. Reset staging by deleting its `STORY#`
  items, never the table.
- **`make invoke-staging` only.** Production runs on its schedule, and the README's raw
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
  `weather-story-bot` in production. Stage 1's gate is a production plan with 0 to add, change or
  destroy.
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
  `count` to the budget, the MVP table and the two schedule-bound alarms moves each production
  object to `[0]` automatically, and removing `count` in a revert moves it back.
- **No `Environment` tag.** The `Project` default tag is already `local.name`, which differs by
  environment. A new tag would put an in-place update on every production resource and bury
  the zero-diff gate.
- **No Python changes.** Nothing in `src/` names an AWS resource; the Lambda gets everything from
  its environment variables. Only `scripts/infracost_usage.py` and its test change.
- **Same bucket, same credentials.** Separate state doesn't mean separate permissions. Phase 2.1's
  OIDC roles can scope a staging role to the `weather-story-bot/staging/*` prefix, and separate
  AWS accounts would be the strongest isolation. That's out of scope for a single-user account.

## Context

- **Visuals:** None.
- **References:** See `references.md`: all of `infra/`, the `Makefile`, `infracost.yml`,
  `scripts/infracost_usage.py`, and the README's Deploy and Alerts sections.
- **Product alignment:** Roadmap Phase 2.0, executed as written. It settles the open bot question
  (a separate bot) and adds the namespace, budget, tfvars and MVP-table findings above. It sets up
  Phase 2.1 ("staging applies before production") and follows the budget-first rule: staging's
  cost is estimated in Task 5, before anything is created.

## Standards Applied

New with this spec:

- `infra/environments` — naming, production-only resources, differences as variables, the
  `ENV`-driven Makefile, one bot per environment, and "staging is where real posts get watched"
- `infra/budget` — fixed cost O(1) in offices, pay-per-use, a cost section in every spec, and the
  budget rises deliberately

Amended by this spec:

- `infra/data-retention` — the MVP table is production-only; staging keeps the same protections
- `infra/iam` — the Telegram token parameter is per environment
- `infra/alarms` — alarms that treat missing data as breaching exist only while the schedule is
  enabled; metric namespaces are per environment
- `global/principles` — "use a deployed environment" becomes "use staging"

Constraining but unchanged:

- `testing/log-contracts` — staging's metric filters match the same exact messages; nothing is
  renamed
