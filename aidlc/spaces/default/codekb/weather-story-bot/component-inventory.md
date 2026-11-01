# Component Inventory: weather-story-bot

Each heading below is a component name used in the Scope of Analysis block. File-level detail is in [code-structure.md](code-structure.md); contracts in [api-documentation.md](api-documentation.md).

### Lambda Handler

- **Location**: `src/weather_story_bot/handler.py`
- **Responsibility**: Lambda entry; per-office loop with lease, list, download, decide, act; failure isolation per office and story; JSON logging with request context; cold-start service wiring (SSM token, httpx, boto3).
- **Depends on**: Config, NWS Client, Planner, State Store, Story History, Story Archive, Telegram Client.

### Dry-Run CLI

- **Location**: `src/weather_story_bot/__main__.py` (console script `weather-story-bot`)
- **Responsibility**: Read-only preview of live decisions and captions for one office.
- **Depends on**: Config, Story Model, NWS Client, Planner, State Store (`story_key` only), Telegram Client (`build_caption` only).

### Config

- **Location**: `src/weather_story_bot/config.py`
- **Responsibility**: Load and validate environment settings and the office map; office id regex `^[A-Z]{3}$` (mirrored in `infra/variables.tf`).
- **Depends on**: none.

### Story Model

- **Location**: `src/weather_story_bot/models.py`
- **Responsibility**: `Story` value type parsed and validated from the NWS payload; derives `image_id`.
- **Depends on**: none.

### NWS Client

- **Location**: `src/weather_story_bot/nws.py`
- **Responsibility**: Fetch an office's listing and story images with one bounded retry.
- **Depends on**: Story Model; httpx.

### Planner

- **Location**: `src/weather_story_bot/planner.py`
- **Responsibility**: Pure decisions: expired split, ambiguity rejection, post/update/unchanged by fingerprint, change naming.
- **Depends on**: Story Model, State Store (hash and key functions, `PostedRecord`).

### State Store

- **Location**: `src/weather_story_bot/state.py`
- **Responsibility**: Story identity and content hashes; DynamoDB key builders; current-story read; atomic post record + ledger event; office lease.
- **Depends on**: Story Model; boto3 DynamoDB client.

### Story History

- **Location**: `src/weather_story_bot/history.py`
- **Responsibility**: Best-effort append-only history (rejected and deletion events, `last_seen_at`, run records); logs and swallows AWS errors.
- **Depends on**: Story Model, State Store; boto3 DynamoDB client.

### Story Archive

- **Location**: `src/weather_story_bot/archive.py`
- **Responsibility**: Story-keyed S3 layout and writes of image + raw JSON per revision.
- **Depends on**: Story Model, State Store (`story_key`); boto3 S3 client.

### Telegram Client

- **Location**: `src/weather_story_bot/telegram.py`
- **Responsibility**: Caption building; send with photo→document fallback; delete; 429 handling; token-safe errors; emits the `Telegram message sent` log contract.
- **Depends on**: Story Model; httpx.

### Operator Scripts

- **Location**: `scripts/`
- **Responsibility**: Reproducible zip build, start/pause an environment, Infracost usage model, two completed migrations.
- **Depends on**: boto3 (dev), Terraform outputs; migrations import Story Model, State Store, Story Archive, Config.

### Main Infrastructure Stack

- **Location**: `infra/` (`lambda.tf`, `scheduler.tf`, `storage.tf`, `iam.tf`, `monitoring.tf`, `variables.tf`, `locals.tf`, `outputs.tf`)
- **Responsibility**: Per-environment Lambda (S3-sourced zip, reserved concurrency, 300 s timeout), schedule (created DISABLED), state table (+ production MVP table), archive bucket (ABAC, versioning, lifecycle), Lambda and scheduler roles under a permissions boundary, SNS topic, two metric filters, five alarms, production budget.
- **Depends on**: Bootstrap Stack outputs (`artifacts_bucket`, `permissions_boundary_arn`); hand-created SSM parameter; S3 state bucket.

### Bootstrap Stack

- **Location**: `infra/bootstrap/`
- **Responsibility**: GitHub OIDC provider; CI roles `ci-pr-plan`, `ci-plan`, `ci-apply-staging`, `ci-apply-production`; per-environment permissions boundaries; artifacts bucket (no overwrites, TLS only). Already allows Phase 2.2 per-office schedules and a `misconfigured` alarm.
- **Depends on**: S3 state bucket; GitHub repository's immutable OIDC subject prefix.

### Task Runner

- **Location**: `mise.toml`, `mise.lock`, `mise-tasks/`
- **Responsibility**: Tool versions and every task: test, tftest, scan, lint, lint-actions(-online/-auditor), format, coverage, build, cost, plan, deploy, start, pause, bootstrap-plan/deploy, and hidden CI helpers (check-break-glass, check-plan, plan-changes, plan-store, plan-summary, write-env-config).
- **Depends on**: uv, Terraform, AWS CLI, actionlint, zizmor, shellcheck, Infracost (optional).

### CI/CD Pipeline

- **Location**: `.github/workflows/pipeline.yml`, `.github/actions/ci-setup/action.yml`, `.github/dependabot.yml`, `.github/CODEOWNERS`
- **Responsibility**: Checks on every change; PR plans for both environments; on `main` deploy staging, save production plan to S3, apply after approval; weekly dependency updates.
- **Depends on**: Task Runner, Bootstrap Stack roles, repository variables and tfvars secrets.

### Test Suites

- **Location**: `tests/`, `infra/tests/`, `infra/bootstrap/tests/`
- **Responsibility**: Offline pytest (respx + moto) for every module, script and CI bash task; offline `terraform test` with a mock AWS provider for both stacks. Counts in [code-quality-assessment.md](code-quality-assessment.md#tests).
- **Depends on**: pytest, respx, moto, Terraform.

### Agent OS Planning Record

- **Location**: `agent-os/` (`product/` mission, roadmap, tech-stack; `specs/` six dated specs each with plan/shape/references/standards and some cost.md; `notes/` four idea notes; `standards/` 27 standards across global, backend, infra, testing + `index.yml`). Related: `.claude/commands/agent-os/` (5 tracked slash commands, not opened).
- **Responsibility**: The project's planning workflow and coding standards: roadmap source of truth, per-phase specs with deploy gates, and the standards that code comments cite by short name. Phase 2.2 spec is in progress (Stages 1-2 and Task 4 done).
- **Depends on**: nothing at runtime; referenced by `CLAUDE.md`, `mise.toml`, code and infra comments (see [code-quality-assessment.md](code-quality-assessment.md#agent-os-coupling)).
