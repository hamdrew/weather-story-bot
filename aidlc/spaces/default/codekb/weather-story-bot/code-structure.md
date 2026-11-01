# Code Structure

## Repository Layout (project-owned)

```
src/weather_story_bot/   application package (src layout, hatchling)
tests/                   pytest suite, one module per source module, plus fixtures/
scripts/                 operator and one-off Python tools (not packaged)
mise-tasks/              bash file tasks (plan, deploy, start, pause, CI helpers)
infra/                   Terraform root for one environment (selected by -var environment)
infra/bootstrap/         Terraform root for CI access (applied by hand)
infra/tests/, infra/bootstrap/tests/   terraform test files
tools/checkov/           separate uv project that pins Checkov
.github/                 pipeline workflow, ci-setup composite action, Dependabot, CODEOWNERS
assets/telegram/         bot and channel avatars and profile text
mise.toml, mise.lock, pyproject.toml, uv.lock, infracost.yml
```

## Source File Classification

| File | Lines | Class | Role |
|---|---|---|---|
| `models.py` | 61 | Model | `Story` frozen dataclass, `parse_time`, `image_id` |
| `config.py` | 77 | Configuration | `Settings.from_env`, `OfficeConfig`, `parse_offices`, `ConfigError` |
| `nws.py` | 81 | Repository (remote) | `NwsClient` with retry, `NwsError` |
| `telegram.py` | 183 | Repository (remote) + Utility | `TelegramClient`, `build_caption`, truncation, `TelegramError` |
| `planner.py` | 131 | Service (pure) | `Outcome`, `Decision`, `select_active`, `decide` |
| `state.py` | 341 | Repository | key builders, hashing, `PostedStore`, `OfficeLease`, `EventKind` |
| `history.py` | 186 | Repository (best effort) | `StoryHistory` events, sightings, run records |
| `archive.py` | 61 | Repository | `StoryArchive`, `archive_prefix` |
| `handler.py` | 420 | Controller + Service + Middleware | Lambda entry, orchestration, JSON logging, context vars |
| `__main__.py` | 118 | Controller (CLI) | read-only `--dry-run` |

## Patterns in Use

- Frozen, slotted dataclasses for values (`Story`, `Decision`, `PostedRecord`, `Settings`, `Services`).
- Clients injected by the caller; boto3 types imported under `TYPE_CHECKING` from `types_boto3_*`; boto3 itself imported lazily in `handler._build_services`.
- One public error type per client (`NwsError`, `TelegramError`, `ConfigError`), one catch-all boundary in the handler, and a `ProcessingError` to fail the invocation.
- Pure planner, side effects only in the handler.
- Structured logs: fixed message plus `extra`; a log-record factory adds `office` and `aws_request_id` from context variables.
- Injected `sleep` callables so retry paths test without delay.
- `match` on `StrEnum` outcomes in the CLI; `raise AssertionError("unreachable")` guards (excluded from coverage).

## Supporting Code

| Path | Class | Notes |
|---|---|---|
| `scripts/build_zip.py` | Utility | reproducible zip; standard library only; prints base64 sha256 |
| `scripts/set_run_state.py` | Utility | start or pause schedule and alarm actions via boto3 |
| `scripts/migrate_story_keys.py`, `migrate_table_keys.py` | Migration | one-off, `--apply` required to change anything |
| `scripts/infracost_usage.py` | Utility | usage files and cost report for `mise run cost` |
| `mise-tasks/*` | Configuration | 11 bash tasks with `#MISE`/`#USAGE` headers, `set -euo pipefail` |
| `infra/*.tf` | Configuration | see `component-inventory.md` |

## Tests

One module per source module (`tests/test_<module>.py`) plus `test_build_zip.py`, `test_ci_tasks.py`, `test_check_break_glass.py`, `test_infracost_usage.py` and the two migration and `set_run_state` modules. Shared fixtures in `tests/conftest.py`: autouse `aws_env` (fake credentials, no Telegram variables), `office_payload`/`office_stories`, `make_story(**overrides)`, moto-backed `dynamodb`, `mvp_table`, `s3`.

## Module Import Graph

`models` and `config` are leaves. `state` imports `models`. `archive`, `planner` import `models` and `state`. `history` imports `models` and `state`. `telegram` and `nws` import `models`. `handler` imports every other module. `__main__` imports `config`, `models`, `nws`, `planner`, `state`, `telegram`. No circular imports were found. Third-party edges are listed in `dependencies.md`.
