# Deploy from GitHub Actions — Shaping Notes

Shaped 2026-10-05. Roadmap Phase 2.1.

## Scope

Production stops being deployed from the laptop. Pull requests run lint, tests, `terraform test`,
a Checkov scan and a plan for both environments. Merges to `main` apply staging automatically,
then plan production, wait for the user's approval and apply it. AWS access comes from GitHub OIDC
roles defined in a separate bootstrap stack that only the user applies (MFA). CI never holds
Telegram credentials. `make deploy` survives as a deliberate break-glass path.

In scope, per the roadmap: the two fixes first (a reproducible zip; `plan`/`deploy` that can't
ship stale code), versioned zips in S3, tags and ABAC for the deploy roles, and both "idea" items
(a security scanner and `terraform test`). Out of scope: a cloud Terraform runner (declined in
the roadmap), separate AWS accounts, managing GitHub settings from Terraform.

## Decisions

### Shaped with the user

- **Both ideas come along:** Checkov and `terraform test`, each as a Makefile target that pull
  requests and the laptop run the same way.
- **Four CI roles.** `ci-pr-plan` (pull requests, strictly read-only), `ci-plan` (`main` only,
  read plus writing production's saved plan), and `ci-apply-staging` / `ci-apply-production`,
  each assumable only from its own GitHub environment.
- **A separate bootstrap stack** (`infra/bootstrap/`) holds the OIDC provider, the roles, their
  boundaries and the artifacts bucket. It has its own state key and is applied by hand with MFA,
  so the pipeline can never widen its own permissions. Defining the roles in the main stack
  would need IAM write on itself, which is privilege escalation by design.
- **Sensitive tfvars.** Actions logs are public on this repo, so `offices`, `alert_email` and
  `nws_user_agent` become `sensitive = true` and print as `(sensitive value)`.
- **Content-addressed zips.** The S3 key is the zip's sha256 under the environment's prefix,
  rather than the git SHA the roadmap first suggested. A docs-only merge plans as a no-op, and a
  rollback is a revert that rebuilds byte-identical bytes.
- **Saved plans travel through private S3.** Production's plan is made on `main` by `ci-plan`,
  uploaded to `plans/production/`, and read by `ci-apply-production` after approval. A GitHub
  artifact was declined because the plan file holds tfvars values in plain text and artifacts on
  a public repo can be downloaded by any signed-in user. Re-planning inside the apply job was
  declined because the approval would come before the plan being applied exists.
- **Apply roles: names, tags and a boundary.** Exact names for production and the `-staging`
  prefix for staging, `Environment` tag conditions wherever an action supports them, and a
  per-environment permissions boundary required on every role the pipeline creates or changes.
  The gaps (actions without tag support) are written down in `infra/iam`.
- **Checkov in its own uv project, blocking from day one.** It's locked in `tools/checkov/uv.lock` (a separate
  project because it pins `boto3` exactly) and bumped by Dependabot, needs no third-party action, and
  every suppression is an inline `checkov:skip=ID:reason`. `make scan` fails on a skip with no
  reason. Today's findings are triaged in the task that adds the scan.
- **Staging applies automatically, production waits for approval.** Staging deploys only from
  `main` and needs no reviewer. Production's environment requires the user's review
  (self-review allowed) and runs after staging succeeds.
- **Break-glass is enforced.** `make plan` and `make deploy` refuse `ENV=production` unless
  `BREAK_GLASS=1` is on the command line (CI is let through by `GITHUB_ACTIONS=true`). It's
  friction, not security: the MFA admin can still do anything.
- **Gated in four stages,** like Phases 1.2 and 2.0: local fixes deployed from the laptop,
  bootstrap (additive), Lambda code from S3 plus the workload boundary (laptop), then the
  pipeline itself.

### Found while shaping

- **Dependabot can't mint OIDC tokens** (GitHub withholds `id-token` from Dependabot-triggered
  runs). Its provider bumps never get a PR plan, so the production plan the user approves has to
  be made on `main`. That's what puts the saved plan and the approval between separate jobs.
- **Trivy's action tags were hijacked in March 2026** (TeamPCP, CVE-2026-33634): 75 of 76
  `trivy-action` tags and every `setup-trivy` tag were force-pushed to credential stealers.
  A scanner running in a job near AWS credentials should come from a pinned package, not a
  mutable action tag. Every action in the workflow is pinned by commit SHA regardless.
