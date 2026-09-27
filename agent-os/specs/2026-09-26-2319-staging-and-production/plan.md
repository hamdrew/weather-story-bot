# Phase 2.0: Staging and Production

Spec folder: `agent-os/specs/2026-09-26-2319-staging-and-production/`

## Context

Phase 1.2 made the CLI strictly read-only, so there is no longer any way to watch a real post
without deploying to production and posting to the public channel. Phase 2.0 adds a **staging**
deployment from the same `infra/`: MKX only, a private test channel, its own Telegram bot, the
schedule off, and invoked by hand. Phase 2.1's pipeline then has somewhere to apply before
production.

The hard constraint: **production must not be renamed.** Renaming the table or the bucket forces
a replace, and `infra/data-retention` forbids that. Production therefore stays unsuffixed and only
staging takes a `-staging` suffix. The Stage 1 gate is a production `make plan` that shows only
moves: 0 to add, change or destroy.

### What shaping found beyond the roadmap

- **Shared metric namespace.** Both log metric filters write to `WeatherStoryBot` with no
  dimensions. Staging's filter would pour its posts into production's `StoriesPosted` metric,
  which feeds `quiet` and `repost-loop`, so staging posts could hide a quiet production or trip
  its repost-loop alarm. Production keeps `WeatherStoryBot`; staging gets `WeatherStoryBot/staging`.
  Renaming production's namespace would reset its metric history, and `quiet` (missing data =
  breaching) could fire right after the deploy.
- **The budget covers the whole account.** A second copy would double the emails for the same
  spend, so the budget is production-only.
- **`terraform.tfvars` is auto-loaded.** Any variable missing from `staging.tfvars` would silently
  fall back to production's value, `offices` included, which holds the public chat ids. It moves to
  `envs/production.tfvars`, which is never auto-loaded.
- **The MVP `posted` table is production's rollback,** so it's production-only as well.
- **No `Environment` tag.** The `Project` default tag is already `local.name`, which differs per
  environment, so Cost Explorer can split the two without it. Adding a tag would put an in-place
  update on every production resource and bury the zero-diff gate.
- **No Python changes.** Nothing in `src/` hard-codes a resource name. Only
  `scripts/infracost_usage.py` and its test change.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Separation | `infra/envs/<env>.backend.hcl` + `<env>.tfvars`, a `TF_DATA_DIR` per env, and the Makefile passes both from one `ENV` |
| Naming | Production unsuffixed (`weather-story-bot`); staging `weather-story-bot-staging` |
| `environment` var | No default, validated to `production`/`staging`, passed by the Makefile as `-var`, never kept in tfvars, so it can't disagree with the backend |
| `ENV` | Required by `plan`/`deploy`; no default |
| Telegram | A **separate staging bot**, token at `/weather-story-bot/staging/telegram-token`; staging's IAM can read only that parameter; a precondition refuses staging on production's parameter |
| Staging alarms | `errors`, `repost-loop` and `nws-ambiguous` on its own `-staging` SNS topic. `missed-runs` and `quiet` exist only while the schedule is enabled |
| Staging data | The **same protections as production** (deletion protection, PITR, versioning). Reset staging by deleting items, not the table |
| Production-only | The account budget and the MVP `posted` table, via `count`; Terraform moves them to `[0]` automatically |
| Invoke | `make invoke-staging` only; production runs on its schedule |
| Rules | New `infra/environments` and `infra/budget` standards |
| Tooling | Plain Terraform plus the Makefile. **Terragrunt considered and declined** (below) |

### Separate state per environment

Each environment has its own state file and its own lock:

| | Production | Staging |
|---|---|---|
| State object | `s3://<state-bucket>/weather-story-bot/terraform.tfstate` (**unchanged**) | `s3://<state-bucket>/weather-story-bot/staging/terraform.tfstate` |
| Lock (`use_lockfile`) | `…/terraform.tfstate.tflock` | `…/staging/terraform.tfstate.tflock` |
| Local data dir | `infra/.terraform-production/` | `infra/.terraform-staging/` |
| Backend config | `envs/production.backend.hcl` | `envs/staging.backend.hcl` |

