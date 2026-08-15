# Weather Story Bot

An AWS Lambda service that periodically retrieves National Weather Service Weather
Stories and publishes approved updates to Telegram.

## Local development

Install the pinned Python and `uv` versions with a compatible tool manager such as
[mise](https://mise.jdx.dev/), then create the local environment:

```sh
uv sync --locked
make check
```

Production dependency installation is deliberately lock-only:

```sh
make sync-production
```

That command runs `uv sync --locked --no-dev`; it fails rather than updating
`uv.lock` when the manifest and lockfile diverge.
