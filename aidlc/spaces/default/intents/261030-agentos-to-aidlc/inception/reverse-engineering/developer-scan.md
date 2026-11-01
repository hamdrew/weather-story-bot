# Developer Code Scan: weather-story-bot

Repo: `weather-story-bot` (project-root repo), commit `657c6f08f0f48d489682544a05c5e3f9e51c8e35`, scanned 2026-10-30. Depth: Minimal.

## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - `src/weather_story_bot/` (all 10 modules read in full)
  - `scripts/build_zip.py`, `scripts/set_run_state.py` (read in full)
  - `infra/` main stack: `lambda.tf`, `scheduler.tf`, `storage.tf`, `iam.tf`, `monitoring.tf`, `variables.tf`, `locals.tf`, `outputs.tf`, `versions.tf`, `providers.tf`, `backend.tf`
  - `infra/bootstrap/`: `locals.tf`, `oidc.tf`, `services.tf`, `plan_roles.tf`, `variables.tf`, `outputs.tf`, `versions.tf` (read in full); `apply.tf`, `artifacts.tf` (read in part, rest outlined by statement)
  - `mise.toml`, `mise-tasks/` (all 12 file tasks), `pyproject.toml`, `tools/checkov/pyproject.toml`, `infracost.yml`, `.env.example`, `.python-version`
  - `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `.github/dependabot.yml`, `.github/CODEOWNERS`
  - `tests/conftest.py`; `README.md`; `CLAUDE.md`; `.vscode/launch.json`
  - `agent-os/product/mission.md`, `agent-os/product/tech-stack.md`, `agent-os/standards/index.yml`
  - Lockfiles read for versions only: `uv.lock`, `mise.lock`, `tools/checkov/uv.lock`, `infra/.terraform.lock.hcl`
- **Skimmed only**:
  - `scripts/migrate_story_keys.py`, `scripts/migrate_table_keys.py`, `scripts/infracost_usage.py` (docstrings and top-level constants)
  - `tests/test_*.py` (headers, test counts per file), `tests/fixtures/`
  - `infra/tests/`, `infra/bootstrap/tests/` (headers, `run` counts per file)
  - `infra/envs/*.example`, `infra/bootstrap/*.example`
  - `agent-os/product/roadmap.md` (headings and Phase 1, 2.2, 2.3, 4 sections), `agent-os/specs/` (directory listing; Phase 2.2 `plan.md` outline), `agent-os/notes/` (headers), `agent-os/standards/global/principles.md` (header)
  - `assets/telegram/` (profile text; images not opened)
  - `.gitignore` (project part only), `LICENSE`, `.vscode/settings.json` (not opened)
- **Left out**:
  - `.venv/` (dependency folder)
  - `build/` (build output)
  - `infra/.terraform*/`, `infra/bootstrap/.terraform*/` (Terraform data dirs, gitignored)
  - `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `htmlcov/` (tool caches)
  - gitignored local-only files: `.env`, `infra/envs/*.tfvars`, `infra/envs/*.backend.hcl`, `infra/override.tf`, `infra/bootstrap/override.tf`, `*.tfplan`
  - AI-DLC install and workspace per brief: `.claude/`, `aidlc/`, `aidlc.settings.json`, `.mcp.json`, the AI-DLC block in `.gitignore`. Note: `.claude/commands/agent-os/*.md` (5 tracked files) sit inside `.claude/` and were not opened; they are agent-os slash commands, not AI-DLC files (see Handoff Summary).

### Packages Found
- `weather_story_bot` — application package (Lambda + local CLI) — Python 3.13 — fetches NWS Weather Stories, decides, archives to S3, posts to Telegram, records state in DynamoDB
- `scripts/` — operator tools (not a package) — Python — reproducible zip build, start/pause an environment, cost usage model, two completed one-off migrations
- `infra/` — Terraform root module (main stack, per environment) — HCL — Lambda, schedule, DynamoDB, S3, IAM, alarms, budget
- `infra/bootstrap/` — Terraform root module (CI-access stack) — HCL — GitHub OIDC provider, 4 CI roles, per-env permissions boundaries, artifacts bucket
- `tools/checkov/` — isolated uv project — Python — pins Checkov for `mise run scan`
- `mise-tasks/` — bash file tasks — Bash — plan/deploy/bootstrap/start/pause and CI helpers
- `agent-os/` — planning content (no code) — Markdown/YAML — product mission, roadmap, tech stack, 6 specs, 4 notes, 27 standards + `index.yml`

