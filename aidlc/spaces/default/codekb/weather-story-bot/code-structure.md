# Code Structure: weather-story-bot

## Repository Layout

```
src/weather_story_bot/   application package (Lambda handler + dry-run CLI)
scripts/                 operator tools (build, start/pause, cost model, finished migrations)
tests/                   pytest suite + captured NWS fixtures (mkx, mpx)
infra/                   Terraform main stack (per environment) + infra/tests/ + envs/*.example
infra/bootstrap/         Terraform CI-access stack + tests/ + *.example
mise.toml, mise-tasks/   every task (inline TOML tasks + bash file tasks)
tools/checkov/           isolated uv project pinning Checkov
.github/                 pipeline workflow, ci-setup composite action, dependabot, CODEOWNERS
agent-os/                planning record: product/, specs/ (6), notes/ (4), standards/ (27 + index.yml)
assets/telegram/         bot avatars (svg/png) and BotFather profile text
.vscode/launch.json      one debug config per executable script (agent-os global/launch-configs)
```

## File Classification (`src/weather_story_bot/`)

| File | Category | Role |
|---|---|---|
| `handler.py` | Controller/Handler + Middleware | Lambda entry, per-office orchestration, JSON log formatter and request-context record factory, service wiring |
| `__main__.py` | Controller/Handler (CLI) | `--dry-run` preview |
| `planner.py` | Service/UseCase (pure) | `select_active`, `decide`, ambiguity checks, `Outcome`, `Decision` |
| `models.py` | Model/Entity | `Story` dataclass, `from_api` boundary validation, `parse_time` |
| `config.py` | Configuration | `Settings.from_env`, `OfficeConfig`, `parse_offices`, office id regex |
| `state.py` | Repository/DAO | `PostedStore`, `OfficeLease`, key builders, hashes (`story_key`, `content_fingerprint`), `event_item` |
| `history.py` | Repository/DAO (best effort) | `StoryHistory`: rejected/deletion events, `last_seen_at`, `RUN#` records |
| `archive.py` | Repository (S3) | `archive_prefix`, `StoryArchive.save` |
| `nws.py` | Adapter (HTTP client) | `NwsClient`, `NwsError`, one retry on transport/5xx |
| `telegram.py` | Adapter (HTTP client) + Utility | `TelegramClient`, `TelegramError`, `build_caption` (UTF-16 length, HTML escape, truncation) |

`scripts/`: `build_zip.py`, `set_run_state.py`, `infracost_usage.py` (Utility/Configuration tools); `migrate_story_keys.py`, `migrate_table_keys.py` (Migration, completed). Tests mirror modules one-to-one (`tests/test_<module>.py`), plus `test_ci_tasks.py` and `test_check_break_glass.py` for bash tasks.

## Internal Import Graph

```
handler   -> archive, config, history, models, nws, planner, state, telegram
__main__  -> config, models, nws, planner, state, telegram
planner   -> models, state
history   -> models, state
archive   -> models, state
state     -> models
nws       -> models
telegram  -> models
config    -> (none)
models    -> (none)
scripts/migrate_* -> archive, config, models, state
```

No circular imports. `state.py` is the shared hub for identity and key construction.

## Code Patterns

- **Injected clients**: every adapter takes its `httpx.Client` / boto3 client (and `sleep`) from the caller; boto3 client types imported under `TYPE_CHECKING` from `types_boto3_*`.
- **Frozen, slotted dataclasses** for all value types (`Story`, `Decision`, `PostedRecord`, `Settings`, `Services`).
- **One public error type per client** (`NwsError`, `TelegramError`, `ConfigError`); `handler.run` is the only catch-all, isolating failures per office and per story.
- **Structured logging**: fixed message + `extra`; `office` and `aws_request_id` injected by a `ContextVar`-backed log record factory, never passed in `extra`.
- **Pure decide, then act**: planner returns decisions; only the handler performs side effects.
- **`StrEnum` outcomes and event kinds**; raw DynamoDB attribute-value dicts (no resource layer).
- **Bash tasks** use `#USAGE` specs for typed arguments and `set -euo pipefail`; environment selects backend, var file, data dir and plan file together.
- **Terraform**: environment differences via `local.production` and variables, never forked files; `#checkov:skip=<ID>:<reason>` inline; `lifecycle.ignore_changes` for operator-owned state.
