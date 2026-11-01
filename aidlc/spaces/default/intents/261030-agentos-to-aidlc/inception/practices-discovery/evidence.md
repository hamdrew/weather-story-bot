# Practices Discovery Evidence

Lead: `aidlc-pipeline-deploy-agent`, working alone (no support agents in this run, so there are no
contribution files). Brownfield, first run: `aidlc/spaces/default/memory/team.md` and `project.md`
were empty templates, so there was no affirmed baseline. The draft was read-only (no tests, builds,
deploys or AWS calls); the only command run against the code was `mise run coverage`, during the
interview (see Coverage measurement).

## Exclusions (blind discovery)

At the owner's request, practices were discovered from the repository alone and not inherited
from agent-os:

- Nothing under `agent-os/` or `.claude/commands/agent-os/` was read.
- The root `CLAUDE.md` "Standards" and "Skills" sections were not used. Its "Commands" and
  "Gotchas" sections were read as evidence of how tasks run.
- Code knowledge base statements, code comments and pull request bodies that cite an agent-os
  standard as the *reason* for a practice were not taken as that reason. Where the practice itself
  is visible in code, tooling or GitHub settings, the visible practice is recorded and the citation
  ignored (for example `mise.toml` line 1 cites `global/tooling`; the tool-version practice is
  read from the file itself).
- Pull request bodies name agent-os specs, tasks and gates. They were read only for what the team
  did (deployed the branch to staging, ran a review, watched for 24 hours), never for the spec
  process.

## Sources inspected

