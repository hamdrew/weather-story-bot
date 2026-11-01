# Team-Level Rules

> This team's affirmed practices and corrections. Loaded after `org.md` as
> strict-additive guidance; contradictions with broader policy are rejected.
> Populated by the practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

We work trunk-based on `main` through short-lived branches and pull requests. One owner
(`@hamdrew`, CODEOWNERS) writes the code; Dependabot opens the rest of the pull requests.

- **Branches**: one short-lived branch and one pull request per change, named for the slice of work
  (for example `phase-2.2-stage-2`). Most branches are opened and merged within a day; head
  branches are deleted on merge.
- **Merge style**: squash. Each pull request lands on `main` as one commit titled with the pull
  request title and `(#N)`; review-fix commits stay on the branch and fold into the squash. Merge
  commits are off.
- **Titles**: a plain sentence naming the slice (`Phase 2.2 Stage 1: record each post and its
  ledger event in one transaction`). Dependabot keeps its own `build(deps):` titles.
- **Protection on `main`**: changes arrive only through a pull request whose `checks` job passes;
  force-pushes and deletion are blocked. No approving review is required (a sole owner cannot
  approve their own pull request).
- **Pull request size**: one revertible slice of work per pull request, deployed and watched before
  the next slice builds on it. The pull request body records what changed, how it was tested, the
  review result, and what to check after merge.
- **Review**: before merge, a fresh-context code review runs and its findings are fixed or
  explicitly deferred in the pull request body.
- **AI-DLC Bolts**: base `main`, target `main`, squash merge, one pull request per Bolt.

## Walking Skeleton

We build a thin end-to-end slice first for new capabilities that add a new path through the system
(for example a new scheduled job or a new output channel): the slice runs the whole way through and
is deployed before the real features go in. Changes to paths that already work get no skeleton
step; they are delivered slice by slice.

## Testing Posture

- **Methodology**: custom
- **Methodology evidence**: Affirmed at the interview (Q2): test-first for bug fixes, test-after
  for new code. The history cannot show the order (tests land in the same squashed commit as the
  code in every behaviour change); its one explicit signal is a review finding "fixed test-first"
  in #27, which fits the bug-fix half of the rule.
- **Ordering**: Bug fixes start with a failing test that reproduces the bug, then the fix; new code
  is written first, then its tests, in the same change.
- **Coverage floor**: 80% line coverage, checked in CI by a separate coverage step. That CI step is
  later work and not part of the current change; until it exists, the floor is checked with
  `mise run coverage`. At affirmation the suite measured 99% branch coverage of
  `src/weather_story_bot/` (296 tests).
- **Coverage stays opt-in locally**: `--cov` is never in pytest `addopts`, because it breaks
  debugger breakpoints; coverage runs through its own task or CI step.
- **Offline suites**: every suite runs without network or credentials. respx mocks HTTP, moto mocks
  AWS, an autouse fixture replaces any real AWS or Telegram credentials, and Terraform tests use
  `mock_provider "aws"` with `-backend=false`.
- **Test types**: Python unit and component tests in `tests/` (pytest), one test module per source
  module (`tests/test_<module>.py`), plus tests that run the bash tasks for real with fake
  `terraform` and `aws` on `PATH`; Terraform tests in `infra/tests/` and `infra/bootstrap/tests/`.
  There is no live integration suite: live behaviour is checked on staging (see Deployment).
- **Test data**: real captured NWS listings in `tests/fixtures/`, loaded through `office_payload` /
  `office_stories`, plus the `make_story(**overrides)` builder.
- **Tooling**: `mise run test` (pytest, `-ra --strict-markers`), `mise run tftest`,
  `mise run coverage` (pytest-cov, branch coverage, terminal and HTML report).
- **CI**: the `checks` job runs `lint`, `test`, `tftest` and `scan` on every pull request and every
  push to `main`, and must pass before merge.

## Guard Policy

<!-- Affirmed by the team. Mode: strict, relaxed, or off. Strict here holds for every intent, whatever one person asks in chat; relaxed or off here applies to every intent whose policy came from its scope, unless project.md or the person sets another; changing this line changes it. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

- **Environments**: two, `staging` and `production`, from one Terraform root (`infra/`) with a
  per-environment backend, tfvars and data dir; staging resources carry a `-staging` suffix and
  their own bot, channel, table, bucket, alarms and permissions boundary. The bootstrap stack
  (`infra/bootstrap/`: OIDC provider, CI roles, boundaries, artifacts bucket) is applied by hand
  with MFA, never by the pipeline.
- **Cadence**: deploy on merge. Every merge to `main` deploys staging automatically, then saves
  production's plan and applies exactly that plan after the owner approves it in the `production`
  GitHub environment. A plan with no changes deploys nothing and asks for no approval. Deploys run
  one at a time.
- **Production is pipeline-only**: `mise run plan|deploy production` refuses off GitHub Actions
  unless `BREAK_GLASS=1` is on the command line.
- **Staging before merge**: only when the risk shows up only against live AWS (IAM changes, data
  migrations, new resources), the branch is deployed to staging from the laptop and checked before
  merging. Everything else merges, is checked on staging after the on-merge deploy, and goes to
  production with the owner's approval.
- **Watch after deploy**: each pull request names what to watch after merge, with a window (for
  example 24 hours on errors, repost loops and the run records' failed counts) and the rollback.
- **Artifacts**: a reproducible, content-addressed Lambda zip (`build/lambda.zip`, key
  `<env>/lambda/<base64url sha256>.zip`), uploaded write-once (`If-None-Match: *`); CI builds it
  twice and fails if the bytes differ, and `deploy` refuses a zip that is not the planned one.
- **Rollback**: revert the commit and let the pipeline redeploy; the same source rebuilds the same
  bytes at the same key. A bootstrap change rolls back with a revert plus `bootstrap-deploy`. Data
  has a 35-day undo window (DynamoDB point-in-time recovery, S3 noncurrent versions).
- **Live-environment operations**: `deploy`, `start`, `pause` and `bootstrap-deploy` change live
  infrastructure and need the MFA profile; the owner runs them, and an agent asks first.

## Code Style

Code style is what the tooling enforces; `mise run lint` is the gate CI runs and
`mise run format` applies the formatters.

- **Python**: 3.13; ruff lint with `E, F, W, I, B, UP, SIM, RUF`, line length 100,
  `target-version = py313`; `ruff format`; `ty check` must pass, and type errors are fixed rather
  than silenced.
- **Terraform**: `terraform fmt -recursive`; environment differences go through variables and
  `local.production`, never forked files; every `#checkov:skip=<ID>:<reason>` carries a reason
  (the scan fails otherwise).
- **Workflows**: actionlint (with shellcheck) and zizmor in `lint`; actions pinned to a full commit
  SHA with the version in a comment; `persist-credentials: false`; an accepted zizmor finding is an
  inline `# zizmor: ignore[<audit>] <reason>`, never a config file.
- **Bash tasks**: `mise-tasks/` file tasks with `#MISE` / `#USAGE` headers and
  `set -euo pipefail`; every task runs through mise (`mise run lint ::: test`).
- **Python design conventions**: frozen, slotted dataclasses for values; clients injected by the
  caller (boto3 types imported under `TYPE_CHECKING`); one public error type per client with a
  single catch-all boundary in the handler; a pure planner with side effects only in the handler;
  structured logs with a fixed message and `extra`.
- **Comments**: explain why, not what; no TODO or FIXME markers in the tree.
- **Naming**: idiomatic snake_case for Python; tests named `test_<behaviour>`; one test module per
  source module.
## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
