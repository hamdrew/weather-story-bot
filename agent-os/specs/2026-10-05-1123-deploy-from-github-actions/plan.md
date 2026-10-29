# Phase 2.1: Deploy from GitHub Actions

Spec folder: `agent-os/specs/2026-10-05-1123-deploy-from-github-actions/`

## Context

Production is still deployed by `make deploy ENV=production` from the laptop. Phase 2.0 wrote down
"production becomes pipeline-only" ahead of being enforceable. This phase makes it true before
Phase 2.2 migrates data or adds offices. Pull requests get lint, tests, Terraform tests, a
security scan and a plan for both environments. Merges to `main` apply staging automatically,
then production after your approval, with AWS access through GitHub OIDC (no long-lived keys)
and no Telegram credentials anywhere in CI. `make deploy` stays as a deliberate break-glass path.

### What shaping found beyond the roadmap

- **The repo is public.** Environment protection rules are free, but every Actions log is
  world-readable. A plan prints tfvars values, so `offices`, `alert_email` and
  `nws_user_agent` become `sensitive`. A saved plan holds those values in plain text, so it
  travels through a private S3 bucket and never as a GitHub artifact.
- **Dependabot can't mint OIDC tokens.** Its Terraform provider bumps get no PR plan, so the
  production plan you approve has to be made on `main`. That is what puts the saved plan and the
  approval between separate jobs.
- **Trivy's GitHub Action tags were hijacked in March 2026** (TeamPCP, CVE-2026-33634) and
  rewritten to steal CI secrets. Checkov is its own locked uv project (`tools/checkov/`), run the
  same way on the laptop and in CI, with no third-party action.
- **`ReadOnlyAccess` would leak the Telegram token.** It includes `ssm:GetParameter`, and the
  `aws/ssm` key lets any principal in the account decrypt. The plan roles get a hand-written
  read policy instead. Granting `s3:Get*` on the bucket ARN (not `bucket/*`) reads
  configuration without reading objects.
- **Production's names are a prefix of staging's.** `weather-story-bot*` matches
  `weather-story-bot-staging` too. The staging role scopes cleanly by prefix, and the
  production role has to use exact names. The state keys have the same shape
  (`weather-story-bot/terraform.tfstate` versus `weather-story-bot/staging/...`).
- **The apply roles must write tags** (`default_tags`), which `infra/iam` currently forbids for
  tag-conditioned roles. The amended rule allows tag writes only when both `aws:ResourceTag` and
  `aws:RequestTag` pin `Environment` to the role's own environment.
- **A shared boundary would let staging reach production.** A boundary covering
  `weather-story-bot*` plus a role policy the staging pipeline writes itself could grant the
  staging Lambda production's table. Each environment gets its own boundary.
- **Content-addressed zips make rollback a revert.** The key is the zip's sha256, so a
  docs-only merge plans as a no-op. Reverting a commit rebuilds byte-identical bytes, and the
  object at that key is either still there or uploaded again.
- **Dependabot has no mise ecosystem** (checked 2026-10-13 against GitHub's supported-ecosystems
  list). Renovate does read `mise.toml`, but it isn't adopted here. An exact tool pin would only
  ever move by hand, so `mise.toml` holds ranges. mise also has no `>=` syntax, so the Terraform
  range comes from tightening `required_version` to match it.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Scope | Roadmap core + Checkov + `terraform test` |