- **`ReadOnlyAccess` would leak the Telegram token.** It includes `ssm:GetParameter`, and the
  `aws/ssm` key's policy lets any principal in the account decrypt through SSM. It also reads
  archive objects and table items. The plan roles get a hand-written read policy:
  `Get*`/`List*`/`Describe*` per service on the project's ARNs. Granting `s3:Get*` on a bucket ARN
  (not `bucket/*`) reads configuration without reading objects.
- **Production's names are a prefix of staging's.** `weather-story-bot*` also matches
  `weather-story-bot-staging`, and the state key `weather-story-bot/` contains staging's and
  bootstrap's. The staging role scopes cleanly by prefix, and the production role has to use exact
  names and keys. The direction that matters most (staging can't touch production) is the easy one.
- **Apply roles must write tags,** because `default_tags` puts them on everything, but
  `infra/iam` forbids tag-write actions on tag-conditioned roles. The amendment: a deploy role may
  hold tag writes only when `aws:ResourceTag/Environment` and `aws:RequestTag/Environment` both
  pin its own environment, so it can't retag its way into another environment.
- **A shared boundary would let staging reach production.** With one boundary covering
  `weather-story-bot*`, the staging pipeline could write its Lambda role a policy granting
  production's table. Each environment gets its own boundary, limited to its own ARNs.
- **IAM can enforce `infra/data-retention`.** An explicit Deny on `DeleteTable`, `DeleteBucket`
  and `DeleteObject*` means even a plan that tries to destroy the table or archive fails at apply.
- **S3 can refuse overwrites.** A bucket policy that denies `PutObject` when `s3:if-none-match`
  is Null forces conditional writes, so a content-addressed zip is never silently replaced. The
  zip is far below the multipart threshold, so the multipart exemption doesn't come up.
- **Plans don't need a lock.** A saved plan records the state serial, and Terraform refuses to
  apply it once state has changed. So the plan roles plan with `-lock=false` and never write a
  lock object, and only the apply roles lock, each on its own exact `.tflock` key.
- **`terraform test` without credentials.** The real provider would need credentials, or skip
  flags in `providers.tf`, and the laptop's `override.tf` pins an MFA profile. A
  `mock_provider` needs neither, but makes `aws_iam_policy_document.json` a placeholder, so the
  tests assert on the documents' inputs (statements, conditions, resources) instead. Test
  assertions can reference locals, so `default_tags` moves into a local to make the
  `Environment` tag testable.
- **Credentialed jobs run no third-party Python.** The zip script is stdlib-only and runs with
  `uv run --no-project`, and the `plan`/`apply` jobs don't run the test suite. So a compromised
  dev dependency never shares a job with an `id-token`.
- **The provider lock file already carries `zh:` hashes for every platform,** so Linux runners
  can `init` against the committed lock file without regenerating it.

## Context

- **Visuals:** None.
- **References:** See `references.md`: the Phase 2.0 spec (the gate model), the `Makefile`,
  `infra/*.tf`, `scripts/set_run_state.py`, and the README's Deploy and Staging sections.
- **Product alignment:** Roadmap Phase 2.1, executed with the open questions settled (scanner,
  `terraform test` approach, how far to scope the deploy roles) and the zip key changed from git
  SHA to content hash. It enforces Phase 2.0's "staging is where real posts get watched;
  production is pipeline-only". Cost stays O(1) (`infra/budget`): IAM and OIDC are free, Actions
  is free on a public repo, and the artifacts bucket costs cents.

## Standards Applied

New with this spec:

- `testing/terraform-tests` (Tasks 3 and 4) — offline `terraform test` with a mock provider,
  assertions on policy inputs, `expect_failures` for validations, every trust policy and boundary
  tested, and Checkov suppressions with reasons
- `infra/pipeline` (Task 9) — the CI roles and their trusts, staging before production, saved
  plans in S3, `id-token` only in jobs that run no project code, a bootstrap change before a new
  AWS service, rollback by revert, and break-glass used deliberately

Amended by this spec:

- `infra/iam` (Tasks 5 and 6) — CI roles, the scoped read exception, the deploy-role tag-write
  rule, per-environment boundaries, and the list of actions without tag support
- `infra/environments` (Tasks 2, 7 and 9) — sensitive tfvars, artifacts bucket and boundary as
  required variables, production pipeline-only now enforced
- `infra/data-retention` (Task 5) — the artifacts bucket is derived data, so its expiry is allowed

Constraining but unchanged:

- `global/principles` — local tools stay read-only: `make plan` and `make deploy` are existing
  deploy tools, and the zip script only writes `build/`
- `infra/budget` — `cost.md` from `make cost`, with a bootstrap project
