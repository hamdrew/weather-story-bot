# weather-story-bot

Python 3.13 Lambda (arm64) that posts NWS Weather Stories to Telegram. Infra is Terraform in `infra/`. Specs and roadmap are in `agent-os/`.

## Commands
Every task is a mise task (`mise.toml`, and bash file tasks in `mise-tasks/`); `mise tasks` lists them and `mise.toml` holds the tool version ranges and the committed `mise.lock` the exact versions (standard `global/tooling`; move them with `mise upgrade`, then `mise lock --platform linux-x64,macos-arm64`). Run several with `:::` (`mise run lint ::: test`): without it, mise hands the second name to the first as an argument.
- `mise run test` - pytest; offline (respx mocks HTTP, moto mocks AWS)
- `mise run coverage` - opt-in coverage; keep `--cov` out of pytest addopts (it breaks debugger breakpoints)
- `mise run tftest` - `terraform test` on `infra/tests/`; offline against a mock AWS provider, no credentials (see `testing/terraform-tests`)
- `mise run scan` - Checkov, blocking; it is its own uv project in `tools/checkov/` (it pins boto3 exactly), locked in `tools/checkov/uv.lock` and bumped by Dependabot; fix a finding or suppress it inline with `#checkov:skip=<ID>:<reason>` (a skip with no reason fails the scan); it scans Terraform only, never the workflows (Checkov silently skips a workflow its schema rejects), which `lint-actions` covers
- `mise run lint` / `mise run format` - ruff check + ruff format + `terraform fmt -recursive`; `lint` also runs `ty check` (fix type errors rather than adding `# ty: ignore`) and `lint-actions` (actionlint on `.github/workflows/*.yml`, zizmor on the workflows and `.github/actions`; zizmor is offline unless a token is set)
- `mise run lint-actions-auditor` - zizmor's stricter auditor persona on the workflows and `.github/actions`, run by hand and not part of `lint`; accept a finding with an inline `# zizmor: ignore[<audit>] <reason>`, never a config file
- `mise run lint-actions-online` - `lint-actions` plus zizmor's online audits, using the `gh` login. **Prefer it over `lint-actions` whenever you lint workflows locally.** Never export a token, put one in `mise.toml`, or pass one on a command line yourself; the task reads it. If it fails because `gh` isn't logged in, say so and fall back to `lint-actions`, naming it as the offline run
- `mise run build` - vendors deps for aarch64-manylinux2014 / py3.13 (binary wheels only) into `build/lambda.zip`; `scripts/build_zip.py` makes it reproducible and writes its base64 sha256 to `build/lambda.zip.sha256`
- `mise run plan <env>` / `mise run deploy <env>` - `<env>` is `production` or `staging` (required positional; selects `infra/envs/<env>.backend.hcl`, `envs/<env>.tfvars` and the data dir `infra/.terraform-<env>/`); `plan` (flag `--no-lock` for `-lock=false`) builds first, passes the zip's hash as `lambda_zip_sha256` and saves `infra/deploy-<env>.tfplan`; `deploy` rebuilds, refuses if the zip isn't the planned one, uploads it to the artifacts bucket (`put-object --if-none-match '*'`, key `<env>/lambda/<base64url hash>.zip`, read from the saved plan), applies exactly that file (no prompt) and deletes it, failing if there's none; the env's tfvars need `artifacts_bucket` and `permissions_boundary_arn` from the bootstrap outputs; ask before running `deploy`. Production is pipeline-only: `plan`/`deploy production` refuse unless `BREAK_GLASS=1` is on the command line (or `GITHUB_ACTIONS=true`); merging to `main` deploys staging, then production after approval (`infra/pipeline`)
- `mise run start <env>` / `mise run pause <env>` - start or pause an environment's schedule and alarm actions through the API (`scripts/set_run_state.py`; Terraform creates the schedule DISABLED and the alarms on, then ignores both); they change a live environment and need the MFA profile, so ask before running
- `mise run bootstrap-plan` / `mise run bootstrap-deploy` - the CI-access stack in `infra/bootstrap/` (OIDC provider, CI roles, per-environment boundaries, artifacts bucket); same saved-plan pattern, applied by hand with the MFA profile, so ask before running `bootstrap-deploy`; `mise run tftest` and `mise run scan` cover it too
- Other Terraform commands need the env's data dir: `TF_DATA_DIR=.terraform-production terraform -chdir=infra output`
- `uv run weather-story-bot --dry-run [--office MKX]` - live NWS fetch, prints each story's decision (`new-or-updated (state not read)` / `expired` / `rejected`) beside its caption; `--dry-run` is required, read-only, never posts

## Standards
- Read `agent-os/standards/index.yml` and the relevant files before changing clients, error handling, retries, logging, config, state/archive, the CLI, tests or infra

## Docs
- Look up API details in Context7 with these library IDs (skip `resolve-library-id`):
  NWS API (api.weather.gov) is `/websites/weather_gov`; Telegram Bot API is `/websites/core_telegram_bots_api`

## Skills
- Planning lives in agent-os (shape-spec, spec plan.md, numbered tasks with deploy gates). Don't use
  superpowers:brainstorming or writing-plans: the spec's plan.md is the plan.
- Everything after planning uses the full superpowers toolkit, subagents included. You may run a
  plan.md stage with executing-plans or subagent-driven-development, fan out independent work with
  dispatching-parallel-agents, and spawn subagents (a fresh-context reviewer on the most capable
  model, research, parallel checks) without asking first.
- In every task: test-driven-development for behaviour changes, systematic-debugging for failures,
  verification-before-completion before reporting done, requesting-code-review before handing back.
- agent-os rules win over a skill's defaults. Stop at natural stopping points you judge, and always
  at the end of a stage and at every gate, even if a skill says to run continuously. Never run `deploy`, `start`/`pause` or `bootstrap-deploy` (they need MFA and
  change live infrastructure), and never commit without asking: where a skill says to commit, stage
  the change and ask. A gate is the user's to run.

## Gotchas
- boto3 is a dev-only dependency (the Lambda runtime provides it). The only runtime dependency is httpx; don't add boto3 to `dependencies`.
- The dev group installs `boto3[crt]` so local scripts can use `aws login` credentials (the login provider needs `awscrt`). `mise run build` exports `--no-dev`, so it never reaches the Lambda zip.
- boto3 client types come from the dev-only `types-boto3[...]` stubs, so import them under `if TYPE_CHECKING:` (e.g. `from types_boto3_s3 import S3Client`). A new AWS service needs its extra added.
- New runtime deps must ship arm64 manylinux wheels, or `mise run build` fails
- Keep each environment's Telegram token in its own SSM parameter (`/weather-story-bot/telegram-token`, `/weather-story-bot-staging/telegram-token`), never in Terraform vars or state
- `infra/envs/*.backend.hcl`, `*.tfvars` and `.env` are gitignored and local-only; the `*.example` files are the templates
- Only mark a story as posted in DynamoDB after Telegram accepts it (a repost is OK, a missed story is not)