- A staging plan can't read, lock or write production's state, and the reverse holds too. A
  crashed or half-applied staging run leaves production's state untouched.
- **Production's state key doesn't move,** so there's no `terraform init -migrate-state` and no
  state surgery. The new data dir just re-inits against the same object.
- **Why a data dir per environment:** `.terraform/` caches which backend it was initialized
  against. With one shared dir, `init -backend-config=envs/staging…` would need `-reconfigure`, and
  forgetting it points a staging plan at production's state. Separate dirs make that
  mismatch impossible to reach, not just unlikely.
- **Same bucket, same credentials.** That separates the *state*, not the *permissions*. Phase 2.1's
  OIDC roles can scope a staging role to the `weather-story-bot/staging/*` prefix. Separate AWS
  accounts would be the strongest isolation, and they're out of scope for a single-user account.

### Why not Terragrunt

Terragrunt's strengths are generating backend config across many modules, ordering dependencies
between stacks (`run-all`), and keeping many environments × accounts × regions consistent. This
project has **one root module, two environments, one account and one region**. The environment
plumbing Terragrunt would replace is a `check-env` guard and two flags in the Makefile.

- **Cost:** a second binary for you and for Phase 2.1's CI, and a restructure into a module plus
  `live/<env>/terragrunt.hcl` (or a `source` pointing back at `infra/`). It also adds a layer
  between you and the plain `terraform plan` output that the gates depend on. And it wraps the
  exact thing this phase is meant to teach.
- **When to revisit:** splitting into several stacks with dependencies, such as an account-level
  stack for the budget and a per-environment bot stack, or moving to separate AWS accounts per
  environment. Offices don't trigger it: they're variables inside one module, not stacks, even at
  122.
- Getting there later is cheap. `envs/<env>.backend.hcl` and `<env>.tfvars` map one-to-one onto
  Terragrunt's `remote_state` and `inputs`.

## Working agreement

**Stop after every task:** `make lint` and `make test` pass, then it goes back for review and a
commit. **Three deploy gates.** You run `plan`/`deploy` (weather-deploy profile, MFA). Each
standard changes in the task that makes it true.

---

# Stage 1 — Production learns its name (a no-op for production)

## Task 1: Save spec documentation

Create the spec folder with `plan.md` (this plan), `shape.md`, `standards.md` (how each of
`global/principles`, `infra/alarms`, `infra/data-retention`, `infra/iam`,
`testing/log-contracts` and the two new standards applies) and `references.md` (`infra/*.tf`, `Makefile`, `infracost.yml`,
`scripts/infracost_usage.py`, the README's Deploy and Alerts sections, and the standards review's
"Environments" notes). No `visuals/`.

`agent-os/product/roadmap.md`: mark Phase 2.0 in progress with the spec name. Settle the open bot
question (separate staging bot) and record the namespace, budget and tfvars findings.

## Task 2: Thread the environment through Terraform

- `variables.tf`: `environment` (string, no default, `contains(["production", "staging"], ...)`).
  `telegram_token_param_name` default becomes `null`.
- `versions.tf` locals:
  `production = var.environment == "production"`,
  `name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"`,
  `telegram_token_param_name = coalesce(var.telegram_token_param_name, local.production ? "/weather-story-bot/telegram-token" : "/weather-story-bot/${var.environment}/telegram-token")`.
  Comment that production stays unsuffixed because a rename is a replace.
- `monitoring.tf`: `metric_namespace = local.production ? "WeatherStoryBot" : "WeatherStoryBot/${var.environment}"`.
  `aws_budgets_budget.monthly` gets `count = local.production ? 1 : 0`, with a comment that it
  covers the whole account.
