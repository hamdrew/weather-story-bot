# weather-story-bot

Python 3.13 Lambda (arm64) that posts NWS Weather Stories to Telegram. Infra is Terraform in `infra/`. Specs and roadmap are in `agent-os/`.

## Commands
- `make test` - pytest; offline (respx mocks HTTP, moto mocks AWS)
- `make coverage` - opt-in coverage; keep `--cov` out of pytest addopts (it breaks debugger breakpoints)
- `make lint` / `make format` - ruff check + ruff format + `terraform fmt`
- `make build` - vendors deps for aarch64-manylinux2014 / py3.13 (binary wheels only) into `build/lambda.zip`
- `make plan` / `make deploy` - terraform plan/apply in `infra/`; ask before running `deploy`
- `uv run weather-story-bot --dry-run [--office MKX] [--send-telegram]` - live NWS fetch, prints captions; `--dry-run` is required, and only `--send-telegram` posts (uses `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` from env/`.env`)

## Standards
- Read `agent-os/standards/index.yml` and the relevant files before changing clients, error handling or retries

## Gotchas
- boto3 is a dev-only dependency (the Lambda runtime provides it). The only runtime dependency is httpx; don't add boto3 to `dependencies`.
- New runtime deps must ship arm64 manylinux wheels, or `make build` fails
- Keep the Telegram token in SSM (`/weather-story-bot/telegram-token`), never in Terraform vars or state
- `infra/backend.hcl`, `*.tfvars` and `.env` are gitignored and local-only; the `*.example` files are the templates
- Only mark a story as posted in DynamoDB after Telegram accepts it (a repost is OK, a missed story is not)
