# Weather Story Bot contributor guide

## Project overview

Weather Story Bot is a Python AWS Lambda service that retrieves National
Weather Service Weather Stories and publishes them to Telegram. The project is
spec-driven: implementation work is governed by the active OpenSpec change and
its task list.

## Required toolchain

- Python 3.13.7 and `uv` 0.12.3 are pinned in `mise.toml` and `.python-version`.
- Install or update the local environment with `uv sync`.
- Production and packaging dependency installation must use
  `uv sync --locked --no-dev`. Do not allow production commands to resolve or
  update `uv.lock`.
- Direct application dependencies and development tooling are declared in
  `pyproject.toml`; commit `uv.lock` whenever dependency inputs change.

## Common commands

Run commands from the repository root:

```sh
make format       # Format Python source and tests with Ruff
make lint         # Run Ruff checks
make typecheck    # Run strict mypy checks
make test         # Run pytest with coverage reporting
make coverage     # Run tests and regenerate all static coverage formats
make check        # Run lint, typecheck, and tests
make sync         # Synchronize the local development environment
make sync-production  # Lock-only, no-dev production synchronization
```

Use `make check` before handing off a code change. Run `make format` whenever
you change Python files, then re-run `make check`.

Pytest writes generated coverage artifacts under `coverage/`: open
`coverage/html/index.html` for the browsable static report, use
`coverage/lcov.info` with VS Code coverage extensions, and publish
`coverage/coverage.xml` to CI or code-quality services that consume Cobertura
XML. JSON output is available at `coverage/coverage.json` for automation.

## Code conventions

- Keep Python compatible with Python 3.13 and follow the Ruff configuration in
  `pyproject.toml`: 100-character lines; E, F, I, UP, and B rules.
- Mypy runs in strict mode across `src/` and `tests/`; do not suppress type
  errors without a narrowly justified reason.
- Add or update focused pytest coverage for behavior changes and failure paths.
- Keep runtime configuration non-secret. Telegram tokens belong only in Secrets
  Manager values that conform to `config/secrets/telegram-secret.v1.schema.json`.
- Do not log, commit, or place in test fixtures Telegram tokens, private chat or
  message IDs, token-bearing URLs, raw request/response bodies, or secrets.

## Configuration and data

- `data/nws_office_ids.v1.json` is the versioned NWS office seed input.
- `config/environments/` contains versioned, non-secret dev, staging, and prod
  runtime configuration. Dev Telegram operations must remain mock-only.
- Preserve environment isolation: staging and prod destinations must be
  distinct, and only MKX is active for the current MVP unless the active
  OpenSpec task explicitly changes that requirement.
- Validate configuration through the Pydantic models in
  `src/weather_story_bot/config.py`; do not bypass those invariants with ad hoc
  parsing.

## OpenSpec workflow

- Read the active change's proposal, design, specs, and tasks before
  implementing a task.
- Keep implementation scoped to the selected task and mark a checkbox complete
  only after its specified behavior and relevant tests are finished.
- Validate a change after editing its artifacts or implementation:

```sh
openspec validate <change-name> --type change --strict
```

- Do not silently weaken specification requirements. If implementation reveals
  an ambiguity or a required design change, update the OpenSpec artifacts or
  request direction before proceeding.

## Tooling maintenance

When introducing, removing, or materially changing repository tooling, update
this `AGENTS.md` in the same change. This includes build/package managers,
language or runtime versions, formatters, linters, type checkers, test runners,
deployment tools, security scanners, task runners, and their standard commands.
Keep the documented commands, versions, required checks, and workflow guidance
accurate so future contributors can work from this file alone.
