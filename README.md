# Weather Story Bot

An AWS Lambda service that periodically retrieves National Weather Service Weather
Stories and publishes approved updates to Telegram.

> This project is not an emergency alerting service. For urgent weather
> information and emergencies, use official National Weather Service channels.

## Project status

Weather Story Bot is under active, AI-DLC-governed development. The initial MVP
polls the NWS Milwaukee/Sullivan office (MKX) every 15 minutes and publishes
validated Weather Stories to an environment-specific Telegram destination.
Development delivery is mock-only; staging and production destinations are
isolated and never committed here.

## Documentation and community

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)
- [Apache License 2.0](LICENSE)
- [AI-DLC state](aidlc-docs/aidlc-state.md)
- [Approved requirements](aidlc-docs/inception/requirements/requirements.md)

Do not publish Telegram tokens, AWS credentials, private identifiers, invite
links, raw payloads, or unbounded operational logs in public collaboration
surfaces.

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
