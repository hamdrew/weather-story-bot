# weather-story-bot

Python 3.13 Lambda (arm64) that posts NWS Weather Stories to Telegram. Infra is Terraform in `infra/`. Specs and roadmap are in `agent-os/`.

## Commands
- `make test` - pytest; offline (respx mocks HTTP, moto mocks AWS)
- `make coverage` - opt-in coverage; keep `--cov` out of pytest addopts (it breaks debugger breakpoints)
- `make lint` / `make format` - ruff check + ruff format + `terraform fmt`; `lint` also runs `ty check` (fix type errors rather than adding `# ty: ignore`)
- `make build` - vendors deps for aarch64-manylinux2014 / py3.13 (binary wheels only) into `build/lambda.zip`
- `make plan` / `make deploy` - terraform plan/apply in `infra/`; ask before running `deploy`
- `uv run weather-story-bot --dry-run [--office MKX] [--send-telegram]` - live NWS fetch, prints captions; `--dry-run` is required, and only `--send-telegram` posts (uses `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` from env/`.env`)

## Standards
- Read `agent-os/standards/index.yml` and the relevant files before changing clients, error handling or retries

## Gotchas
- boto3 is a dev-only dependency (the Lambda runtime provides it). The only runtime dependency is httpx; don't add boto3 to `dependencies`.
- The dev group installs `boto3[crt]` so local scripts can use `aws login` credentials (the login provider needs `awscrt`). `make build` exports `--no-dev`, so it never reaches the Lambda zip.
- boto3 client types come from the dev-only `types-boto3[...]` stubs, so import them under `if TYPE_CHECKING:` (e.g. `from types_boto3_s3 import S3Client`). A new AWS service needs its extra added.
- New runtime deps must ship arm64 manylinux wheels, or `make build` fails
- Keep the Telegram token in SSM (`/weather-story-bot/telegram-token`), never in Terraform vars or state
- `infra/backend.hcl`, `*.tfvars` and `.env` are gitignored and local-only; the `*.example` files are the templates
- Only mark a story as posted in DynamoDB after Telegram accepts it (a repost is OK, a missed story is not)
