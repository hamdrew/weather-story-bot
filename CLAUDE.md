# weather-story-bot

Python 3.13 Lambda (arm64) that posts NWS Weather Stories to Telegram. Infra is Terraform in `infra/`. Specs and roadmap are in `agent-os/`.

## Commands
- `make test` - pytest; offline (respx mocks HTTP, moto mocks AWS)
- `make coverage` - opt-in coverage; keep `--cov` out of pytest addopts (it breaks debugger breakpoints)
- `make tftest` - `terraform test` on `infra/tests/`; offline against a mock AWS provider, no credentials (see `testing/terraform-tests`)
- `make scan` - Checkov, blocking; it is its own uv project in `tools/checkov/` (it pins boto3 exactly), locked in `tools/checkov/uv.lock` and bumped by Dependabot; fix a finding or suppress it inline with `#checkov:skip=<ID>:<reason>` (a skip with no reason fails the scan)
- `make lint` / `make format` - ruff check + ruff format + `terraform fmt -recursive`; `lint` also runs `ty check` (fix type errors rather than adding `# ty: ignore`)
- `make build` - vendors deps for aarch64-manylinux2014 / py3.13 (binary wheels only) into `build/lambda.zip`; `scripts/build_zip.py` makes it reproducible and writes its base64 sha256 to `build/lambda.zip.sha256`
- `make plan ENV=<env>` / `make deploy ENV=<env>` - `ENV` is `production` or `staging` (required; selects `infra/envs/<env>.backend.hcl`, `envs/<env>.tfvars` and the data dir `infra/.terraform-<env>/`); `plan` builds first, passes the zip's hash as `lambda_zip_sha256` and saves `infra/deploy-<env>.tfplan`; `deploy` rebuilds, refuses if the zip isn't the planned one, applies exactly that file (no prompt) and deletes it, failing if there's none; ask before running `deploy`
- `make start ENV=<env>` / `make pause ENV=<env>` - start or pause an environment's schedule and alarm actions through the API (`scripts/set_run_state.py`; Terraform creates the schedule DISABLED and the alarms on, then ignores both); they change a live environment and need the MFA profile, so ask before running
- Other Terraform commands need the env's data dir: `TF_DATA_DIR=.terraform-production terraform -chdir=infra output`
- `uv run weather-story-bot --dry-run [--office MKX]` - live NWS fetch, prints each story's decision (`new-or-updated (state not read)` / `expired` / `rejected`) beside its caption; `--dry-run` is required, read-only, never posts

## Standards
- Read `agent-os/standards/index.yml` and the relevant files before changing clients, error handling, retries, logging, config, state/archive, the CLI, tests or infra

## Docs
- Look up API details in Context7 with these library IDs (skip `resolve-library-id`):
  NWS API (api.weather.gov) is `/websites/weather_gov`; Telegram Bot API is `/websites/core_telegram_bots_api`

## Skills
- Planning lives in agent-os (shape-spec, spec plan.md, numbered tasks with deploy gates).
  Don't use superpowers:brainstorming, writing-plans, executing-plans,
  subagent-driven-development or dispatching-parallel-agents.
- Within a spec task, use superpowers for discipline: test-driven-development for
  behaviour changes, systematic-debugging for failures, verification-before-completion
  before reporting a task done, requesting-code-review before handing back.

## Gotchas
- boto3 is a dev-only dependency (the Lambda runtime provides it). The only runtime dependency is httpx; don't add boto3 to `dependencies`.
- The dev group installs `boto3[crt]` so local scripts can use `aws login` credentials (the login provider needs `awscrt`). `make build` exports `--no-dev`, so it never reaches the Lambda zip.
- boto3 client types come from the dev-only `types-boto3[...]` stubs, so import them under `if TYPE_CHECKING:` (e.g. `from types_boto3_s3 import S3Client`). A new AWS service needs its extra added.
- New runtime deps must ship arm64 manylinux wheels, or `make build` fails
- Keep each environment's Telegram token in its own SSM parameter (`/weather-story-bot/telegram-token`, `/weather-story-bot-staging/telegram-token`), never in Terraform vars or state
- `infra/envs/*.backend.hcl`, `*.tfvars` and `.env` are gitignored and local-only; the `*.example` files are the templates
- Only mark a story as posted in DynamoDB after Telegram accepts it (a repost is OK, a missed story is not)
