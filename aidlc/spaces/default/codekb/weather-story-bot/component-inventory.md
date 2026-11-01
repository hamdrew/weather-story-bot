# Component Inventory

Each component is listed once here; other artifacts cross-reference by heading.

## Application Components

### Story Model
- **Path**: `src/weather_story_bot/models.py`
- **Responsibility**: immutable `Story` parsed from the NWS payload; `image_id` from the download URL; `parse_time` (naive means UTC).
- **Depends on**: standard library only.

### Settings
- **Path**: `src/weather_story_bot/config.py`
- **Responsibility**: read and validate the five environment variables; parse `OFFICES_JSON`.
- **Depends on**: standard library only.

### NWS Client
- **Path**: `src/weather_story_bot/nws.py`
- **Responsibility**: list stories and download images with a bounded retry.
- **Depends on**: httpx, Story Model.

### Telegram Client
- **Path**: `src/weather_story_bot/telegram.py`
- **Responsibility**: send, fall back, delete; build the HTML caption within 1024 UTF-16 units.
- **Depends on**: httpx, Story Model.

### Planner
- **Path**: `src/weather_story_bot/planner.py`
- **Responsibility**: pure decision logic: `select_active`, ambiguity detection, `decide`.
- **Depends on**: Story Model, Posted Store (hash helpers and `PostedRecord`).

### Posted Store
- **Path**: `src/weather_story_bot/state.py` (`PostedStore`, key builders, hashing)
- **Responsibility**: read the current record; write record plus ledger event in one transaction.
- **Depends on**: botocore, Story Model.

### Office Lease
- **Path**: `src/weather_story_bot/state.py` (`OfficeLease`)
- **Responsibility**: one run per office at a time via a conditional write.
- **Depends on**: botocore.

### Story History
- **Path**: `src/weather_story_bot/history.py`
- **Responsibility**: best-effort rejected, deleted and delete-failed events, `last_seen_at`, run records.
- **Depends on**: botocore, Posted Store key builders.

### Story Archive
- **Path**: `src/weather_story_bot/archive.py`
- **Responsibility**: write each revision's PNG and raw JSON to S3.
- **Depends on**: Story Model, Posted Store (`story_key`).

### Lambda Handler
- **Path**: `src/weather_story_bot/handler.py`
- **Responsibility**: entry point, service wiring on cold start, per-office orchestration, failure isolation, JSON logging with request context.
- **Depends on**: every application component, boto3 (lazy), httpx.

### Dry-Run CLI
- **Path**: `src/weather_story_bot/__main__.py`
- **Responsibility**: read-only local preview of decisions and captions.
- **Depends on**: Settings, NWS Client, Planner, Telegram Client (caption only), python-dotenv (optional).

## Infrastructure Components

### Runtime Stack
- **Path**: `infra/` (`lambda.tf`, `storage.tf`, `scheduler.tf`, `iam.tf`, `monitoring.tf`, `locals.tf`, `variables.tf`, `outputs.tf`, `providers.tf`, `backend.tf`, `versions.tf`)
- **Responsibility**: Lambda and log group; state table (and production-only legacy `posted` table); versioned, private archive bucket with bucket ABAC; schedule (created DISABLED); Lambda and Scheduler roles under the environment's boundary; SNS topic and email subscription; 2 log metric filters and 5 alarms; production-only budget.
- **Depends on**: Bootstrap Stack outputs (`artifacts_bucket`, `permissions_boundary_arn`).

### Bootstrap Stack
- **Path**: `infra/bootstrap/`
- **Responsibility**: GitHub OIDC provider; four CI roles (`pr-plan`, `plan`, `apply-staging`, `apply-production`) trusted by exact subjects; per-environment permissions boundaries and apply policies; artifacts bucket (write-once, versioned).
- **Depends on**: nothing in the repository; applied by hand with MFA.

### Terraform Tests
- **Path**: `infra/tests/`, `infra/bootstrap/tests/`
- **Responsibility**: offline assertions on names, tags, policies, trust and validations using a mock provider.

## Tooling Components

### Build Tooling
- **Path**: `scripts/build_zip.py`, `mise.toml` (`build`)
- **Responsibility**: vendor arm64 wheels, produce a byte-reproducible zip, print its base64 sha256.

### Task Layer
- **Path**: `mise.toml`, `mise-tasks/`
- **Responsibility**: every developer and CI command: test, tftest, scan, lint, format, build, plan, deploy, start, pause, bootstrap, cost, workflow linting.

### Run-State Script
- **Path**: `scripts/set_run_state.py`
- **Responsibility**: enable or disable the schedule and alarm actions idempotently.

### Migration Scripts
- **Path**: `scripts/migrate_story_keys.py`, `scripts/migrate_table_keys.py`
- **Responsibility**: one-off, plan-then-`--apply` data migrations to the current archive paths and state-table keys.

### Cost Model
- **Path**: `scripts/infracost_usage.py`, `infracost.yml`
- **Responsibility**: per-scenario usage files and a side-by-side monthly cost report.

### CI Pipeline
- **Path**: `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `.github/dependabot.yml`, `.github/CODEOWNERS`
- **Responsibility**: checks, read-only PR plans, staging and production deploys with an approval gate.

### Security Scan Project
- **Path**: `tools/checkov/`
- **Responsibility**: isolated, locked Checkov install for `mise run scan`.