| CI roles | `ci-pr-plan` (PRs, read-only), `ci-plan` (`main` only, read + `plans/production/*` write), `ci-apply-staging`, `ci-apply-production` (each assumable only from its GitHub environment) |
| Bootstrap | `infra/bootstrap/`: its own state key and data dir, applied by hand with MFA. The pipeline can never widen its own permissions |
| Apply-role scope | Names + `Environment` tag conditions where supported + a per-environment permissions boundary required on every role it creates or changes. Explicit Deny on `DeleteTable`, `DeleteBucket`, `DeleteObject*`. Gaps written into `infra/iam` |
| Zips | `s3://<artifacts>/<env>/lambda/<sha256>.zip`. Each apply role writes only its own prefix. Writes must send `If-None-Match` (bucket policy), so an object is never overwritten |
| Saved plan | Production's plan goes to `s3://<artifacts>/plans/production/<run_id>.tfplan` (`ci-plan`) and is read by `ci-apply-production` |
| Public logs | `offices`, `alert_email`, `nws_user_agent` are `sensitive = true` |
| Scanner | Checkov in its own uv project, `tools/checkov/` (it pins `boto3` exactly, so it can't share the root lock), version in its `uv.lock`, bumped by Dependabot. Blocking. Inline `#checkov:skip=ID:reason`, and `make scan` fails on a skip with no reason |
| Staging / production | Staging applies on merge (main only, no reviewer). Production waits for your approval after staging succeeds |
| Break-glass | `make plan`/`make deploy` refuse `ENV=production` unless `BREAK_GLASS=1` is on the command line (or `GITHUB_ACTIONS=true`) |
| Locks | Plan roles plan with `-lock=false` (a stale saved plan is refused at apply anyway). Apply roles lock on their own exact `.tflock` key |
| Cloud runner | Declined, as the roadmap records |
| Task runner | mise tasks replace the `Makefile` (Task 8). Before Task 8, `make <target>` in this plan is history as written. From Task 8 on, the same target is `mise run <target>` |
| Tool versions | `mise.toml` holds the ranges for the laptop and every CI job: the major by default, the minor for a 0.x tool, and Terraform's from the stacks' `required_version`. A committed `mise.lock` (amended 2026-10-27, Task 9) records what they resolve to, for `linux-x64` and `macos-arm64`, so every job and the laptop install the same versions and CI installs `--locked`. Nothing bumps the lock: `mise upgrade` then `mise lock --platform linux-x64,macos-arm64`, by hand. CI installs through `jdx/mise-action`, not per-tool setup actions |

## Working agreement

**Stop after every task:** `make lint` and `make test` pass, then it goes back for review and a
commit. Each standard changes in the task that makes it true. You run anything that needs MFA
(`plan`/`deploy`, `bootstrap-*`), and GitHub settings. **Four gates**, each one deployable and
revertible.

---

# Stage 1: Honest builds, tests and scans (laptop deploy)

## Task 1: Save spec documentation

`plan.md` (this plan), `shape.md`, `standards.md` (`global/principles`, `infra/environments`,
`infra/iam`, `infra/budget`, `infra/data-retention`, plus the two new standards when written),
`references.md` (Phase 2.0 spec as the gate model, `Makefile`, `infra/*.tf`,
`scripts/set_run_state.py`, README Deploy/Staging). No `visuals/`.
`roadmap.md`: Phase 2.0 done, Phase 2.1 in progress with the spec name, and the decisions above
recorded where the roadmap left them open (scanner, `terraform test` approach, role depth).

## Task 2: Reproducible zip, build-first plans, sensitive values

- `scripts/build_zip.py` (stdlib only, run with `uv run --no-project`, so the credentialed CI
  jobs never execute third-party Python): sorted entries, fixed 1980-01-01 timestamps, fixed
  permissions, no directory entries, fixed deflate level. It prints the zip's base64 sha256.
  TDD: the same tree with different mtimes or a different walk order gives identical bytes.
- `Makefile`: `build` uses it. `plan` depends on `build` and passes
  `-var lambda_zip_sha256=<base64>`. `deploy` rebuilds, reads the planned value from
  `terraform show -json`, and **refuses if the rebuilt zip differs**. It also runs `init` so a
  fresh runner can apply a downloaded plan.
- `lambda.tf`: `source_code_hash = var.lambda_zip_sha256` (still `filename` until Stage 3).
- `variables.tf`: `offices`, `alert_email`, `nws_user_agent` get `sensitive = true`. Confirm in a
  plan that the Lambda environment shows only `OFFICES_JSON`/`NWS_USER_AGENT` as
  `(sensitive value)`.
- `infracost.yml`: placeholder `lambda_zip_sha256`. CLAUDE.md and README build notes.
- Verify: `make build` twice gives the same sha256.

## Task 3: `terraform test` for the main stack

- `infra/tests/*.tftest.hcl` with `mock_provider "aws"` and `override_data` for
  `aws_caller_identity`. Fully offline, no credentials (the laptop's `override.tf` profile is
  never configured under a mock).
- Mocked policy JSON is a placeholder, so **assert on the policy documents' inputs**
  (`data.aws_iam_policy_document.lambda.statement[*]`), not on `.json`. Move the provider's
  `default_tags` map into `local.default_tags` so the `Environment` tag can be asserted.
- Cases (Phase 2.0's console checks): names and metric namespaces per environment; the token
  parameter validation refusing another environment's path and the slash-less form
  (`expect_failures`); the production-only `count`s; the lowercase `Environment` tag; the
  `State`/`Archive`/`TelegramToken` tag conditions staying attached to exact ARNs; `Logs` having
  none.
- `make tftest`: `TF_DATA_DIR=.terraform-test terraform -chdir=infra init -backend=false` then
  `terraform test`. `lint`'s `terraform fmt -check` becomes `-recursive`.
- New standard **`testing/terraform-tests`** + index entry.

## Task 4: Checkov, blocking

- `make scan`: `uv run --locked --project tools/checkov checkov -d infra --framework terraform` (and `infra/bootstrap` once
  it exists), compact output, non-zero on any failure. A grep step fails on any
  `checkov:skip=ID` with no `:reason`.
- Triage today's findings in this task. Fix the ones that are free and safe. Skip the rest
  inline with a reason (expected: VPC, DLQ, X-Ray, code signing, CMK encryption, cross-region
  replication, 1-year log retention, which conflicts with the deliberate 30 days. SNS CMK breaks
  CloudWatch publishing with the AWS-managed key). Any fix that changes infra is listed for
  Gate 1.
- `testing/terraform-tests` gains the suppression rules. CLAUDE.md commands.

### Gate 1: deploy both environments from the laptop

`make plan ENV=staging` → `make deploy ENV=staging`, then production. **Pass:** each plan shows a
Lambda code update (the first reproducible zip has new bytes), the Checkov fixes listed in Task
4 (the multipart-abort lifecycle rule and the Lambda's reserved concurrency of 10, both in-place),
and nothing else. An immediate second `make plan` shows **No changes**, which proves the zip is
reproducible. The next production run logs `Run complete`.
**Rollback:** revert. The old zip simply plans as another code update.

**Passed 2026-10-08** (staging applied 9:17 PM CDT, production 9:20 PM CDT). Staging: 3 in-place
changes. Production: 4. Both second plans read **No changes**, and every rebuild from `rm -rf
build` printed the same `lLRsXkEy8eZ2kMPI928VVclO5y9jLQLq4Z4HtLBEvPE=`. Lambda's own `CodeSha256`
equals it in both environments, so the hash handed to Terraform is the one AWS computes for the
package. Reserved concurrency reads back as 10. Production's 9:30 PM CDT run, the first on the new
code, logged `Run complete` (MKX: skipped 1, nothing failed). Staging's schedule is `DISABLED`, so
it had no run to watch.
**Found at Gate 1:** the plan also updated two resources the criteria above didn't list, both
because `alert_email` became `sensitive`: `aws_sns_topic_subscription.alerts_email` (its
`endpoint`) and, in production only, `aws_budgets_budget.monthly[0]` (the `notification` blocks'
`subscriber_email_addresses`). In both the value is unchanged and only the sensitive marking is
new. For the budget the saved plan's JSON showed it: no differing keys, equal notifications,
`after_sensitive` true. A later gate's "nothing else" should count every resource that reads a
newly `sensitive` variable.

---

# Stage 2: Bootstrap (additive: nothing uses it yet)

## Task 5: Bootstrap stack, OIDC and the plan roles

- `infra/bootstrap/` with `backend.tf` (partial), `envs`-style gitignored `backend.hcl` + `.example`
  (key `weather-story-bot/bootstrap/terraform.tfstate`), its own `override.tf` (gitignored),
  data dir `.terraform-bootstrap`, `make bootstrap-plan` / `make bootstrap-deploy` (MFA, the same
  saved-plan pattern). Variables: `github_repository`, `state_bucket`, `region`.
- `aws_iam_openid_connect_provider.github` (`token.actions.githubusercontent.com`, audience
  `sts.amazonaws.com`). Trust policies use `StringEquals` on `aud` and an exact `sub`, never
  `StringLike`.
- Artifacts bucket `weather-story-bot-artifacts-<account>`: public access blocked, TLS-only, a
  Deny on `PutObject` when `s3:if-none-match` is Null (no overwrites), versioning with 7-day
  noncurrent expiry, `*/lambda/` expiring after 90 days and `plans/` after 14 (all derived and
  rebuildable data). Amend `infra/data-retention`: it's derived, so expiry is allowed.
- `ci-pr-plan` (sub `repo:<repo>:pull_request`) and `ci-plan` (sub `repo:<repo>:ref:refs/heads/main`)
  share one read policy: `Describe*`/`List*`/`Get*` per service on the project's ARNs only
  (bucket ARNs, never `bucket/*`, no `GetItem`/`Query`/`Scan`, no `ssm:GetParameter*`), plus
  `GetObject` on the two state keys. `ci-plan` adds `PutObject` on `plans/production/*`.
- `infra/bootstrap/tests/`: each role's trust (`aud`, exact `sub`), and that no read statement
  names an object, item or parameter.
- `.github/dependabot.yml` adds `/infra/bootstrap`. `infracost.yml` adds a bootstrap project.
  `cost.md` from `make cost`: production and staging unchanged, plus the bootstrap bucket (cents).
  GitHub Actions is free for public repos.

## Task 6: Apply roles and per-environment boundaries

- `for_each` over `staging` and `production`: `ci-apply-<env>` (sub
  `repo:<repo>:environment:<env>`) and `aws_iam_policy.boundary["<env>"]`, named
  `<env name>-boundary`, covering only what that environment's Lambda and Scheduler roles do.
- Apply policy per service. Staging uses `weather-story-bot-staging*` ARNs, production uses exact
  names. `aws:ResourceTag/Environment` goes on existing resources and `aws:RequestTag` +
  `aws:TagKeys` on creates, where each action supports them (Service Authorization Reference).
  Unsupported actions are listed in `infra/iam`. `iam:CreateRole`/`PutRolePolicy`/
  `AttachRolePolicy` require `iam:PermissionsBoundary` = the own environment's boundary, with no
  way to change or delete a boundary. `iam:PassRole` is scoped with `iam:PassedToService`. State:
  the environment's exact keys, plus its `.tflock`. Zips: `PutObject`/`GetObject` on
  `<env>/lambda/*`. Production also reads `plans/production/*`. The Lambda statement includes
  `lambda:PutFunctionConcurrency` (the function's reserved concurrency, Task 4) on the
  environment's own function. Explicit Deny on `DeleteTable`,
  `DeleteBucket` and `DeleteObject*` for the table and archive (`infra/data-retention`, now
  enforced by IAM).
- Tests: the staging role names no production ARN or state key, boundaries differ per
  environment, the Deny statements are present, and the trust is environment-exact.
- Amend `infra/iam`: CI roles, the scoped `Get*`/`List*`/`Describe*` read exception, the tag-write
  rule, boundaries, and the gap list.

### Gate 2: apply the bootstrap

First, with `readonly`: `aws iam list-open-id-connect-providers`. If a GitHub provider already
exists, import it rather than create a duplicate. Then, by hand in GitHub and **before the
apply** (a workflow naming a missing environment creates it unprotected): environments `staging`
(main only) and `production` (main only, required reviewer: you, self-review allowed), repo
variables `AWS_ACCOUNT_ID` and `TF_STATE_BUCKET`, and repo **secrets** `STAGING_TFVARS` and
`PRODUCTION_TFVARS` (the repo is public and Actions prints variables unmasked; README gets the
exact `gh` commands). Then `make bootstrap-plan` → `bootstrap-deploy` (MFA). **Pass:** only
bootstrap resources are created, and the production and staging plans still show No changes.
Spot checks with `aws iam simulate-principal-policy` (readonly): `ci-apply-staging` is denied
production's table, state key and token; `ci-apply-production` is allowed its own table; both
are denied `DeleteTable`, `UpdateContinuousBackups` and the archive's `PutLifecycleConfiguration`;
`ci-pr-plan` is denied `ssm:GetParameter` and `GetObject` on **both** environments' archives;
`ci-apply-staging` is allowed `iam:TagRole` on a staging role with only `aws:RequestTag` context
(a create, no `aws:ResourceTag`); `ci-apply-production` is allowed `cloudwatch:PutMetricAlarm` on
its errors alarm with only `aws:ResourceTag` context (an update).
Neither apply role can touch a CI role: `iam:PutRolePolicy`, `iam:UpdateAssumeRolePolicy` and
`iam:PassRole` on `role/weather-story-bot-ci-apply-staging` and `-production` are `implicitDeny` for
both, as is `iam:DeleteRolePermissionsBoundary` on a staging role.
**Rollback:** `terraform destroy` the bootstrap. Nothing depends on it.

**As built (Stage 2, 2026-10-09):** the roles are named `weather-story-bot-ci-<pr-plan|plan|apply-staging|apply-production>`
so `aws iam list-roles` groups them. The bootstrap's variables live in a gitignored
`infra/bootstrap/bootstrap.tfvars` (`.example` committed). An apply role's permissions came to
8.7 KB (staging) and 11 KB (production), over IAM's 10,240-character inline limit, so each apply role
holds three customer managed policies (`access`, `roles-tags`, `writes`) instead of one inline
policy. Per-service statements are merged into one statement per kind of access, which grants the
same access because an action only matches its own service's ARNs. The tag conditions on log
groups, SNS, CloudWatch alarms and S3 bucket actions, and the action name `s3:PutBucketABAC`, can't
be verified offline: Gate 4a (the first plan and apply under these roles) is where they are proven.

**Gate 2 passed (applied 2026-10-09 23:42 CDT):** no GitHub OIDC provider existed, so none was imported. The `staging` and
`production` environments (main only; production with you as reviewer, self-review allowed), the
two variables and the two `*_TFVARS` secrets existed before the apply. `bootstrap-deploy` added 29
resources, changed and destroyed none, and the production and staging plans both show No changes.
Every `simulate-principal-policy` spot check above came out as written: the CI roles and the
boundaries are `implicitDeny` for both apply roles, the retention Denies are `explicitDeny`, the
own-environment table and both tag-condition cases are `allowed`. The simulator reads the policies,
so it doesn't prove the services honor the tag conditions: that stays with Gate 4a.

---

# Stage 3: Code from S3, bounded workload roles (laptop deploy)

## Task 7: Lambda from the artifacts bucket

- `lambda.tf`: `s3_bucket = var.artifacts_bucket`,
  `s3_key = "${var.environment}/lambda/<base64url of the hash>.zip"`, and
  `source_code_hash = var.lambda_zip_sha256`. No local file in Terraform.
- Required variables (outside things, per `infra/environments`): `artifacts_bucket` and
  `permissions_boundary_arn`, the latter validated to end in `policy/${local.name}-boundary`.
  `aws_iam_role.lambda` and `.scheduler` get `permissions_boundary`.
- `Makefile deploy`: after the hash check, `aws s3api put-object --if-none-match '*'`. A 412 means
  it's already there, which is fine because the key is the content. Then apply. Locally it uses
  the `weather-deploy` profile, and in CI the environment's credentials.
- Tests: key derivation, boundary present on both roles. `infracost.yml` placeholders, tfvars
  examples, README.

### Gate 3: staging, then production, from the laptop

**Pass:** each plan shows the Lambda moving to S3 code and two in-place role updates (the
boundary) and the new `lambda_s3_key` output, nothing else. On staging, `make start ENV=staging` runs complete without
`AccessDenied` (a post, if MKX has a story, proves `PutObject` under the boundary), then
`make pause`. Production: `Run complete` on the next run, and the `errors` alarm quiet through the
next cold start (role credentials refresh then).
**Rollback:** revert. The boundary removal and `filename` code are in-place updates.

---

# Stage 4: The pipeline

## Task 8: mise for tool versions and tasks

- `mise.toml` at the repo root holds the tool versions as ranges, not exact pins. Dependabot
  can't bump `mise.toml`, so an exact pin would only ever move by hand:
  - `terraform = "1"`. mise has no `>=` syntax, so the stacks' constraint moves to meet it:
    `required_version` in `infra/versions.tf` and `infra/bootstrap/versions.tf` goes from
    `">= 1.11"` to `"~> 1.11"` (1.11 or later, below 2.0). `"1"` is that range's major, and
    `terraform init` refuses a version outside it, so a mismatch fails loudly instead of drifting.
    A comment beside each says the two move together.
  - `uv = "0.13"`. The default is the major, but uv is pre-1.0, where a minor release is the
    breaking boundary (`"0"` would accept all of them). So a 0.x tool takes its minor.
  - Nothing else. uv already provides Python (`requires-python`), and Checkov stays in
    `tools/checkov/uv.lock`.
  - `min_version` (hard) for the mise features the tasks use, and
    `[settings] minimum_release_age = "7d"`. A range installs whatever release is newest, in
    jobs that hold AWS credentials, so a release must be a week old before it's picked up.
    mise's default is 24h.
- Every `Makefile` target becomes a mise task of the same name, and the `Makefile` is deleted.
  Short tasks go in `[tasks]` in `mise.toml`. `plan`, `deploy`, `bootstrap-plan`,
  `bootstrap-deploy`, `start` and `pause` become file tasks in `mise-tasks/` (bash,
  `set -euo pipefail`). `check-env`/`check-plan` become hidden helper tasks. `ENV=<env>` becomes a
  required positional argument with `choices "staging" "production"` (`mise run plan staging`).
  `BREAK_GLASS=1` and `GITHUB_ACTIONS` stay environment variables.
- Behavior doesn't change. `plan` still builds first and passes the hash, `deploy` still refuses
  a different zip, uploads with `--if-none-match '*'`, applies exactly the saved plan and deletes
  it. Keep `mise.toml` free of `[env]` sourcing and hooks, so loading the config runs nothing.
- Docs: CLAUDE.md Commands, README, `.vscode/launch.json`, the standards that name a target
  (`index.yml`, `infra/environments`, `infra/alarms`, `infra/budget`, `infra/data-retention`,
  `infra/iam`, `backend/cli`, `global/launch-configs`, `testing/terraform-tests`), and the
  docstrings and messages in `scripts/*.py` and `tools/checkov/pyproject.toml`. The earlier
  tasks and gate records in this plan keep `make` as written.
- New standard **`global/tooling`**: `mise.toml` is the one source of tool versions for the
  laptop and CI, and every task is a mise task. Ranges, not pins (the major, the minor for 0.x,
  Terraform's from `required_version`). Why: Dependabot can't bump mise. A new tool means a
  `mise.toml` line, not a setup action. `mise upgrade` moves the laptop within the ranges.
- Verify: `mise run lint ::: test ::: tftest ::: scan` is green (`mise run a b` hands `b` to `a` as an
  argument; `:::` separates tasks). `mise run build` twice gives the same hash,
  and it equals the last `make build` hash from before the switch. `mise run plan staging` and
  `mise run plan production` both show **No changes**.

**As built (Task 8, 2026-10-13):** `mise.toml` plus `mise-tasks/{plan,deploy,check-plan,bootstrap-plan,bootstrap-deploy,start,pause}`; the `Makefile` is gone. `check-env` has no task: the `choices` on the environment argument refuse anything else, and an exported `ENV` can't reach a positional argument. `mise run build` twice gave `lLRsXkEy8eZ2kMPI928VVclO5y9jLQLq4Z4HtLBEvPE=`, the same as the last `make build`. `lint`, `test`, `tftest` and `scan` pass. Two things to know:
- **`:::` between tasks.** `mise run lint test` passes `test` to `lint` as an argument, so every multi-task line (Task 9's `checks` job too) uses `:::`.
- **`minimum_release_age = "7d"` hides uv 0.13.0** (released 2026-10-09) until about 2026-10-16, so `uv = "0.13"` doesn't resolve in a clean install before then. Locally it was verified with `MISE_MINIMUM_RELEASE_AGE=0d`. Don't run Gate 4a's CI before that date, or take uv's minor from the newest aged release (`0.12`) until it passes.
- `mise run plan staging` and `mise run plan production` both showed **No changes** (2026-10-27), with the same zip hash. `.github/workflows/pipeline.yml` (staged draft) still calls `make`; Task 9 rewrites it for mise.
- **Also in this commit, found at Gate 4a (2026-10-28): immutable OIDC subjects.** `infra/bootstrap` now accepts only immutable subjects (`repo:<owner>@<owner id>/<name>@<repository id>`, from `gh api repos/<owner>/<name>/actions/oidc/customization/sub --jq .sub_claim_prefix`): the `variables.tf` validation, `locals.tf`, `bootstrap.tfvars.example` and `tests/trust.tftest.hcl`, with the rule in `infra/iam`. The change was in the working tree before the Task 9 session and went into this commit without a review, and the plan never mentioned it. It was not applied either (that needs `bootstrap-deploy` and MFA), so the four deployed roles still trusted the name-only subjects until Gate 4a. Why: an immutable subject still matches after a rename, a repository recreated under the old name can't match, and this repository's tokens never carry the name-only form.

No gate of its own. Nothing in AWS changes (`required_version` is not a resource), and Gate 4a
proves the same tasks in CI.

## Task 9: Pull-request workflow

- `.github/workflows/pipeline.yml`, `permissions: contents: read` at the top. Actions are pinned
  by commit SHA (Dependabot already updates them).
- Every job installs its tools with `jdx/mise-action` (SHA-pinned) from `mise.toml`, the
  credentialed jobs included. There is no `setup-terraform`/`setup-uv` and no version in the
  workflow. The action's own mise version uses `minimum_release_age: 7d` rather than a pin, for
  the same reason as the tools.
- `checks` job (every event, **no `id-token`**): `mise run lint ::: test ::: tftest ::: scan`, and
  `mise run build` twice with the hashes compared.
- `plan` job (PRs from this repo, not Dependabot; matrix staging/production; `id-token: write`
  only here): writes `envs/<env>.backend.hcl` from variables and `.tfvars` from the `<ENV>_TFVARS` secret, then
  `mise run plan <env> --no-lock` with `ci-pr-plan`. It runs no project tests, so third-party
  code never shares a job with AWS credentials.
- `plan` task: a `--no-lock` flag → `-lock=false`.

**As built (Task 9, 2026-10-27):** `pipeline.yml` now has no `make`, no `setup-terraform`/`setup-uv` and no version in the file; both jobs use `jdx/mise-action` pinned at v5.2.1 (released 2026-10-19: the newer 5.2.2–5.2.4 were inside our own 7-day window). Things to know:
- **The action has its own `minimum_release_age`** (default 24h, for the mise binary itself), so both jobs set `7d` to match `mise.toml`. `plan` sets `cache: false` because it holds credentials. `checks` keeps the tool cache, keyed explicitly on `hashFiles('mise.toml', 'mise.lock')` (the action's default key may not cover those two file names; its docs list only the dotted ones), so a changed lock is a cache miss. The cache can't cause drift now: `--locked` installs the lock's exact version whatever the cache holds. uv's own package cache is gone with `setup-uv`: watch the `checks` time at Gate 4a, and add an `actions/cache` step for uv only if it hurts.
- **`mise.lock` (added the same day).** `mise lock --platform linux-x64,macos-arm64` recorded Terraform 1.16.6 and uv 0.13.4 with checksums for both platforms (Terraform's match HashiCorp's published `SHA256SUMS`; uv's carry a GitHub attestation verified at lock time), and `lockfile = true` keeps it current. mise-action adds `--locked` when the file exists. See `global/tooling`.
- **`:::` runs the tasks in parallel** (mise's `jobs` defaults to 8; `make` ran them in order), on the laptop too. Two cold-start runs (no `.venv`, no `.terraform-test`) passed with no lock contention. If Gate 4a flakes, `--jobs 1` on the `checks` command is the first thing to try.
- **No `mise trust` step:** the action exports `MISE_TRUSTED_CONFIG_PATHS` for the workspace.
- **`:::` is a YAML trap.** An unquoted `run: mise run lint ::: test` is a parse error (a colon followed by a space starts a mapping), so the `checks` command is in a `run: |` block. Found by parsing the file; `mise run lint-actions` (below) now lints it.
- **Terraform 1.17.0 becomes eligible at 2026-10-28 12:32 CDT** (released 2026-10-21) and the lock holds 1.16.6, so CI stays on 1.16.6 until someone upgrades the lock. That upgrade is its own deliberate change (`mise upgrade`, `mise lock --platform linux-x64,macos-arm64`, then the PR plans), not something Gate 4a absorbs by accident.
- **Workflow linting (2026-10-27).** `actionlint`, `zizmor` and `shellcheck` are locked mise tools; `mise run lint-actions` runs actionlint and zizmor and `lint` includes it. First run: one real nit fixed in `pipeline.yml` (`tr a-z A-Z` became character classes, SC2018/SC2019), otherwise clean. Both tools were shown to bite on a deliberately bad workflow (zizmor: `dangerous-triggers`, `template-injection`, `unpinned-uses`, `artipacked`; actionlint: SC2086 and a mistyped `github.evnt`).
  - **Checkov does not scan workflows, by decision.** It silently skips any workflow its bundled schema rejects (it reported 0 resources for `pipeline.yml` because of `cancel-in-progress: ${{ ... }}`), and zizmor covers its useful checks. `scan` stays Terraform-only (`testing/terraform-tests`).
  - **actionlint is given `.github/workflows/*.yml`** rather than finding workflows itself: with no `.git` root it checks nothing and exits 0. Name workflows `.yml`.
  - **CI.** `checks` has a separate step, `mise run lint-actions` with `GH_TOKEN: ${{ github.token }}`, which turns on zizmor's online audits (impostor commits, known-vulnerable actions); the `lint` step runs it again offline. `plan` installs only `terraform uv` (`install_args: --locked terraform uv`). Only Gate 4a shows these two working on a runner.
  - **`mise run lint-actions-online`** is the laptop version: the same checks with zizmor's online audits, token read from `gh auth token` per run (tested: it fails loudly when `gh` fails or prints nothing). `CLAUDE.md` tells agents to prefer it over `lint-actions`.
  - **zizmor's "(2 suppressed)" on `pipeline.yml`** is the two `secrets-outside-env` findings on the `TFVARS` line (`secrets.STAGING_TFVARS` and `secrets.PRODUCTION_TFVARS`). That audit belongs to the `auditor` persona, so the default `regular` persona hides them whatever the comment says, and `--no-ignores` changes nothing. Under `--persona=auditor` they surface: 2 medium findings, or "2 ignored" with the `# zizmor: ignore[secrets-outside-env]` comment on that line (the only ignore in the repo, no config file). They are not online-only: the auditor run was offline. The ignore is deliberate (secrets stay outside a GitHub environment because an environment would change the OIDC subject `ci-pr-plan` trusts), and it is inert until someone runs with the auditor persona.
  - **Gate 4a pre-check:** `mise run lint` is green before the PR is opened.

### Gate 4a: the PR for Task 9 shows its own plans

**Pass:** checks green, and both plan jobs end in **No changes**. That proves `ci-pr-plan`'s read
policy and that the CI-built zip matches the laptop's (if Linux and macOS bytes differ, record
it: the first pipeline apply will then show one code update). The CI log's Terraform and uv
versions equal `mise.lock`'s and the laptop's `mise ls` (the lock makes that so, so any
difference means the lock misses a platform: record it and re-lock). An `AccessDenied` is fixed in
`infra/bootstrap` and applied with MFA, then re-run.

**Gate 4a result (2026-10-28, PR #26): passed, with one recorded difference and one open item.** Three fixes were needed first, and each is worth remembering:
1. **Checkov crashed on Python 3.15.0** (`scan`). `tools/checkov` had `requires-python = ">=3.13"` and no pin, so a clean runner downloaded the newest CPython, and `beartype` imports `typing.no_type_check_decorator`, which 3.15 removed. The laptop's old 3.13 `.venv` hid it. Fixed with `tools/checkov/.python-version` (`3.13`, `0f02b9a`). mise also cancelled the other parallel tasks when `scan` failed, so that log under-reported (`mise run --continue-on-error` would show every failure; not added).
2. **`sts:AssumeRoleWithWebIdentity` denied.** The deployed trust policies still had the name-only subjects while GitHub issues the immutable ones (Task 8 note). `mise run bootstrap-plan` showed exactly four `sub` strings changing, and `bootstrap-deploy` applied them: 0 added, 4 changed, 0 destroyed. All four roles are fixed, not only `ci-pr-plan`, so Gate 4b's apply roles won't hit this.
3. **`Plan` failed on missing variables.** `STAGING_TFVARS` and `PRODUCTION_TFVARS` (set 2026-10-10) predated `artifacts_bucket` and `permissions_boundary_arn` (Task 7). Re-uploaded from the local tfvars with `gh secret set <NAME> < infra/envs/<env>.tfvars`. **A new required Terraform variable means refreshing both secrets**: say so in `infra/pipeline` (Task 10).

**Result.** `checks` green. Both plan jobs: `0 to add, 1 to change, 0 to destroy`, and the one change is the Lambda code: `s3_key` and `source_code_hash` go from the laptop's `lLRsXkEy…` to CI's `ItiiqOHJ…`. The CI zip differs from the laptop's, which the pass criterion allows: the first pipeline apply (Gate 4b) will show this one code update. Everything else held: Terraform 1.16.6 and uv 0.13.4 equal `mise.lock`; provider 6.68.0; the read policy, backend and refresh worked under `ci-pr-plan` in both environments; and the `cache_key` template, the online zizmor step and `install_args: --locked terraform uv` all worked.

**Also seen.** GitHub masks a multi-line secret line by line, so the tfvars' single-character lines print as `***` in plan logs (`tags = {***`). Harmless, but it makes them look odd.

**Open: the `checks` job's zip differs from the plan jobs'.** Same commit, lock and runner image, but `9n+rdGoR…` against `ItiiqOHJ…`. The two plan jobs agree with each other, and each build is stable within a job. It matters for Task 10, where `deploy-production` rebuilds in a different job from `plan-production`. `scripts/build_zip.py` fixes names, order, times and modes, and its docstring names one input it can't control: the `*.dist-info/RECORD` and `INSTALLER` files `uv pip install` writes. 

**Cause found and fixed (2026-10-28).** `uv pip install --target` writes console-script wrappers into `build/package/bin/` (`bin/httpx`, `bin/idna`). Their first line is `#!<path of the interpreter that ran the install>`, and each package's `RECORD` lists the script's SHA-256. That interpreter depends on where the build runs: the laptop's `.venv/bin/python` (a macOS path), the `checks` job's `.venv/bin/python` (a runner path: lint and test had created the venv), and the `plan` jobs' `/usr/bin/python` (CPython 3.12.3: no venv exists there, and `uv pip` used the system Python although `.python-version` says 3.13). So the zip's bytes depend on the host. The package is correct in all three, because `--python-version 3.13` and `--python-platform aarch64-manylinux2014` pick the wheels; only the shebangs and the matching `RECORD` lines differ, and Lambda never runs `bin/`. The `build_zip.py` docstring blamed `RECORD` drift between uv versions, which was the wrong input. **Fix:** `drop_console_scripts` in `scripts/build_zip.py` (called first by `main`) removes `bin/` and the `RECORD` lines for it, test-first in `tests/test_build_zip.py` (5 tests; the property is that the same package installed by two different interpreters zips to identical bytes). Nothing runs those scripts: the handler is a Python import and `httpx`'s CLI needs an extra we don't install. The zip has 194 members, down from 196, and no host path left in it. **The laptop's hash is now `o97k286EsovCe09skB1OFrtqvS01hw3XsBOc70Nf6Ks=`** (stable across builds). **Confirmed in CI (PR #26, commit `1824088`):** the laptop, `checks` (both builds) and both `plan` jobs all print `o97k286E…`, although the interpreters still differ (`.venv` 3.13.16 against `/usr/bin/python` 3.12.3). The plans still show 1 change per environment: the deployed Lambda has the old laptop-built `lLRsXkEy…`, so the only delta is `lLRsXkEy…` → `o97k286E…` (`s3_key`, `source_code_hash`), which Gate 4b's first apply performs; after that an unchanged build plans as No changes. The deployed code's hash changes once more, and Gate 4b's first apply is that update either way.

## Task 10: Main-branch deploys and pipeline-only production

- On push to `main`, with `concurrency: deploy` (never cancelled):
  `deploy-staging` (environment `staging`, `ci-apply-staging`: `mise run plan staging` +
  `mise run deploy staging`) → `plan-production` (`ci-plan`: plan printed to the log, `.tfplan`
  uploaded, key passed as a job output) → `deploy-production` (environment `production`, waits
  for your approval, `ci-apply-production`: download, `mise run deploy production`).
- `plan`/`deploy` tasks: `production` needs `BREAK_GLASS=1` in the environment unless
  `GITHUB_ACTIONS=true`.
- New standard **`infra/pipeline`**: roles and trusts, staging before production, saved plans
  in S3, `id-token` only in jobs that run no project code, a new AWS service means a bootstrap
  change applied first, rollback is a revert, and break-glass is used deliberately (including
  for a new table or archive: the apply roles' retention Deny blocks the PITR, versioning and
  lifecycle settings Terraform applies right after creating one, `infra/iam`). Amend
  `infra/environments` (pipeline-only is now enforced). README Deploy rewritten (pipeline,
  approval, rollback, break-glass). CLAUDE.md commands.
- **One-off auditor review of the deploy workflow.** Once the deploy jobs are written, run
  `zizmor --persona=auditor .github/workflows` by hand and read the findings. This is the first
  workflow that holds apply credentials, so it is worth the stricter persona's false positives
  once. It is a review, not a gate: the default `regular` persona stays in `lint-actions` (the
  auditor persona only adds findings we accept, such as `secrets-outside-env` on the repo-level
  tfvars secrets), and no `--persona` flag is added to the task.

**As built (Task 10, 2026-10-28):**
- **Workflow.** `pipeline.yml` gains `deploy-staging` → `plan-production` → `deploy-production` on push to `main` (all after `checks`). The apply jobs name their GitHub environment (the OIDC subject the apply roles trust); `plan-production` is repository-level under `ci-plan`. They install only locked `terraform` and `uv`, no cache, and run no tests or linters.
- **Concurrency.** Group `deploy` (never cancelled) is set on the three deploy jobs, not the workflow, so `checks` on `main` is never held up. A run whose `deploy-production` awaits approval still holds the group, so later pushes' deploys queue behind it until you approve or reject it. GitHub replaces a *pending* job with a newer one, which is safe because every deploy applies all of `main` and a stale plan is refused. 
- **Saved plan.** `mise run plan-store upload|download <key>` (hidden, Actions only) uses the AWS CLI with `If-None-Match: *`. The key is `plans/production/<run_id>-<run_attempt>.tfplan` (a deviation from `<run_id>`: the bucket never allows a second write to a key, so re-running `plan-production` would otherwise collide). Passed to `deploy-production` as the `plan_key` job output; the account id masking would have dropped a bucket-bearing output, so the bucket is read from the tfvars' `artifacts_bucket` instead of being passed.
- **No changes, no deploy (added after review).** `plan-changes` (hidden) prints `true`/`false` from the saved plan (`terraform show -json`: any resource action beyond no-op/read, `resource_drift`, `change.importing`, or an output change; drift and imports were added on request, so `start`/`pause` toggles show as drift and cost one approval on the next push). `deploy-staging` skips its Deploy step, `plan-production` skips saving the plan and outputs `changed`, and `deploy-production` has `if: ... needs.plan-production.outputs.changed == 'true'`, so with nothing to apply there is no approval to give. It fails closed: `plan-changes --github-output` writes the output only once it has `true` or `false` (a first version used `echo "changed=$(…)"`, which exits 0 whatever the command does; found in review). A pending `deploy-production` can be cancelled by a newer run's job in the same group; that run ends red with no approval asked, and the newer run's plan covers it. Terraform's own "No changes" and the Gate 4b pass criteria are unchanged for a run that does change something.
- **Plan summary (added after review).** `plan-summary` (hidden, Actions only) appends the saved plan to `$GITHUB_STEP_SUMMARY` after each plan step (PR `plan`, `deploy-staging`, `plan-production`), `continue-on-error`. No PR comment, by decision: that would need `pull-requests: write` and belongs in a separate uncredentialed job if wanted.
- **Shared setup.** `.github/actions/ci-setup` (local composite action: locked mise tools, `write-env-config`, OIDC credentials) is used by all four credentialed jobs, including Gate 4a's `plan` job; `lint-actions` now runs zizmor on `.github/actions` too. zizmor's `self-repository` hint (`$/...` for `./...`) is ignored inline because actionlint rejects `$/`.
- **`write-env-config`** (hidden, Actions only) writes the backend config and tfvars; it names which variable is missing and refuses a value with a quote or newline. `plan-store` reads the bucket the way Terraform would (last assignment wins, indentation allowed) and validates it. 30 tests in `tests/test_ci_tasks.py` run the tasks for real with fake `terraform` and `aws` on `PATH`. `deploy` now tests `GITHUB_ACTIONS == true`, as the guard does.
- **Break-glass.** `check-break-glass` (hidden), called first by `plan` and `deploy`; only `BREAK_GLASS=1` or `GITHUB_ACTIONS=true` pass for production. 8 tests in `tests/test_check_break_glass.py`, written first.
- **Docs.** New standard `infra/pipeline`; `infra/environments`, README Deploy, CLAUDE.md amended.
- **Auditor review.** `zizmor --persona=auditor` finds nothing new: 3 ignored, all `secrets-outside-env` on the repo-level tfvars secrets in the non-environment jobs (the two `plan` legs and `plan-production`). The environment jobs need no ignore.
- **Not proved offline:** the jobs themselves, `plan-store`'s S3 calls, and the environment approval. That is Gate 4b.

### Gate 4b: the first pipeline deploy

**Watch too:** a No-changes run (both deploys skipped, no approval); a changed run you approve; and a re-run of `deploy-production` after state moved (the stale-plan refusal). Zips are byte-checked within one runner only (`checks`); `deploy-production` rebuilds on another runner, and `deploy`'s hash check refuses a different zip after your approval, so a mismatch would show up there.

Merge Task 10. **Pass:** `deploy-staging` applies the one code update from Gate
4a, `plan-production` shows the same, you approve, and it applies. (A later run with No changes skips both deploys and asks for nothing.) `mise run deploy production`
without `BREAK_GLASS=1` refuses. Writes are proved by the next real change, which flows staging
→ production through the pipeline. Until then the break-glass path is ready.
**Rollback:** revert. The laptop path still works with `BREAK_GLASS=1`.

Then `roadmap.md`: Phase 2.1 done.

---

## Verification (end to end)

- `make lint test tftest scan` after every task (`mise run lint ::: test ::: tftest ::: scan` from Task 8 on). The build is
  byte-identical twice, and the same before and after the switch to mise.
- Gate 1: a second plan shows No changes. Gate 2: the simulator spot checks, and the main stacks
  unchanged. Gate 3: staging and production run under the boundary with no `AccessDenied`.
- Gate 4a/4b: PR plans are green and read-only (`ci-pr-plan` can't read the token or archive
  objects). The production apply happens only after approval, from a plan made on `main`.
- `aws iam list-roles` (readonly) shows the four CI roles. Each Lambda role carries its own
  environment's boundary.
