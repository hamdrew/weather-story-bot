# Technology Stack

Versions come from `pyproject.toml`, `uv.lock`, `mise.toml`, `mise.lock`, the Terraform `versions.tf` files and `tools/checkov/uv.lock`.

## Runtime

| Item | Value |
|---|---|
| Language | Python 3.13 (`.python-version`, `requires-python >= 3.13`) |
| Platform | AWS Lambda `python3.13`, arm64, 256 MB, 300 s timeout |
| Runtime dependency | httpx 0.28.1 (only one) |
| Provided by Lambda | boto3/botocore (dev-only locally, 1.43.93 locked) |
| AWS services | Lambda, EventBridge Scheduler, DynamoDB, S3, SSM Parameter Store, CloudWatch Logs/Alarms, SNS, IAM, AWS Budgets |
| Region | `us-east-2` (variable default) |
| External services | NWS API (api.weather.gov), Telegram Bot API |

## Development Dependencies (dependency group `dev`)

pytest 9.1.1, pytest-cov (>=7.1.0), respx 0.23.1, moto 5.2.3 (cloudwatch, dynamodb, s3, scheduler, ssm), boto3[crt], python-dotenv, ruff 0.16.10, ty 0.0.85, types-boto3 stubs (cloudwatch, dynamodb, s3, scheduler, ssm, sts).

## Infrastructure

| Item | Value |
|---|---|
| IaC | Terraform `~> 1.11` (mise resolves 1.16.6); AWS provider `~> 6.23` |
| State | S3 backend, partial config per environment, native lockfile (`use_lockfile`) |
| Environments | `staging`, `production` from one root; separate bootstrap root |
| Auth in CI | GitHub OIDC into four roles; permissions boundaries per environment |

## Build and Tooling

| Tool | Pin | Role |
|---|---|---|
| mise | `min_version 2026.10.0`; `minimum_release_age = 7d`; `lockfile = true` | tool versions and every task |
| uv | 0.13 range (0.13.4 locked) | Python env, lock, export, `uv pip install --target` |
| hatchling | build backend | wheel for the package |
| actionlint | 1.7.12 | workflow syntax and `run:` scripts |
| shellcheck | 0.11.0 | used by actionlint |
| zizmor | 1.31.1 | workflow security |
| Checkov | 3.3.29 (own lock) | Terraform scan |
| infracost | external, optional | `mise run cost` |

### Tasks (mise)

`test`, `tftest`, `scan`, `coverage`, `lint`, `format`, `lint-actions`, `lint-actions-online`, `lint-actions-auditor`, `clean`, `build`, `cost`; file tasks `plan`, `deploy`, `start`, `pause`, `bootstrap-plan`, `bootstrap-deploy`, and hidden CI helpers `check-break-glass`, `check-plan`, `plan-changes`, `plan-store`, `plan-summary`, `write-env-config`.

## CI

GitHub Actions, `ubuntu-24.04`: `actions/checkout` v7.0.1, `jdx/mise-action` v5.2.1, `aws-actions/configure-aws-credentials` v6.3.0, each pinned to a full commit SHA. Dependabot updates uv (root and `tools/checkov`), Terraform (both roots) and GitHub Actions weekly, grouping minor and patch.

## Editor

`.vscode/settings.json` enables pytest on `tests`; `.vscode/launch.json` is also committed (not opened).
