# Component Inventory

## Application Packages

- `weather_story_bot` - Single deployable Python application package.
  - Configuration and domain models
  - NWS HTTP client and ingestion
  - DynamoDB history and state machine
  - S3 image retention
  - Telegram publishing
  - Scheduled processing
  - Runtime settings and Lambda handlers

## Infrastructure Packages

- None implemented.
- AWS SAM/CloudFormation infrastructure is specified in OpenSpec and remains pending.
- Terraform and CDK are not used.

## Shared Packages

- No separately packaged shared library exists.
- Shared contracts are Python protocols and immutable models inside `weather_story_bot`.

## Test Packages

- `tests` - One repository-local test suite containing 12 functional test modules plus fixture data
  and repository-policy coverage.
- Test styles include example-based unit tests, integration-style tests with in-memory adapters,
  property-based tests, and static repository/workflow policy tests.

## Configuration Packages

- `config/environments` - Versioned non-secret dev, staging, and production settings.
- `config/secrets` - Versioned Telegram secret JSON Schema, not secret values.
- `data` - Versioned NWS office seed set containing 124 office IDs.

## Specification and Architecture Packages

- `openspec/changes/init` - Original service proposal, design, five capability specs, and task list.
- `openspec/changes/infracost-integration` - Cost-estimation proposal, design, capability spec, and
  pending task list.
- `docs` - Living persistence, lifecycle, history-operations, and review documentation.
- `aidlc-docs` - AI-DLC state, audit, and lifecycle artifacts generated from this point forward.

## Delivery and Repository Controls

- `.github/workflows/pr-validation.yml` - Locked Python format, lint, strict mypy, test, and coverage
  gate.
- `.github/workflows/security.yml` - CodeQL and dependency/license review.
- `.github/dependabot.yml` - uv and GitHub Actions update proposals.
- `.github/CODEOWNERS` and templates - Ownership and safe public collaboration controls.

## Total Count

- **Application packages**: 1
- **Application modules**: 10
- **Infrastructure packages**: 0 implemented
- **Shared packages**: 0 separately packaged
- **Test package roots**: 1
- **Tracked test modules**: 12 functional modules plus repository fixtures/support files
- **OpenSpec change packages**: 2