- `storage.tf`: `aws_dynamodb_table.posted` gets `count = local.production ? 1 : 0` (it's
  production's rollback). `outputs.tf`: `mvp_table_name = one(aws_dynamodb_table.posted[*].name)`.
- `iam.tf`, `lambda.tf`: use `local.telegram_token_param_name`. Add a `lifecycle.precondition`
  on the function: outside production, the parameter must not be production's.
- `infracost.yml`: `environment: production` in the shared vars.
  `scripts/infracost_usage.py`: key the MVP table as `aws_dynamodb_table.posted[0]`.
- **New `agent-os/standards/infra/environments.md`** + an `index.yml` entry: production is
  unsuffixed and every other environment is `-<env>`; production-only resources and why;
  per-environment differences are variables or `local.production`, never forked files; each
  environment has its own Telegram bot, and a bot is never made an admin in another environment's
  channels; metric namespaces are per environment.
- Amend `infra/data-retention` (the `posted` row: production only; staging has the same
  protections) and `infra/iam` (the token parameter is per environment).
- Verify: `terraform validate` in a throwaway data dir (`init -backend=false`); `make cost`
  still reports $0.60 for one office.

## Task 3: Environment files and an ENV-driven Makefile

- `infra/envs/`: `production.backend.hcl.example` (the key stays
  `weather-story-bot/terraform.tfstate`), `staging.backend.hcl.example` (key
  `weather-story-bot/staging/terraform.tfstate`), `production.tfvars.example` (moved from
  `terraform.tfvars.example`) and `staging.tfvars.example` (MKX with a private chat id; no
  `environment`). The old examples go away.
- Local, gitignored files, which I move and don't commit: `infra/terraform.tfvars` →
  `infra/envs/production.tfvars`, `infra/backend.hcl` → `infra/envs/production.backend.hcl`.
  Delete `infra/.terraform/` once the new data dir is initialized, so a bare `terraform plan`
  can't find a configured backend.
- `.gitignore`: `infra/envs/*.backend.hcl` and `infra/.terraform-*/` replace `infra/backend.hcl`.
- `Makefile`: a `check-env` guard (`ENV` must be `production` or `staging`, otherwise exit 2
  with a hint). `plan` runs `init -input=false -backend-config=envs/$(ENV).backend.hcl`, then
  `plan -var environment=$(ENV) -var-file=envs/$(ENV).tfvars -out=deploy-$(ENV).tfplan`.
  `deploy` applies `deploy-$(ENV).tfplan` and deletes it. Both set
  `TF_DATA_DIR=.terraform-$(ENV)`. **Verify that this resolves inside `infra/` under `-chdir`.**
- `CLAUDE.md` Commands and the README's Deploy, setup, alert-tuning and add-an-office sections
  change in the same commit: `make plan ENV=production`, the `envs/` paths.
- `infra/environments` gains the Makefile section: one `ENV` selects the backend, var file, data
  dir and plan file together.

### Gate 1 — deploy production

You run `make plan ENV=production`. **Pass:** `0 to add, 0 to change, 0 to destroy`, plus
"has moved to" lines for `aws_budgets_budget.monthly[0]` and `aws_dynamodb_table.posted[0]`.
Run it against the zip already in `build/`: a rebuild shows a Lambda code update until Phase
2.1 makes the zip reproducible. Anything else, including any replace, is a stop. Then
`make deploy ENV=production`, and the next scheduled run logs `Run complete` normally.
**Rollback:** revert the commits. Removing `count` moves `[0]` back automatically.

---

# Stage 2 — Staging exists

## Task 4: Schedule toggle and monitoring that tolerates an idle staging

- `schedule_enabled` (nullable bool, `local.schedule_enabled = coalesce(var.schedule_enabled, local.production)`).
  `aws_scheduler_schedule.bot` gets `state = local.schedule_enabled ? "ENABLED" : "DISABLED"`.
- `missed_runs` and `quiet` get `count = local.schedule_enabled ? 1 : 0`, with a comment that
  both treat missing data as breaching and would sit in ALARM on an idle schedule.
- `outputs.tf`: add `region` for `make invoke-staging`.
- Amend `infra/alarms`: alarms that treat missing data as breaching exist only while the schedule
  is enabled; namespaces are per environment. README alarm table: add a note on the staging
  alarm set.
- **Production plan:** moves for `missed_runs[0]` and `quiet[0]` plus the new output. No
  resource changes. It's fine to deploy this with Gate 2.

## Task 5: Staging cost, and the `infra/budget` standard (before anything is created)

- `scripts/infracost_usage.py`: `Scenario` gains a runs figure (and an environment). Add a
  `staging` scenario: 1 office, about 60 hand invocations a month, posts scaled to match.
  `infracost.yml` gets a `staging` project with `environment: staging`. Test in
  `tests/test_infracost_usage.py`.
- **New `agent-os/standards/infra/budget.md`** + index: fixed monthly cost stays O(1) in offices;
  per-office visibility comes from queries, not metrics; prefer pay-per-use with no idle cost;
  every spec carries a `cost.md`; retention is a cost decision; the budget rises deliberately when
  a spec raises expected spend.
- `cost.md` in the spec folder from `make cost`. Expected: production unchanged ($0.60 at one
  office), staging about $0.30 at list price (three alarms, near-zero usage). The account then
  has 8 alarms, inside CloudWatch's 10 free, so the real cost is about $0. The $5 budget holds,
  with no change.

## Task 6: Stand up staging

- `Makefile`: `invoke-staging` reads `function_name` and `region` from staging's outputs,
  invokes synchronously with the weather-deploy profile, writes to `build/`, prints the summary,
  and exits non-zero on a `FunctionError`.
- README **Staging** section (you run it, once): create the bot in BotFather; create a private
  channel and make the staging bot its admin; find the chat id; `aws ssm put-parameter --type
  SecureString --name /weather-story-bot/staging/telegram-token`; copy the two staging examples;
  `make build`, `make plan ENV=staging`, `make deploy ENV=staging`; confirm the staging SNS
  subscription email; `make invoke-staging`.
- Amend `global/principles`: "use a deployed environment" becomes "use staging"
  (`infra/environments`). `infra/environments` records the rule: **staging is where real posts
  get watched.** Production becomes pipeline-only in Phase 2.1. Until then it's
  `make deploy ENV=production`, and the rule is written down ahead of being enforceable.

### Gate 2 — deploy staging

**Pass:** the staging plan creates only `-staging` resources (no budget, no `posted`, no
`missed-runs` or `quiet`, the schedule `DISABLED`). The first `make invoke-staging` posts MKX's
active stories to the private channel, and a second shows them all `skipped`. `aws cloudwatch
set-alarm-state` on `weather-story-bot-staging-errors` delivers an ALARM and an OK email. The
production plan shows no resource changes.
**Rollback:** staging is additive, so revert or leave it idle. Production is untouched.

---

## Verification (end to end)

- `make lint` and `make test` after every task. `terraform validate` in a scratch data dir for
  each environment's vars.
- `make plan` with no `ENV`, or `ENV=prod`, fails with the hint and touches nothing.
- State separation (readonly profile): after Gate 2 the state bucket holds both
  `weather-story-bot/terraform.tfstate` and `weather-story-bot/staging/terraform.tfstate`.
  `terraform state list` in each data dir shows only that environment's resources, and the
  production object's `LastModified` is unchanged by the staging deploy.
- Gate 1: production plan shows moves only, and it keeps posting after the deploy.
- Gate 2: a real post appears in the private channel, and nothing in the public one. A repeat
  invoke is `skipped`. The staging alarm email arrives with `staging` in its name.
- `make cost` shows the staging column. `aws cloudwatch describe-alarms` (readonly profile) lists
  5 production alarms and 3 staging ones.
