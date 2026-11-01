# Code Quality Assessment: weather-story-bot

## Summary

High quality for a single-owner project: complete offline test suites for Python and Terraform, strict linting and type checking, a blocking security scan, SHA-pinned and audited CI, reproducible builds, and unusually thorough rationale in comments. Main debt is transitional (Phase 2.2 mid-flight, MVP rollback artifacts) plus tight coupling of comments and agent instructions to the `agent-os/` standards.

## Tests

| Suite | Files | Cases | Notes |
|---|---|---|---|
| pytest (`tests/`) | 16 modules + `conftest.py` | ~223 | Offline: respx (HTTP), moto (AWS); real captured NWS listings (MKX 2026-09-13, MPX 2026-10-29); `make_story` builder; bash tasks run for real with fake `terraform`/`aws` on PATH |
| terraform test (`infra/tests/`) | 4 | 30 runs | `mock_provider "aws"`; variable validations, IAM, Lambda, environment differences |
| terraform test (`infra/bootstrap/tests/`) | 4 | 31 runs | Trust, plan roles, apply roles, artifacts bucket |

Coverage: configured (branch) but opt-in (`mise run coverage`), no enforced floor; kept out of `addopts` so debugger breakpoints work. Test baseline was not run by this scan (read-only).

## Linting and Static Analysis

ruff check (E,F,W,I,B,UP,SIM,RUF; line 100) and ruff format; ty; `terraform fmt -check`; actionlint + zizmor (online in CI); Checkov blocking with 18 inline skips, each with a reason. No `noqa`, `ty: ignore`, TODO or FIXME markers found.

## CI/CD

`pipeline.yml`: checks (lint, test, tftest, scan, build twice and compare) on every change; credentialed jobs run no tests or linters; PR plans per environment with the read-only role; main deploys staging, saves production's plan to S3, applies after approval; one deploy at a time. Dependabot weekly across five ecosystems. CODEOWNERS routes reviews to the owner.

## Documentation

`README.md` covers setup, local dev, deploy, bootstrap, staging, start/pause, alerts runbook, cost, data recovery, adding an office. Module and function docstrings explain why, citing standards. `CLAUDE.md` gives commands, standards pointer and gotchas. Alarm descriptions are runbooks.

## Quick Ratings

| Aspect | Rating | Note |
|---|---|---|
| Naming clarity | good | Descriptive, domain vocabulary consistent |
| Function size | good | Small single-purpose functions; `handler.py` module is 420 lines but cohesive |
| Error handling | good | One error type per client; one catch-all boundary; per-office/story isolation; history failures warn |
| Test presence | good | Every module and script has a test file |
| Duplication | fair | `event_item` and `StoryHistory.record_deletion` build similar items; `_is_condition_failure` exists in both `state.py` and `history.py` |
| Dead code | fair | Two completed migration scripts and the MVP table/output kept on purpose; `decide` keeps unused params |

## Technical Debt

1. **Phase 2.2 in flight**: bootstrap already permits per-office schedules (`weather-story-bot-???`) and a `misconfigured` alarm (`infra/bootstrap/locals.tf:50-57`), but the main stack still has one schedule, `OFFICES_JSON` (4 KB env cap), and `handler.run` loops all offices in one invocation.
2. **MVP rollback leftovers**: `aws_dynamodb_table.posted` (production), `mvp_table_name` output, `-posted` in bootstrap name lists, `scripts/migrate_*.py` with tests and launch configs.
3. **Small duplication** noted above.
4. **Single global `quiet` alarm** cannot see one silent office (acknowledged in roadmap Phase 2.2/4).

## Agent OS Coupling

What the active intent (remove agent-os, continue in AI-DLC) must handle:

- **Direct path references**: `CLAUDE.md` lines 3 (specs and roadmap location), 22 ("Read `agent-os/standards/index.yml` … before changing …"), 29 and 37 (agent-os planning workflow, shape-spec, plan.md, gates); `mise.toml:1`; `src/weather_story_bot/planner.py:4`.
- **Indirect references by standard short name** (≈60 sites): `backend/*`, `infra/*`, `global/*`, `testing/*` in `src/` (state, handler, history, planner, `__main__`), `scripts/`, `tests/`, `infra/*.tf`, `infra/bootstrap/*.tf`, both tftest folders, `mise-tasks/`, `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `README.md:95`.
- **Tracked agent-os tooling** outside `agent-os/`: `.claude/commands/agent-os/{discover-standards,index-standards,inject-standards,plan-product,shape-spec}.md`.
- **In-flight work**: `agent-os/specs/2026-10-29-1409-wisconsin-and-minneapolis-offices/` (Phase 2.2, Task 5 onward pending) and roadmap Phases 2.3, 3, 4 plus four idea notes.
- **Invariants that live only in the standards** (must be preserved wherever they move): frozen hash encoding (`story-identity`), side-effect order, log contracts, IAM shape, data retention, environments, pipeline rules, CLI read-only rule, testing conventions.
