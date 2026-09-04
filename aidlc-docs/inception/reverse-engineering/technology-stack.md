# Technology Stack

## Programming Languages

- **Python 3.13.7** - Application, Lambda handlers, tests, and policy checks.
- **YAML** - GitHub Actions, Dependabot, issue templates, and OpenSpec configuration.
- **JSON** - Versioned environment configuration, secret schema, test fixtures, and office seeds.
- **Markdown** - OpenSpec, architecture, policy, runbooks, and AI-DLC artifacts.

## Application Libraries

- **boto3 1.43.74** - DynamoDB runtime access and AWS SDK integration.
- **httpx 0.28.1** - Synchronous NWS and image HTTP clients.
- **Pillow 12.3.0** - Defensive JPEG and PNG parsing.
- **Pydantic 2.13.4** - Strict configuration and upstream-data validation.
- **regex 2026.7.19** - Unicode grapheme clusters for Telegram caption truncation.
- **timezonefinder 8.3.0** - Coordinate-to-IANA-timezone derivation.

## AWS Services

### Represented in Implemented Code

- **AWS Lambda** - Publisher and reconciliation handler interfaces.
- **Amazon DynamoDB** - Current projections and operational history abstraction.
- **Amazon S3** - Two-phase current-image retention abstraction.

### Planned in OpenSpec

- **AWS SAM and CloudFormation** - Infrastructure definition and deployment.
- **EventBridge Scheduler** - Independent 15-minute invocation per active office.
- **AWS Secrets Manager** - Environment-specific Telegram bot token.
- **Amazon SNS** - Alert trigger and fallback email paths.
- **Amazon CloudWatch** - Logs, metrics, alarms, and dashboards.
- **AWS Backup** - Monthly DynamoDB recovery points.
- **AWS Budgets** - $100 aggregate monthly application budget.
- **IAM and GitHub OIDC** - Least-privilege runtime and deployment identities.

## Build and Package Tools

- **uv 0.12.3** - Locked resolution, development synchronization, and command execution.
- **Hatchling** - Python wheel build backend.
- **mise** - Pinned local Python and uv toolchain manager.
- **GNU Make-compatible task runner** - Standard contributor commands.
- **AWS SAM CLI** - Required by OpenSpec but not yet introduced in the repository.
- **Infracost** - Required by the pending cost-integration change but not yet configured.

## Testing and Quality Tools

- **pytest 9.1.1** - Test runner.
- **pytest-cov 7.1.0** - Line coverage with a 75% required floor and multiple static formats.
- **Hypothesis 6.165.10** - Network-independent invariant and boundary testing.
- **mypy 2.3.1** - Strict type checking across source and tests.
- **Ruff 0.16.3** - Formatting and E/F/I/UP/B lint rules.
- **CodeQL** - GitHub-hosted Python static security analysis.
- **Dependency Review** - GitHub dependency vulnerability and license gate.

## Delivery Platform

- **GitHub** - Public source, pull requests, ownership, security automation, and dependency updates.
- **GitHub Actions** - Current validation/security workflows; deployment, release, SAM, SBOM, and
  Infracost workflows remain planned.
- **Telegram Bot API** - External publication and planned private operator alerts.
- **National Weather Service API** - Public office, region, collection, and image source.

## Runtime Environments

- **dev** - Mock-only Telegram operations.
- **staging** - Isolated live test destinations.
- **prod** - Isolated live production destinations.
- **AWS Region**: `us-east-2` is mandated by OpenSpec for all three future stacks.
