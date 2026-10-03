# Phase 2.0: Staging and Production

Spec folder: `agent-os/specs/2026-09-26-2319-staging-and-production/`

## Context

Phase 1.2 made the CLI strictly read-only, so there is no longer any way to watch a real post
without deploying to production and posting to the public channel. Phase 2.0 adds a **staging**
deployment from the same `infra/`: MKX only, a private test channel, its own Telegram bot, the
schedule off, and started by hand. Phase 2.1's pipeline then has somewhere to apply before
production.

The hard constraint: **production must not be renamed.** Renaming the table or the bucket forces
a replace, and `infra/data-retention` forbids that. Production therefore stays unsuffixed and only
staging takes a `-staging` suffix. The Stage 1 gate is a production `make plan` that shows only
moves, tag-only in-place updates and one addition (the archive bucket's ABAC setting), checked
by a script rather than by eye. Nothing is destroyed or replaced.

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
- **An `Environment` tag after all (reversed after shaping).** Shaping first declined it: the
  `Project` default tag is already `local.name`, so Cost Explorer can split the environments
  without it, and a new tag puts an in-place update on every production resource, burying a
  zero-diff gate. You then chose to scope the Lambda role with tag conditions
  (`aws:ResourceTag/Environment`, Task 5), which need the tag. Gate 1 stays reviewable because a
  script, not your eye, checks that every change in the plan is a move, a tag-only update or the
  one allowed addition (Task 3). The archive bucket gets ABAC in Stage 1 as well, since S3 ignores
  bucket tags in conditions until it's on.
- **No Python changes.** Nothing in `src/` hard-codes a resource name. Only
  `scripts/infracost_usage.py` and its test change.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Separation | `infra/envs/<env>.backend.hcl` + `<env>.tfvars`, a `TF_DATA_DIR` per env, and the Makefile passes both from one `ENV` |
| Naming | Production unsuffixed (`weather-story-bot`); staging `weather-story-bot-staging` |
| `environment` var | No default, validated to `production`/`staging`, passed by the Makefile as `-var`, never kept in tfvars, so it can't disagree with the backend |
| `ENV` | Required by `plan`/`deploy`; no default |
| Telegram | A **separate staging bot**, token at `/weather-story-bot-staging/telegram-token`; staging's IAM can read only that parameter; `telegram_token_param_name` is required and validated to sit under `/${local.name}/` |
| Staging alarms | `errors`, `repost-loop` and `nws-ambiguous` on its own `-staging` SNS topic. `missed-runs` and `quiet` too: all five alarms exist, created with their actions off and toggled with the schedule |
| Staging data | The **same protections as production** (deletion protection, PITR, versioning). Reset staging by deleting items, not the table |
| Production-only | The account budget and the MVP `posted` table, via `count`; Terraform moves them to `[0]` automatically |
| Tags | `Environment = var.environment` (lowercase) on everything via `default_tags`, next to `Project = local.name`. **Reversed after shaping**, for the tag conditions |
| Tag conditions | The Lambda role's `State`, `TelegramToken` and `Archive` statements add `aws:ResourceTag/Environment` to their exact ARNs (Task 5); `Logs` doesn't. Everything a condition reads (tags, bucket ABAC, the hand-tagged token parameter) goes live a deploy before the condition |
| Bucket ABAC | `aws_s3_bucket_abac` on the archive, in Stage 1: the only addition in production's Gate 1 plan |
| Gate 1 check | A script reads the saved plan's JSON and fails on anything but a move, a tag-only update or the ABAC addition (Task 3) |
| Start/pause | `make start ENV=<env>` / `make pause ENV=<env>` toggle the schedule and the alarm actions through the API; Terraform creates both off and ignores them afterwards, in every environment |
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
commit. **Three deploy gates:** Gate 1 deploys production's tags, Gate 2 stands up staging and
Gate 3 gives production the tag conditions. You run `plan`/`deploy` (weather-deploy profile,
MFA). Each standard changes in the task that makes it true.

---

# Stage 1 — Production learns its name (moves, tags and bucket ABAC; no behaviour change)

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
  `telegram_token_param_name` becomes required (no default), validated with
  `startswith(var.telegram_token_param_name, "/${local.name}/")`: values that exist outside
  Terraform are variables, never hard-coded per environment. It goes in every tfvars file and
  `infracost.yml`.
- Split `versions.tf`: it keeps only `terraform {}`, the provider moves to `providers.tf`, and the
  locals and `aws_caller_identity` move to `locals.tf`. The environment locals in `locals.tf`:
  `production = var.environment == "production"`,
  `name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"`.
  Comment that production stays unsuffixed because a rename is a replace.
- `providers.tf`: `default_tags` gains `Environment = var.environment` beside `Project` and
  `ManagedBy`. The value is always lowercase, since IAM tag conditions compare case-sensitively.
  `aws_scheduler_schedule` takes no tags, which is fine.
- `storage.tf`: `aws_s3_bucket_abac.archive` with `abac_status { status = "Enabled" }`, commented:
  S3 evaluates bucket tags only once ABAC is on; after that, bucket tags are written through S3
  Control `TagResource`/`UntagResource`, which provider >= 6.23 uses only when the caller holds
  `s3:TagResource`, `s3:UntagResource` and `s3:ListTagsForResource` (otherwise it silently falls
  back to `PutBucketTagging`, which fails); it changes no access while no policy reads bucket tags;
  undo with `status = "Disabled"`.
- `monitoring.tf`: `metric_namespace = local.production ? "WeatherStoryBot" : "WeatherStoryBot/${var.environment}"`.
  `aws_budgets_budget.monthly` gets `count = local.production ? 1 : 0`, with a comment that it
  covers the whole account.
- `storage.tf`: `aws_dynamodb_table.posted` gets `count = local.production ? 1 : 0` (it's
  production's rollback). `outputs.tf`: `mvp_table_name = one(aws_dynamodb_table.posted[*].name)`.
- `infracost.yml`: `environment: production` in the shared vars.
  `scripts/infracost_usage.py`: key the MVP table as `aws_dynamodb_table.posted[0]`.
- **New `agent-os/standards/infra/environments.md`** + an `index.yml` entry: production is
  unsuffixed and every other environment is `-<env>`; production-only resources and why;
  per-environment differences are variables or `local.production`, never forked files; each
  environment has its own Telegram bot, and a bot is never made an admin in another environment's
  channels; metric namespaces are per environment; every resource carries the lowercase
  `Environment` tag through `default_tags`, hand-made things are tagged by hand, and every
  archive bucket has ABAC on.
- Amend `infra/data-retention` (the `posted` row: production only; staging has the same
  protections) and `infra/iam` (the token parameter is per environment). Bucket ABAC doesn't touch
  versioning, lifecycle or public access, so `infra/data-retention` doesn't mention it.
- README setup: `aws ssm put-parameter` gains `--tags Key=Environment,Value=production` (it can't
  be combined with `--overwrite`), plus `aws ssm add-tags-to-resource` for a parameter that
  already exists.
- Verify: `terraform validate` in a throwaway data dir (`init -backend=false`); `make cost`
  still reports $0.60 for one office (the ABAC resource has no cost).

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
- **A mechanical check of the Gate 1 plan** (a Makefile target, or a small `scripts/` tool the
  target calls, with a test in `tests/`). It reads `terraform show -json deploy-$(ENV).tfplan`
  (same `TF_DATA_DIR`) and fails, listing the offenders, if any resource change is anything other
  than:
  - `no-op`: unchanged, or a move (`previous_address` set)
  - `update` (moved or not) where the only attributes that differ between `before` and `after`,
    counting `after_unknown`, are `tags` and `tags_all`, and the only tag key that differs is
    `Environment`
  - `create` of `aws_s3_bucket_abac.archive`, at most once
  - `update` of an `aws_iam_role_policy` whose only change is `policy` becoming known after apply,
    because its one policy document is read at apply (`read_because_dependency_pending`), with
    statements that are known and identical to the live policy (Sid, Effect, Action and Resource
    only; anything else fails). **Found at Gate 1:** `data.aws_iam_policy_document.lambda` takes
    ARNs from the log group, table and bucket, so their tag updates defer its read and the plan
    shows `aws_iam_role_policy.lambda` as `policy = (known after apply)`. The policy that comes
    out is the live one; the check proves it rather than trusting an eye on the diff

  Anything else, a `delete`, a replace or any other create, fails. Data sources (`mode = "data"`)
  aren't resource changes and are skipped. The test runs it over small hand-written plan JSON
  fixtures: each allowed kind passes, and a replace, a non-tag attribute change, a second create and
  a changed `Project` tag each fail. It only reads a plan file, so it stays a read-only local tool.
  Eyeballing ~30 tag diffs is how a real change slips through.
- `CLAUDE.md` Commands and the README's Deploy, setup, alert-tuning and add-an-office sections
  change in the same commit: `make plan ENV=production`, the `envs/` paths.
- `infra/environments` gains the Makefile section: one `ENV` selects the backend, var file, data
  dir and plan file together.

### Gate 1 — deploy production

First, tag production's token parameter by hand. Nothing reads the tag yet; it has to be live
before Task 5's condition does:

```sh
aws ssm add-tags-to-resource --region us-east-2 --resource-type Parameter \
  --resource-id /weather-story-bot/telegram-token --tags Key=Environment,Value=production
```

You run `make plan ENV=production`, then the Task 3 plan check against it. **Pass:** the check
passes, and the summary is `1 to add, N to change, 0 to destroy`: the one addition is
`aws_s3_bucket_abac.archive`, the N changes are tag-only in-place updates adding
`Environment = "production"` plus `aws_iam_role_policy.lambda` with its deferred, unchanged policy
(the real plan: 1 to add, 15 to change), and there are "has moved to" lines for
`aws_budgets_budget.monthly[0]` and `aws_dynamodb_table.posted[0]`. Run it against the zip
already in `build/`: a rebuild shows a Lambda code update until Phase 2.1 makes the zip
reproducible. A failing check, a replace or a destroy is a stop. The bucket's tag update runs
before the ABAC addition (it depends on the bucket), and the weather-deploy profile holds the S3
Control tag actions either way. Then `make deploy ENV=production`, and the next scheduled run
logs `Run complete` normally.
**Rollback:** revert the commits. Removing `count` moves `[0]` back automatically, and removing
the tag is another tag-only update. The tag and bucket ABAC change no access on their own, so a
partial revert can keep them. To turn ABAC off, apply `status = "Disabled"` before removing the
resource (the provider docs don't say whether deleting it disables ABAC).

---

# Stage 2 — Staging exists

## Task 4: Created paused, toggled by `make start` / `make pause`

Revised 2026-10-02. This task first made `schedule_enabled` a variable and put `count` on
`missed_runs` and `quiet`. That gave staging a smaller alarm set and made the toggle a Terraform
variable. It was replaced by one rule for every environment: **everything is created paused, and a
script starts and pauses it.**

- No `schedule_enabled` variable or local. `aws_scheduler_schedule.bot` is created
  `state = "DISABLED"`, and every `aws_cloudwatch_metric_alarm` is created with
  `actions_enabled = false`. Both have `lifecycle { ignore_changes = [...] }` for that attribute,
  so no apply undoes a start or a pause. `lifecycle` can't be conditional, so this holds in
  production too: its existing schedule and alarms stay as they are, because the attributes are
  ignored, not changed.
- All five alarms exist in every environment, so `missed_runs` and `quiet` lose their `count`
  (production's plan shows nothing for them, since Task 4's `count` was never deployed there). A
  paused environment's two breaching alarms sit in ALARM without emailing, because their actions
  are off.
- `outputs.tf`: `region`, `schedule_name` and `alarm_names`.
- `scripts/set_run_state.py` (tested against moto): `start` enables the schedule, then the alarm
  actions; `pause` disables the alarm actions, then the schedule. It reads `terraform output -json`,
  sends the schedule's whole current definition back (`update-schedule` replaces it), is a dry run
  without `--apply`, and is idempotent. `make start ENV=<env>` and `make pause ENV=<env>` run it
  with `--apply`, through `check-env` and the environment's data dir.
- Amend `infra/alarms` and `infra/environments`; README alarm section.
- **Production plan:** the three new outputs and nothing else. It's fine to deploy this with
  Gate 3. Production's schedule and alarms are already on, and stay on.

## Task 5: Tag conditions on the Lambda role

- `iam.tf`: the `State` (DynamoDB), `TelegramToken` (SSM) and `Archive` (S3 `PutObject`)
  statements each gain an Allow condition, `StringEquals` on `aws:ResourceTag/Environment` =
  `[var.environment]`. The exact ARNs stay: the condition is added to the ARN, never used instead
  of it. Comment each on what it reads:
  - DynamoDB supports `aws:ResourceTag` on item actions, but only while the account's DynamoDB
    ABAC setting is on ("enabled by default for most accounts"). If it's off, conditions evaluate
    as if the table had no tags and the Allow fails closed. There's no CLI to read the setting
    (console Settings page only), so staging's first run proves it
  - SSM reads the parameter's own tags. The parameter is made by hand, so it's tagged by hand
    (Gate 1 for production, the README's Staging section for staging)
  - S3 `PutObject` on `bucket/*` reads the bucket's tags, which it honours only with bucket ABAC
    on (Task 2)
- `Logs` gets no condition. Whether `PutLogEvents` evaluates log-group tags is unverified, and the
  failure would be quiet: logs silently lost, and the metric-filter alarms with them.
- Amend `infra/iam` with the ABAC rules:
  - tag conditions are added to exact ARNs, never used instead of them
  - Allow + `StringEquals` only, so a missing tag fails closed; never an Allow with
    `StringNotEquals`
  - a role constrained by tag conditions never holds tag-write actions (`TagResource`,
    `ssm:AddTagsToResource` and the like), or it could retag its way into access
  - everything a condition reads (resource tags, bucket ABAC, hand-tagged parameters) goes live
    at least one deploy before the condition does
  - which statements carry conditions, and why `Logs` doesn't
- **Production plan:** one in-place update, `aws_iam_role_policy.lambda`. It deploys in Gate 3,
  after staging has proved the conditions.

## Task 6: Staging cost, and the `infra/budget` standard (before anything is created)

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

## Task 7: Stand up staging

- `Makefile`: `start` and `pause` (Task 4) take `ENV`, so staging's are `make start ENV=staging`
  and `make pause ENV=staging`. Nothing else is added here.
- README **Staging** section (you run it, once): create the bot in BotFather; create a private
  channel and make the staging bot its admin; find the chat id; `aws ssm put-parameter --type
  SecureString --name /weather-story-bot-staging/telegram-token --tags
  Key=Environment,Value=staging` (the tag is what Task 5's condition reads; `--tags` can't be
  combined with `--overwrite`); copy the two staging examples;
  `make build`, `make plan ENV=staging`, `make deploy ENV=staging`; confirm the staging SNS
  subscription email; `make start ENV=staging`.
- Amend `global/principles`: "use a deployed environment" becomes "use staging"
  (`infra/environments`). `infra/environments` records the rule: **staging is where real posts
  get watched.** Production becomes pipeline-only in Phase 2.1. Until then it's
  `make deploy ENV=production`, and the rule is written down ahead of being enforceable.

### Gate 2 — deploy staging

Staging is created with its tags, bucket ABAC, a hand-tagged token parameter and the tag
conditions all at once. That's safe only because nothing public depends on it, and its first run is
the proof production needs at Gate 3.

**Pass:** the staging plan creates only `-staging` resources (no budget, no `posted`, no
`missed-runs` or `quiet`, the schedule `DISABLED`). `make start ENV=staging` fires a run at once that posts MKX's
active stories to the private channel, and the next scheduled run (15 min) logs them all
`skipped`; then `make pause ENV=staging`. The first run
also proves the conditions in this account: the lease proves DynamoDB (and so the account's
DynamoDB ABAC setting), the token read proves SSM, and a posted story's archive write proves S3
bucket ABAC (if MKX has no active story, S3 stays unproved; wait for one before Gate 3). An
`AccessDenied` there is a stop for Gate 3. `aws cloudwatch set-alarm-state` on
`weather-story-bot-staging-errors` delivers an ALARM and an OK email. Production's plan shows
nothing beyond what Gate 3 lists.
**Rollback:** staging is additive, so revert or leave it idle. Production is untouched.

---

# Stage 3 — Production takes the tag conditions

### Gate 3 — deploy the conditions to production

Only after Gate 2 has proved DynamoDB, SSM and S3 in this account. Production's tags, bucket ABAC
and hand-tagged token parameter have been live since Gate 1, so nothing the conditions read is new.

**Pass:** the plan shows the new `region`, `schedule_name` and `alarm_names` outputs
and one in-place update, `aws_iam_role_policy.lambda` (Task 5's conditions). Nothing else. After
`make deploy ENV=production`, each condition is exercised at a different time:
- DynamoDB on every run (the lease), so the next scheduled run logging `Run complete` proves it
- SSM only at the next cold start. A policy change doesn't cold-start the Lambda, and the token
  is cached per cold start, so a warm environment keeps posting on the token it already read
- S3 `PutObject` only when a story is actually posted

The `errors` alarm covers all three, so production isn't fully proved until a cold start and a
post have both happened without it firing.
**Rollback:** revert the policy commit. The tags and bucket ABAC are harmless alone and stay.

---

## Verification (end to end)

- `make lint` and `make test` after every task. `terraform validate` in a scratch data dir for
  each environment's vars.
- `make plan` with no `ENV`, or `ENV=prod`, fails with the hint and touches nothing.
- State separation (readonly profile): after Gate 2 the state bucket holds both
  `weather-story-bot/terraform.tfstate` and `weather-story-bot/staging/terraform.tfstate`.
  `terraform state list` in each data dir shows only that environment's resources, and the
  production object's `LastModified` is unchanged by the staging deploy.
- Gate 1: the plan check passes on production's plan (moves, tag-only updates and the ABAC
  addition), and it keeps posting after the deploy.
- Gate 2: a real post appears in the private channel, and nothing in the public one. The next
  scheduled run is `skipped`. The staging alarm email arrives with `staging` in its name.
- Gate 3: production keeps posting under the tag conditions through a cold start and a post,
  with the `errors` alarm quiet.
- `make cost` shows the staging column. `aws cloudwatch describe-alarms` (readonly profile) lists
  5 production alarms and 3 staging ones.
