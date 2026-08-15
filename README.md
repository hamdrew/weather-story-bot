# Weather Story Bot

An AWS Lambda service that periodically retrieves National Weather Service Weather
Stories and publishes approved updates to Telegram.

## Local development

This repository pins Python 3.13.7 and `uv` 0.12.3 in `mise.toml`. With
[mise](https://mise.jdx.dev/) installed, run:

```sh
mise trust
mise install
uv sync --locked
make check
```

For zsh, enable mise in new shells once with:

```sh
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
exec zsh
```

Without shell activation, run project commands through mise explicitly, for
example `mise exec -- uv sync --locked` and `mise exec -- make check`.

Production dependency installation is deliberately lock-only:

```sh
make sync-production
```

That command runs `uv sync --locked --no-dev`; it fails rather than updating
`uv.lock` when the manifest and lockfile diverge.

## Coverage reports

`make test` and `make coverage` generate static coverage reports in `coverage/`.
Open `coverage/html/index.html` in a browser for the detailed report. The same
run also produces `coverage/lcov.info` for VS Code coverage extensions,
`coverage/coverage.xml` for CI and code-quality services that consume Cobertura
XML, and `coverage/coverage.json` for automation.

## Configuration inputs

The checked-in, non-secret configuration is versioned under `data/` and
`config/`. It contains the complete NWS Weather Forecast Office seed set and
isolated `dev`, `staging`, and `prod` Telegram destinations. Only MKX is active
for the MVP; development uses mock-only Telegram identifiers. Bot tokens belong
only in a Secrets Manager value that conforms to
`config/secrets/telegram-secret.v1.schema.json` and must never be committed.