| Source | What it showed |
|---|---|
| `git log --all --graph` (HEAD `657c6f0`) | Linear `main` of squash commits with `(#N)`; one merge commit (#1); branch commits not on `main` |
| `git log --stat` on `src/ tests/ infra/ scripts/ mise-tasks/` | Tests and code land in the same commit in every behaviour change |
| `git branch -a -vv` | Branch names `phase-X.Y[-stage-N]`, `feat/...`, `docs/...`; Dependabot `dependabot/<eco>/...` |
| `gh pr list --state merged` (#1 to #31) | 31 PRs, 2026-09-14 to 2026-10-30 UTC; owner PRs mostly opened and merged the same day; Dependabot PRs wait up to 9 days |
| `gh api repos/hamdrew/weather-story-bot` | Squash and rebase allowed, merge commits off, squash title = PR title, delete branch on merge, public |
| `gh api .../rules/branches/main` | Ruleset: PR required (0 approvals), `checks` required, no force-push, no deletion, merge methods squash or rebase |
| Owner PR bodies #9 to #31 | Sections: summary, tests, review, gate / after merge; staging deployed from the branch before merge (#29); fresh-context review before merge (#27, #28, #31); 24-hour watch and "rollback is a revert" (#29, #30) |
| `.github/workflows/pipeline.yml` | `checks` on every PR and push to `main`; PR plans for both environments; `main` deploys staging, saves production's plan, applies after approval; deploy concurrency group; credentials only in jobs that run no tests |
| `.github/actions/ci-setup/action.yml` | (listed only) shared setup for credentialed jobs |
| `.github/CODEOWNERS` | `* @hamdrew`; code-owner review deliberately not required |
| `.github/dependabot.yml` | Weekly; uv (root, `tools/checkov`), terraform (`infra`, `infra/bootstrap`), github-actions; minor and patch grouped |
| `mise.toml`, `mise.lock` | Every task; tool ranges plus a lock; `minimum_release_age = 7d`; `lint`, `format`, `test`, `tftest`, `scan`, `coverage`, `build`, `lint-actions*` |
| `mise-tasks/deploy`, `check-break-glass` | Saved-plan apply, zip hash check, write-once upload; production refused off Actions without `BREAK_GLASS=1` |
| `pyproject.toml` | ruff rules and line length, pytest `addopts`, coverage config (branch, opt-in), boto3 dev-only |
| `tests/conftest.py`, test file list | Autouse fake credentials; real captured NWS fixtures; `make_story` builder; one test module per source module |
| `infra/tests/`, `infra/bootstrap/tests/` | Terraform tests (4 + 4 files) |
| Test and commit text search | One explicit "fixed test-first" (#27); "pinned" regression tests |
| `README.md` (deploy, break-glass, staging sections) | Pipeline flow, rollback by revert, laptop path for staging and emergencies, staging is where real posts are watched |
| Root `CLAUDE.md` Commands and Gotchas | Task usage, ask before live-infrastructure tasks, token in SSM, boto3 dev-only, record after Telegram accepts |
| `aidlc/spaces/default/codekb/weather-story-bot/code-structure.md` | Layout, one test module per source module, code patterns (injected clients, frozen dataclasses, one error type per client, bash task shape, Terraform environment pattern) |
| `aidlc/spaces/default/codekb/weather-story-bot/technology-stack.md` | Python 3.13 arm64, Terraform, mise, uv, ruff, ty, Checkov, actionlint, zizmor, SHA-pinned actions |
| `aidlc/spaces/default/codekb/weather-story-bot/dependencies.md` | httpx-only runtime, boto3 dev-only, separate Checkov project, out-of-band prerequisites (GitHub environments, secrets, MFA profile) |
| `aidlc/spaces/default/codekb/weather-story-bot/code-quality-assessment.md` | Test counts, offline suites, opt-in coverage with no floor, no `noqa` / `ty: ignore` / TODO; CI summary |
| `aidlc/spaces/default/codekb/weather-story-bot/architecture.md` | Deploy-from-main sequence, content-addressed zip, plan-then-apply exact saved plan, bootstrap by hand with MFA |
| `aidlc/spaces/default/codekb/weather-story-bot/business-overview.md` | Single owner and user; production deploys through the pipeline with approval; live since 2026-09-13 |

## Per-section inference

### Way of Working

- **Trunk-based, short-lived branches**: every change reaches `main` through a PR; owner branches
  live hours to about a day (#26 is the longest at about a day; #18's branch carried earlier spec
  commits). Inferred, high confidence.
- **Squash merge**: 30 of 31 PRs are single squash commits on `main` with `(#N)`; branch commits
  (`7ade2d5`, `251ca40`, `1496439`) fold into one (`71109c1`). Rebase is allowed by the ruleset but
  never used. Settled by evidence.
- **One revertible slice per PR**: PR titles map to one stage or task; each PR names its own
  deploy check and rollback. Inferred from PR bodies.
- **Pre-merge review**: fresh-context review recorded in #27, #28, #31; code review in #11.
  Observed; whether it is mandatory is not stated.
- **Commit title style**: Conventional Commits through #13, plain "Phase X Stage N: ..." from #19
  on. Resolved: plain-sentence titles (confirmed in the summary).

### Walking Skeleton

- MVP (#1) shipped the whole end-to-end path at once; later phases split into deployable stages,
  including a refactor-first stage (#8). Evidence shows incremental, end-to-end-deployable slices,
  but not a rule about building a thin slice first. Resolved at Q1.
- This intent's scope is `refactor`; the walking skeleton matters most for future feature work.

### Testing Posture

- Tests co-land with code in every behaviour change (squash hides order). One explicit
  test-first fix (#27). The draft's provisional `tdd` was replaced by `custom` at Q2.
- Offline suites, tooling and test types: settled by `mise.toml`, `pyproject.toml`, `conftest.py`.
- Coverage: opt-in, branch coverage, no floor in the repository today. Resolved at Q3: an 80% line
  floor, checked in CI by a separate step (later work).
- Live verification lives in deployment (staging check, post-deploy watch), not in an
  integration suite.

### Deployment

- Deploy on merge to staging; production after approval of the exact saved plan; no-op plans skip
  approval. Settled by `pipeline.yml` and README. This matches the framework default.
- Production pipeline-only, laptop break-glass: settled by `check-break-glass`.
- Pre-merge staging deploy from the branch: observed in #29 (and laptop staging gates before the
  pipeline existed: #11, #13). Resolved at Q4: only for risk that shows up only against live AWS.
- Post-deploy watch window and rollback-by-revert named per PR: observed (#29, #30).
- Topology: two environments in one region (us-east-2), separated by name suffix, tags and
  permissions boundaries; bootstrap stack by hand with MFA.

### Code Style

- Settled by tooling: `pyproject.toml` (ruff rules, line 100, py313), `ty`, `terraform fmt`,
  actionlint, zizmor, shellcheck, Checkov skip-reason check.
- Design conventions read from the code itself and the code knowledge base (`code-structure.md`),
  not from the standards the comments cite.
- No open point: the linters and the code agree.

## Interview decisions

The interview (`practices-discovery-questions.md`) asked only what the evidence could not settle.
The owner answered "Looks correct" to the Consolidated Summary Confirmation.

| Question | Answer | Effect on `team-practices.md` / `discovered-rules.md` |
|---|---|---|
| Settled by evidence (confirmed in the summary) | Not asked | One short-lived branch and PR per change, squash-merged into `main` behind `checks`, plain-sentence titles; staging on every merge, production only from the pipeline after the owner approves the saved plan (`BREAK_GLASS=1` for a laptop deploy); code style is what ruff, ty, terraform fmt, actionlint, zizmor and Checkov enforce |
| Q1 Thin end-to-end slice first? | **A**, the conductor's recommendation, chosen at the owner's request | Walking Skeleton: yes for new capabilities that add a new path through the system (a new scheduled job, a new output channel); no skeleton step for changes to paths that already work |
| Q2 Tests before or after the code? | **C** | Testing Posture: `Methodology: custom`; bug fixes test-first, new code test-after, in the same change |
| Q3 Coverage floor? | **B** | Testing Posture: 80% line-coverage floor, checked in CI by a separate coverage step; wiring that step into CI is later work; coverage stays out of pytest `addopts` |
| Q4 Staging before merge? | **B**, the conductor's recommendation, chosen at the owner's request | Deployment: deploy the branch to staging from the laptop before merge only when the risk shows up only against live AWS (IAM changes, data migrations, new resources); everything else is checked on staging after the on-merge deploy |
| Q5 Hard rules | **A** | All 16 rules in `discovered-rules.md` affirmed as written (8 Mandated, 8 Forbidden) |

The draft's open point on the post-deploy watch window was not asked separately; the observed
practice (each PR names a watch window and rollback) is kept as written and covered by the
summary confirmation.

## Coverage measurement

Run during the interview with `mise run coverage` at commit `657c6f0`: 296 tests passed; 99% total
branch coverage of `src/weather_story_bot/` (764 statements, 6 missed).

## Rule provenance

| Rule | Evidence |
|---|---|
| ALWAYS land on `main` through a PR whose `checks` passes | GitHub ruleset on `main` (`pull_request`, `required_status_checks: checks`) |
| ALWAYS deploy production through the pipeline (`BREAK_GLASS=1` off it) | `mise-tasks/check-break-glass`; `production` GitHub environment reviewer rule |
| ALWAYS keep the test suites offline | `tests/conftest.py` autouse `aws_env`; `mise.toml` `test` and `tftest` |
| ALWAYS give a Checkov skip or zizmor ignore an inline reason | `scan` task fails a skip with no reason; root `CLAUDE.md` Commands |
| ALWAYS pin a GitHub Action to a full commit SHA | every `uses:` in `pipeline.yml`; zizmor in `lint` |
| ALWAYS keep each environment's Telegram token in its own SSM parameter | root `CLAUDE.md` Gotchas; `infra/` reads it by name |
| ALWAYS record a story as posted only after Telegram accepts it | root `CLAUDE.md` Gotchas; record-after-send order in `handler.py` |
| ALWAYS ask before `deploy`, `start`, `pause`, `bootstrap-deploy` | root `CLAUDE.md` Commands (live infrastructure, MFA profile) |
| NEVER force-push to or delete `main` | ruleset `non_fast_forward`, `deletion` |
| NEVER put the Telegram token in Terraform variables or state | root `CLAUDE.md` Gotchas |
| NEVER add boto3 to runtime `dependencies` | `pyproject.toml` comment; root `CLAUDE.md` Gotchas |
| NEVER grant `id-token: write` to a job that runs tests or linters | `pipeline.yml` header and job permissions |
| NEVER apply the bootstrap stack from the pipeline | README; bootstrap IAM design (the pipeline cannot widen its own permissions) |
| NEVER upload a saved plan as a GitHub artifact | `pipeline.yml` header (sensitive values, public repository) |
| NEVER put `--cov` in pytest `addopts` | `pyproject.toml` comment; root `CLAUDE.md` Commands |
| NEVER silence a type error with `# ty: ignore` | root `CLAUDE.md` Commands |

## Remaining uncertainty

- **Coverage measure**: the affirmed floor is 80% *line* coverage, but `pyproject.toml` turns on
  branch coverage, so `mise run coverage` (and a `--cov-fail-under` check built on the same config)
  reports a combined statement-and-branch figure. That figure is the stricter of the two, so a
  check against it never lets line coverage fall below 80%; the CI step's design should say which
  measure it gates on. At 99% today, neither is close to the floor.
- **Coverage step is not yet in CI**: until the later work adds it, the floor is enforced only when
  someone runs `mise run coverage` (Build and Test does).
- **Bug fix versus new code**: the custom ordering depends on classifying a change; a change that
  mixes both follows test-first for the bug-fix part.
- Branch age is read from PR open and merge dates (UTC), not from first-commit dates.
- The pipeline deploy path is one day old (#27, 2026-10-29); its cadence is described from its
  design and README, with one observed run (#28 "Gate 4b passed").
- `.github/actions/ci-setup/action.yml` was listed but not read in full; nothing in these practices
  depends on its contents.