### Build System
- **Type**: uv (hatchling backend) for Python; mise as task runner and tool-version manager; Terraform for IaC
- **Config Files**: `pyproject.toml`, `uv.lock`, `.python-version`, `mise.toml`, `mise.lock`, `tools/checkov/pyproject.toml`, `tools/checkov/uv.lock`, `infra/versions.tf`, `infra/.terraform.lock.hcl`, `infra/bootstrap/versions.tf`, `infra/bootstrap/.terraform.lock.hcl`, `infracost.yml`
- **Build Dependencies**: `mise run build` → `uv export --no-dev` → `uv pip install --target build/package --python-platform aarch64-manylinux2014 --only-binary :all:` → copy `src/weather_story_bot` → `scripts/build_zip.py` (stored, sorted, fixed-timestamp zip; prints base64 sha256). `mise run plan <env>` → `build` → `terraform plan -var lambda_zip_sha256=...`. `mise run deploy <env>` → `check-plan` → `build` → hash compare → `s3api put-object --if-none-match '*'` → `terraform apply <saved plan>`. Main stack consumes bootstrap outputs (`artifacts_bucket`, `permissions_boundary_arn`) as input variables.

### APIs Discovered
- REST client (outbound) — `src/weather_story_bot/nws.py` — 2 calls: `GET /offices/{id}/weatherstories` (Accept `application/ld+json`), `GET <story.download>` (image/png)
- REST client (outbound) — `src/weather_story_bot/telegram.py` — 3 Bot API methods: `sendPhoto`, `sendDocument` (fallback), `deleteMessage`
- AWS SDK (outbound, boto3) — `handler.py`, `state.py`, `history.py`, `archive.py` — SSM `GetParameter`; DynamoDB `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `TransactWriteItems`; S3 `PutObject`
- Lambda entry point (inbound) — `handler.lambda_handler(event, context)` — 1; returns `{office: {posted, updated, skipped, rejected, failed}}`, raises `ProcessingError` when any count failed; `event` is currently ignored
- CLI (inbound) — `weather-story-bot --dry-run [--office XXX] [--user-agent ...]` (`__main__.py`) — 1 command
- Operator scripts (inbound CLIs) — `scripts/set_run_state.py {start|pause} <outputs> [--apply]`, `scripts/build_zip.py <src> <dst>`, `scripts/infracost_usage.py {write|report}`, two migration scripts — 5
- Log contracts (outbound, consumed by CloudWatch metric filters) — `"Telegram message sent"` → `StoriesPosted`; `"Ambiguous stories from NWS"` → `AmbiguousStories`

### Frameworks & Libraries
- httpx — 0.28.1 — the only runtime dependency (NWS and Telegram HTTP)
- boto3 / botocore — 1.43.93 — AWS SDK; dev-only (Lambda runtime provides it), `boto3[crt]` for `aws login` credentials
- moto — 5.2.3 — AWS mocking in tests (cloudwatch, dynamodb, s3, scheduler, ssm)
- respx — 0.23.1 — httpx mocking in tests
- pytest — 9.1.1; pytest-cov — 7.1.0 (coverage 7.16.0)
- python-dotenv — 1.2.4 — `.env` for the local dry run (optional import)
- ruff — 0.16.10 — linter and formatter
- ty — 0.0.85 — type checker
- types-boto3 — 1.43.94 (+ per-service stubs) — typing under `TYPE_CHECKING`
- Terraform — 1.16.6 (constraint `~> 1.11`); hashicorp/aws provider — 6.68.0 (constraint `~> 6.23`)
- Checkov — 3.3.29 (own uv project)
- uv 0.13.4, actionlint 1.7.12, zizmor 1.31.1, shellcheck 0.11.0 (mise.lock)
- GitHub Actions: actions/checkout v7.0.1, jdx/mise-action v5.2.1, aws-actions/configure-aws-credentials v6.3.0 (all SHA-pinned)
- Infracost — external CLI, not pinned (manual `mise run cost`)

### Test Coverage
- **Test Directories**: `tests/` (pytest, 16 test modules, ~223 test functions, fixtures `tests/fixtures/{mkx,mpx}_weatherstories.json`); `infra/tests/` (4 `.tftest.hcl`, 30 runs); `infra/bootstrap/tests/` (4 `.tftest.hcl`, 31 runs)
- **Test Frameworks**: pytest + respx + moto (offline); `terraform test` with `mock_provider "aws"` (offline)
- **Coverage Config**: present (`[tool.coverage.*]` in `pyproject.toml`, branch coverage, opt-in via `mise run coverage`; deliberately not in pytest addopts). No coverage floor is enforced.

### Code Quality Indicators
- **Linting**: ruff (`pyproject.toml` `[tool.ruff]`, rules E,F,W,I,B,UP,SIM,RUF, line 100); `ruff format`; `ty check`; `terraform fmt -check -recursive`; actionlint + zizmor on workflows (`mise.toml`); Checkov blocking scan with mandatory skip reasons
- **CI/CD**: `.github/workflows/pipeline.yml` (checks → PR plans for both envs; main: deploy staging → plan production (saved to S3) → approved deploy production); composite action `.github/actions/ci-setup`; Dependabot weekly for uv (root and `tools/checkov`), Terraform (both stacks), GitHub Actions
- **Documentation**: thorough `README.md` (setup, deploy, bootstrap, alerts runbook, cost, recovery, add-an-office); docstrings on every module and most functions explain intent and cite agent-os standards; `CLAUDE.md` holds commands and gotchas

### Technical Debt Signals
- No TODO/FIXME/HACK, `noqa` or `ty: ignore` markers in `src/`, `scripts/`, `tests/`, `infra/`.
- 18 `#checkov:skip` suppressions, each with a written reason (`infra/lambda.tf` 7, `infra/storage.tf` 5, `infra/bootstrap/artifacts.tf` 4, `infra/scheduler.tf` 1, `infra/monitoring.tf` 1).
- Completed one-off migrations kept with tests and launch configs: `scripts/migrate_story_keys.py` (2026-09-15), `scripts/migrate_table_keys.py` (2026-09-24).
- MVP DynamoDB table `aws_dynamodb_table.posted` (production only, `infra/storage.tf:2`) kept as rollback; `mvp_table_name` output; bootstrap still names `<name>-posted` (`infra/bootstrap/locals.tf:45`).
- Single-schedule, all-offices-in-one-invocation design (`OFFICES_JSON` env var, `handler.run` loops offices, `event` ignored) is mid-migration: Phase 2.2 Stage 2 already widened bootstrap IAM for per-office schedules (`weather-story-bot-???`) and a `misconfigured` alarm (`infra/bootstrap/locals.tf:50-57`) that the main stack does not yet create.
- `planner.decide` takes `office_id` and `now` but deletes them (`planner.py:78`), kept for call-shape stability.
- `handler.py` is 420 lines (logging setup, orchestration, service wiring in one module); functions are small and single-purpose.
- Pervasive references to agent-os standards by short name (`backend/...`, `infra/...`, `global/...`, `testing/...`) in code comments, Terraform comments, tests, workflow and `mise.toml` (≈60 sites); 1 full-path reference in code (`planner.py:4`).

