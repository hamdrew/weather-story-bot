# Code Quality Assessment

## Quick Ratings

| Dimension | Rating | Evidence |
|---|---|---|
| Naming clarity | good | descriptive snake_case names; tests named `test_<behaviour>` |
| Function size | fair | most functions short; `handler.py` is 420 lines and `_apply_post_or_update` is long |
| Error handling | good | one error type per client, no swallowed exceptions, explicit best-effort paths with warnings |
| Test presence | good | one test module per source module; every script and bash task has tests |
| Duplication | good | key builders and `event_item` shared between `state.py` and `history.py` |
| Dead code | good | only `planner.decide`'s unused `office_id` and `now` (deleted explicitly) |

## Tests

- **Python**: 17 modules under `tests/`, 223 test functions (more once parametrized), offline: respx for HTTP, moto for AWS, an autouse fixture that fakes AWS credentials and removes Telegram variables. Bash tasks are tested by running them with fake `terraform` and `aws` on `PATH` (`test_ci_tasks.py`, `test_check_break_glass.py`).
- **Terraform**: 30 runs in `infra/tests/`, 31 in `infra/bootstrap/tests/`, using `mock_provider "aws"`.
- **Fixtures**: two real NWS captures (`mkx`, `mpx`) plus the `make_story` builder.
- **Coverage**: configured for branch coverage in `pyproject.toml` and opt-in through `mise run coverage`. The team record states 99% branch coverage of `src/weather_story_bot/` against an 80% floor; this scan did not run it. No CI coverage step exists yet.
- **Gaps**: no live integration suite (staging is the live check); no contract test pins the log messages that metric filters match; no test pins timeout, lease and schedule relationships.

## Static Analysis and Policy

| Tool | Scope | Gate |
|---|---|---|
| ruff check and format | Python, rules `E,F,W,I,B,UP,SIM,RUF`, line length 100 | `mise run lint` |
| ty | Python, `ty check` | `mise run lint`; no `# ty: ignore` in the tree |
| terraform fmt | `infra/` recursive | `mise run lint` |
| Checkov | `infra/` and `infra/bootstrap/`, blocking | `mise run scan`; 18 inline skips, each with a reason, enforced by a grep step |
| actionlint, shellcheck, zizmor | workflows and local action | `mise run lint-actions`; 7 inline zizmor ignores, each with a reason |
| Reproducibility | build twice and compare hashes | `checks` job |

## CI/CD

A single `pipeline` workflow. Notable controls: actions pinned to SHAs with the version in a comment; `persist-credentials: false`; `permissions: contents: read` by default; `id-token: write` only on jobs that run no project tests; public-repository safe logging (sensitive Terraform variables, saved plans stored in the artifacts bucket, never as artifacts); deploy jobs serialized by a concurrency group; production approval through a GitHub environment.

## Documentation

`README.md` is thorough and operational (setup, deploy, bootstrap, staging, alerts, cost, recovery, adding an office). Docstrings explain why, not what. No TODO or FIXME markers exist.

## Technical Debt and Risks

| # | Item | Location | Impact |
|---|---|---|---|
| 1 | Log messages double as an alarm interface | `telegram.py`, `handler.py`, `infra/monitoring.tf` | a rename silently disables an alarm |
| 2 | Frozen hash encoding | `state._sha256_json` | any change reposts every active story |
| 3 | Coupled timing constants enforced only by comments | `infra/lambda.tf`, `state.LEASE_DURATION`, `variables.tf` | a slow run's lease could expire mid-run |
| 4 | Bootstrap ahead of main stack (per-office schedule names, `misconfigured` alarm) | `infra/bootstrap/locals.tf` vs `infra/scheduler.tf`, `monitoring.tf` | work in flight; verify before relying on either |
| 5 | Legacy `posted` table and migration tooling | `infra/storage.tf`, `scripts/migrate_*.py` | extra surface until removed |
| 6 | Large handler module and test module | `handler.py`, `tests/test_handler.py` | harder review and change |
| 7 | Substring match on Telegram error text | `telegram._PHOTO_REJECTION_MARKERS` | wording changes would skip the document fallback |
| 8 | Lambda imports botocore at module load | `state.py`, `history.py`, `handler.py` | fine on the Lambda runtime; needs boto3 in any other host |
| 9 | CI coverage step missing | `pipeline.yml` | 80% floor checked by hand |
| 10 | Real-capture fixtures can age | `tests/fixtures/` | payload drift is found only when fixtures are refreshed |

## Conventions Observed in Code

Match the written rules in `aidlc/active-memory/team.md` (Code Style) and `project.md` (Forbidden, Mandated): tooling-enforced style, frozen slotted dataclasses, injected clients, a pure planner, structured logs with a fixed message, comments that explain why, tests named by behaviour, and every suppression carrying a reason.
