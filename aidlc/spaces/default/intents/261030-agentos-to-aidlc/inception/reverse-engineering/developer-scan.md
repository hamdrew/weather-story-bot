## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - `src/weather_story_bot/` (all 9 modules read in full)
  - `scripts/` (docstrings, entry points and structure of all 5 scripts; `build_zip.py` and `set_run_state.py` headers read in detail)
  - `mise-tasks/` (all 11 file tasks read in full)
  - `mise.toml`, `mise.lock`, `pyproject.toml`, `.python-version`, `.env.example`, `infracost.yml`, `.vscode/settings.json`
  - `infra/` main stack (`versions.tf`, `backend.tf`, `providers.tf`, `locals.tf`, `variables.tf`, `lambda.tf`, `storage.tf`, `iam.tf`, `scheduler.tf`, `monitoring.tf`, `outputs.tf`)
  - `infra/bootstrap/` (`locals.tf`, `oidc.tf`, `outputs.tf`, `versions.tf`, resource inventory of every `.tf` file)
  - `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `.github/dependabot.yml`, `.github/CODEOWNERS`
  - `tests/conftest.py` and the test inventory (names and counts per module)
  - `README.md` (structure and the operational sections), `CLAUDE.md`
- **Skimmed only**:
  - `tests/test_*.py` bodies (counted tests per module; read `conftest.py` only)
  - `infra/tests/*.tftest.hcl` and `infra/bootstrap/tests/*.tftest.hcl` (run counts and the mock-provider header)
  - `infra/bootstrap/apply.tf`, `plan_roles.tf`, `services.tf`, `artifacts.tf` (resource names and comments only)
  - `scripts/migrate_story_keys.py`, `migrate_table_keys.py`, `infracost_usage.py` (docstrings and imports)
  - `uv.lock` and `tools/checkov/uv.lock` (pinned versions of key packages only)
  - `assets/telegram/` (avatars and profile text)
- **Left out**: `build/`, `.venv/`, `htmlcov/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/` and `infra/.terraform*` data directories (build output, dependencies and caches; ignored by `.gitignore`). `tests/fixtures/*.json` were listed but not opened (two captured NWS listings). The `.claude/`, `aidlc/`, `.mcp.json` and AI-DLC-marked sections of `AGENTS.md`/`.gitignore` were not scanned, as instructed.

### Packages Found
- `weather_story_bot` — application package (hatchling wheel) — Python 3.13 — Lambda runtime plus a local dry-run CLI (`weather-story-bot` console script)
- `scripts/` — operator and one-off tooling, not packaged — Python — reproducible zip build, start/pause, two data migrations, cost model
- `tools/checkov` — separate uv project (`package = false`) — Python — pins Checkov so its exact boto3 pin does not clash with the main project
- `infra/` — Terraform root module — HCL — per-environment Lambda, DynamoDB, S3, Scheduler, CloudWatch, SNS, IAM
- `infra/bootstrap/` — separate Terraform root module — HCL — GitHub OIDC provider, CI roles, per-environment permissions boundaries, artifacts bucket
- `mise-tasks/` — bash file tasks — Bash — plan, deploy, start, pause and CI helpers

### Build System
- **Type**: mise (task runner and tool-version manager) over uv (Python) and Terraform; hatchling build backend; custom reproducible zip builder
- **Config Files**: `mise.toml`, `mise.lock`, `pyproject.toml`, `uv.lock`, `tools/checkov/pyproject.toml`, `tools/checkov/uv.lock`, `.python-version`, `infra/.terraform.lock.hcl`, `infra/bootstrap/.terraform.lock.hcl`
- **Build Dependencies**: `build` depends on `clean`; `plan` runs `build`; `deploy` runs `check-break-glass`, `check-plan`, `build`, then Terraform apply; `lint` includes `lint-actions`

### APIs Discovered
- NWS API (consumed) — `src/weather_story_bot/nws.py` — 2 calls: `GET /offices/{id}/weatherstories` (`application/ld+json`) and the story's `download` URL (`image/png`)
- Telegram Bot API (consumed) — `src/weather_story_bot/telegram.py` — 3 methods: `sendPhoto` (falls back to `sendDocument`), `deleteMessage`
- Lambda handler (provided) — `src/weather_story_bot/handler.py` — 1 entry point, `weather_story_bot.handler.lambda_handler(event, context)`; the event is ignored; returns a per-office counts dict
- DynamoDB single-table state model (consumed) — `state.py`, `history.py` — items `STORY#`, `EVENT#`, `RUN#`, `LEASE` under `PK=OFFICE#<id>`
- S3 archive (consumed) — `archive.py` — `PutObject` of a `.png` and `.json` per revision
- SSM Parameter Store (consumed) — `handler._build_services` — `GetParameter` with decryption for the Telegram token
- Local CLI (provided) — `__main__.py` — `weather-story-bot --dry-run [--office] [--user-agent]`

### Frameworks & Libraries
- httpx — `>=0.28.1`, locked 0.28.1 — only runtime dependency; HTTP client for NWS and Telegram
- boto3 (+crt) — `>=1.43.93`, locked 1.43.93 — dev-only; the Lambda runtime provides it
- pytest — locked 9.1.1; pytest-cov 7.1.0 (min); respx 0.23.1 (HTTP mocks); moto 5.2.3 (AWS mocks: cloudwatch, dynamodb, s3, scheduler, ssm); python-dotenv (dev, optional in the CLI)
- ruff — locked 0.16.10; ty — locked 0.0.85; types-boto3 stubs (cloudwatch, dynamodb, s3, scheduler, ssm, sts)
- Terraform `~> 1.11` (locked 1.16.6 by mise); AWS provider `~> 6.23`
- actionlint 1.7.12, zizmor 1.31.1, shellcheck 0.11.0, uv 0.13.4 (mise.lock); Checkov 3.3.29 (tools/checkov/uv.lock)

### Test Coverage
- **Test Directories**: `tests/` (17 test modules, 223 test functions, more once parametrized, plus 2 captured NWS fixtures); `infra/tests/` (4 files, 30 `run` blocks); `infra/bootstrap/tests/` (4 files, 31 `run` blocks)
- **Test Frameworks**: pytest with respx and moto; `terraform test` with `mock_provider "aws"`
- **Coverage Config**: present — `[tool.coverage.run]` (branch, source `weather_story_bot`) and `[tool.coverage.report]` in `pyproject.toml`; opt-in through `mise run coverage`, deliberately absent from pytest `addopts`; no CI coverage step (the 80% floor is checked by hand)

### Code Quality Indicators
- **Linting**: ruff rules `E,F,W,I,B,UP,SIM,RUF`, line length 100, `pyproject.toml`; `ty check`; `terraform fmt -check -recursive`; actionlint and zizmor on workflows and the local action; Checkov on `infra/` (blocking, skip needs an inline reason)
- **CI/CD**: `.github/workflows/pipeline.yml` (jobs `checks`, `plan`, `deploy-staging`, `plan-production`, `deploy-production`), composite action `.github/actions/ci-setup/action.yml`, Dependabot for uv (2 projects), terraform (2 roots) and github-actions
- **Documentation**: a long, current `README.md` (setup, deploy, bootstrap, alerts, recovery, cost); module and function docstrings explain why; `CLAUDE.md` for commands and gotchas

### Technical Debt Signals
- No TODO, FIXME or HACK markers and no `# noqa` or `# ty: ignore` anywhere in `src/`, `scripts/`, `tests/` (grep).
- 18 `#checkov:skip` lines, all with reasons (`infra/lambda.tf`, `storage.tf`, `monitoring.tf`, `scheduler.tf`, `bootstrap/artifacts.tf`); 7 `zizmor: ignore` lines, all with reasons (`pipeline.yml`).
- The bootstrap stack is ahead of the main stack: `infra/bootstrap/locals.tf` already allows per-office schedule names (`<name>-???`) and a `misconfigured` alarm, but `infra/scheduler.tf` creates one schedule and `infra/monitoring.tf` has five alarms with no `misconfigured`. This matches work in flight, not an error.
- The legacy `weather-story-bot-posted` table (`infra/storage.tf`, production only, `count`-gated) and its two one-off migration scripts and tests remain until a deliberate removal.
- `planner.decide` accepts `office_id` and `now` and deletes them unused (`planner.py`), kept for call-shape symmetry.
- `handler.py` (420 lines) mixes logging setup, service wiring, orchestration and Telegram deletion; `tests/test_handler.py` is 987 lines.
- Log message strings are an interface: two CloudWatch metric filters match `"Telegram message sent"` and `"Ambiguous stories from NWS"` exactly (`monitoring.tf`), so renaming either log line silently breaks an alarm.
- `tests/conftest.py` fixtures dated 2026-09-13 and 2026-10-29 are real NWS captures and can age as NWS changes its payload.
- `_PHOTO_REJECTION_MARKERS` in `telegram.py` matches Telegram error text by substring.
- Lambda `timeout = 300` and `state.LEASE_DURATION = 360s` are coupled by comment only, and `schedule_expression` (15 min) must stay longer than the lease; no test or validation enforces the first pair.

## Handoff Summary
- **Intent-relevant finding**: The project's conventions live in tooling and configuration, not in a separate rules system: ruff and ty (`pyproject.toml`), the `lint`/`test`/`tftest`/`scan` mise tasks (`mise.toml`), the `checks` CI job (`.github/workflows/pipeline.yml`), and the memory files `aidlc/active-memory/team.md` and `project.md`. Nothing under `src/`, `scripts/`, `infra/`, `.github/`, `mise.toml` or `pyproject.toml` references a removed tool.
- **Risks / follow-up**: Preserve three coupling facts in the synthesis: (1) exact log-message strings are consumed by `infra/monitoring.tf` metric filters; (2) `story_key` and `content_fingerprint` encodings in `state.py` are frozen (changing them reposts every active story); (3) a story is recorded only after Telegram accepts it (`handler._apply_post_or_update`), and the `posted`/`updated` ledger event shares one DynamoDB transaction with the record. Also preserve that the bootstrap stack already anticipates per-office schedules the main stack does not yet create.