## Handoff Summary
- **Intent-relevant finding**: `agent-os/` is the project's only planning and standards record and is woven into the codebase. Direct path references: `CLAUDE.md:3,22,29,37` (spec/roadmap location, "Read `agent-os/standards/index.yml`" rule, agent-os planning workflow), `mise.toml:1`, `src/weather_story_bot/planner.py:4`. Indirect references by standard short name (e.g. `backend/side-effect-order`, `infra/pipeline`, `global/tooling`) appear in `src/` (state.py, handler.py, history.py, planner.py, __main__.py), `scripts/`, `tests/`, `infra/*.tf`, `infra/bootstrap/*.tf`, `infra/tests/`, `mise-tasks/`, `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `README.md:95`. Five agent-os slash commands are tracked under `.claude/commands/agent-os/` (inside the AI-DLC-excluded harness dir, not opened). The 27 standards encode load-bearing invariants (frozen hash encoding, side-effect order, log-message contracts for metric filters, IAM shape) that must survive the move. Phase 2.2 is in progress (`agent-os/specs/2026-10-29-1409-wisconsin-and-minneapolis-offices/plan.md`: Stages 1-2 and Task 4 merged as commits #29-#31; Task 5 onward pending).
- **Risks / follow-up**: (1) Removing `agent-os/` without relocating the standards and the in-flight Phase 2.2 plan loses the rationale that ≈60 code comments cite; the destination (AI-DLC memory/knowledge, codekb, or a `docs/` folder) is an open decision. (2) Log messages `"Telegram message sent"` and `"Ambiguous stories from NWS"` are alarm contracts; any comment/doc refactor must not alter them. (3) `_sha256_json` encoding in `state.py` is frozen; never touch it during a refactor. (4) The refactor scope is docs/config only, so the existing pytest, tftest, lint and scan suites must stay green; no new-test floor. (5) Root `CLAUDE.md` "Skills" and "Standards" sections direct agents to agent-os workflows and must be rewritten. (6) Claude auto-memory outside the repo also references agent-os specs (not in scope here).
