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

Hypothesis is the development dependency for focused, deterministic,
network-independent property tests. They run with the normal `make test` and
`make check` validation gates alongside example-based unit and integration tests.

Pytest writes generated coverage artifacts under `coverage/`: open
`coverage/html/index.html` for the browsable static report, use
`coverage/lcov.info` with VS Code coverage extensions, and publish
`coverage/coverage.xml` to CI or code-quality services that consume Cobertura
XML. JSON output is available at `coverage/coverage.json` for automation.
Pytest enforces a minimum 75% line-coverage floor. Branch coverage is not
enabled because pytest-cov does not provide a separate branch-only fail gate.

## Code conventions

- Keep Python compatible with Python 3.13 and follow the Ruff configuration in
  `pyproject.toml`: 100-character lines; E, F, I, UP, and B rules.
- Prefer existing library functionality over home-grown code that duplicates it;
  for example, use boto3 paginators for AWS list operations.
- Mypy runs in strict mode across `src/` and `tests/`; do not suppress type
  errors without a narrowly justified reason.
- Every code change MUST add or update focused unit tests covering its intended
  behavior and important failure or boundary paths. A change is not complete
  until those tests run successfully through `make check`.
- When designing tests for a changed set of code, explicitly evaluate whether
  deterministic, network-independent property-based testing can cover its
  invariants, input boundaries, or state transitions; add Hypothesis coverage
  when it provides meaningful additional assurance over example-based tests.
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
- Treat [docs/data-model.md](docs/data-model.md) and
  [docs/state-diagram.md](docs/state-diagram.md) as living architecture references.
  Any change to persisted records, key schema, retention, S3 image lifecycle, or
  state transitions must update the relevant document in the same change. Keep both
  documents aligned with the active OpenSpec artifacts and preserve the repository
  redaction rules: document contracts and field names only, never secret values,
  tokens, real private identifiers, invite links, raw payloads, or raw responses.

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

## Git workflow

- Make code changes on a feature branch; do not commit directly to the default
  branch.
- Name branches according to [Conventional Branch](https://conventionalbranch.org/),
  using a purpose prefix such as `feature/`, `fix/`, `chore/`, or `codex/` and a
  lowercase, hyphen-separated description.
- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
  for commit messages.
- Submit completed changes as a pull request for review. Do not merge directly
  unless explicitly authorized.
- Create pull requests ready for review by default; use Draft mode only when
  the user specifically requests a draft pull request.
- Pin every GitHub Action reference to the full commit hash for a released
  action version, followed by an inline comment naming that release tag (for
  example, `# v1.0.0`). Look up the latest release on GitHub before adding or
  updating an action reference.
- For `/review` commands, use the detailed checklist in
  [`docs/code-revew.md`](docs/code-revew.md) after reading the active OpenSpec
  artifacts. Report only actionable findings, ordered by severity, with
  concrete impact and file/line references; if there are no findings, state
  that explicitly and list residual risks or untested assumptions.

## Tooling maintenance

When introducing, removing, or materially changing repository tooling, update
this `AGENTS.md` in the same change. This includes build/package managers,
language or runtime versions, formatters, linters, type checkers, test runners,
deployment tools, security scanners, task runners, and their standard commands.
Keep the documented commands, versions, required checks, and workflow guidance
accurate so future contributors can work from this file alone.
