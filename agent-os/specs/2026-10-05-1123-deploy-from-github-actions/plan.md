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
boundary), nothing else. On staging, `make start ENV=staging` runs complete without
`AccessDenied` (a post, if MKX has a story, proves `PutObject` under the boundary), then
`make pause`. Production: `Run complete` on the next run, and the `errors` alarm quiet through the
next cold start (role credentials refresh then).
**Rollback:** revert. The boundary removal and `filename` code are in-place updates.

---

# Stage 4: The pipeline

## Task 8: Pull-request workflow

- `.github/workflows/pipeline.yml`, `permissions: contents: read` at the top. Actions are pinned
  by commit SHA (Dependabot already updates them). Terraform and uv versions are pinned.
- `checks` job (every event, **no `id-token`**): `make lint test tftest scan`, and `make build`
  twice with the hashes compared.
- `plan` job (PRs from this repo, not Dependabot; matrix staging/production; `id-token: write`
  only here): writes `envs/<env>.backend.hcl` from variables and `.tfvars` from the `<ENV>_TFVARS` secret, then
  `make plan ENV=<env> LOCK=false` with `ci-pr-plan`. It runs no project tests, so third-party
  code never shares a job with AWS credentials.
- `Makefile`: `LOCK ?= true` → `-lock=$(LOCK)`.

### Gate 4a: the PR for Task 8 shows its own plans

**Pass:** checks green, and both plan jobs end in **No changes**. That proves `ci-pr-plan`'s read
policy and that the CI-built zip matches the laptop's (if Linux and macOS bytes differ, record
it: the first pipeline apply will then show one code update). An `AccessDenied` is fixed in
`infra/bootstrap` and applied with MFA, then re-run.

## Task 9: Main-branch deploys and pipeline-only production

- On push to `main`, with `concurrency: deploy` (never cancelled):
  `deploy-staging` (environment `staging`, `ci-apply-staging`: `make plan` + `make deploy`) →
  `plan-production` (`ci-plan`: plan printed to the log, `.tfplan` uploaded, key passed as a job
  output) → `deploy-production` (environment `production`, waits for your approval,
  `ci-apply-production`: download, `make deploy ENV=production`).
- `Makefile`: `ENV=production` needs `BREAK_GLASS=1` on the command line unless
  `GITHUB_ACTIONS=true`.
- New standard **`infra/pipeline`**: roles and trusts, staging before production, saved plans
  in S3, `id-token` only in jobs that run no project code, a new AWS service means a bootstrap
  change applied first, rollback is a revert, and break-glass is used deliberately (including
  for a new table or archive: the apply roles' retention Deny blocks the PITR, versioning and
  lifecycle settings Terraform applies right after creating one, `infra/iam`). Amend
  `infra/environments` (pipeline-only is now enforced). README Deploy rewritten (pipeline,
  approval, rollback, break-glass). CLAUDE.md commands.

### Gate 4b: the first pipeline deploy

Merge Task 9. **Pass:** `deploy-staging` applies (No changes, or the one code update from Gate
4a), `plan-production` shows the same, you approve, and it applies. `make deploy ENV=production`
without `BREAK_GLASS=1` refuses. Writes are proved by the next real change, which flows staging
→ production through the pipeline. Until then the break-glass path is ready.
**Rollback:** revert. The laptop path still works with `BREAK_GLASS=1`.

Then `roadmap.md`: Phase 2.1 done.

---

## Verification (end to end)

- `make lint test tftest scan` after every task. `make build` is byte-identical twice.
- Gate 1: a second plan shows No changes. Gate 2: the simulator spot checks, and the main stacks
  unchanged. Gate 3: staging and production run under the boundary with no `AccessDenied`.
- Gate 4a/4b: PR plans are green and read-only (`ci-pr-plan` can't read the token or archive
  objects). The production apply happens only after approval, from a plan made on `main`.
- `aws iam list-roles` (readonly) shows the four CI roles. Each Lambda role carries its own
  environment's boundary.
