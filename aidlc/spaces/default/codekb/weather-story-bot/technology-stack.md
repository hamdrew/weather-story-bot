# Technology Stack: weather-story-bot

Versions are locked versions (lockfile) with the declared range in parentheses.

## Languages and Runtime

| Item | Version | Notes |
|---|---|---|
| Python | 3.13 (`requires-python >=3.13`, `.python-version`) | Lambda runtime `python3.13`, arm64 |
| HCL (Terraform) | 1.16.6 (`~> 1.11`; mise `terraform = "1"`) | Two root modules |
| Bash | — | `mise-tasks/` file tasks |

## Cloud (AWS, us-east-2)

Lambda, EventBridge Scheduler, DynamoDB (on-demand, PITR), S3 (archive, artifacts), SSM Parameter Store (SecureString), CloudWatch Logs / metric filters / alarms, SNS (email), AWS Budgets, IAM (OIDC provider, roles, permissions boundaries). Terraform provider `hashicorp/aws` 6.68.0 (`~> 6.23`). State in S3 with native lockfile.

## Python Libraries

| Library | Version (range) | Scope | Purpose |
|---|---|---|---|
| httpx | 0.28.1 (>=0.28.1) | runtime | NWS and Telegram HTTP |
| boto3 / botocore | 1.43.93 (>=1.43.93, `[crt]`) | dev | AWS SDK (runtime provides it in Lambda) |
| types-boto3 (+ cloudwatch, dynamodb, s3, scheduler, ssm, sts) | 1.43.94 | dev | Type stubs |
| moto | 5.2.3 (>=5.2.3) | dev | AWS mocks |
| respx | 0.23.1 | dev | httpx mocks |
| pytest / pytest-cov | 9.1.1 / 7.1.0 | dev | Tests, opt-in coverage |
| python-dotenv | 1.2.4 | dev | `.env` for the dry run |
| ruff | 0.16.10 | dev | Lint + format |
| ty | 0.0.85 | dev | Type check |
| hatchling | — | build | Build backend |

## Tooling

| Tool | Version | Purpose |
|---|---|---|
| mise | min 2026.10.0 | Tool versions and tasks; `minimum_release_age = 7d` |
| uv | 0.13.4 (`0.13`) | Python env, lock, export, vendoring |
| Checkov | 3.3.29 (>=3.3.19, `tools/checkov`) | Blocking Terraform security scan |
| actionlint | 1.7.12 | Workflow lint |
| zizmor | 1.31.1 | Workflow security audit |
| shellcheck | 0.11.0 | Shell in workflows |
| Infracost | unpinned, external | Manual cost estimate |

## Delivery

GitHub Actions (`ubuntu-24.04`), SHA-pinned actions: `actions/checkout` v7.0.1, `jdx/mise-action` v5.2.1, `aws-actions/configure-aws-credentials` v6.3.0. Dependabot weekly (uv ×2, terraform ×2, github-actions). Telegram Bot API and NWS API (api.weather.gov) as external services.

## Planning Toolchain

Agent OS (`agent-os/` content, `.claude/commands/agent-os/` commands) is the current planning workflow; the active intent replaces it with AI-DLC.
