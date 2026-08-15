## Why

The Milwaukee/Sullivan National Weather Service office publishes timely visual Weather Stories. A user wants to receive them as a Telegram message so that they are notified on their phone and can view the content in a mobile-friendly manner. A reliable, deduplicated publishing service will make these updates available promptly while preserving a durable record for later analysis.

## What Changes

- Seed a registry of all NWS Weather Story offices, implement only active MKX processing for the MVP, and publish new stories with retained images and text descriptions to that office's configured Telegram channel.
- Poll each active office every 15 minutes through its own Lambda invocation.
- Truncate messages that exceed Telegram's message limit and end the truncated text with the Unicode ellipsis character `…`.
- Add durable, queryable storage for story metadata and delivery outcomes so duplicate publications are prevented and historical analytics are possible.
- Retain downloaded story images in durable history for later analysis and audit.
- Add operational monitoring and alerting that notifies a configured private Telegram user when delivery or scheduled-processing failures occur; if alert delivery fails, notify an operator through SNS/email.
- Define and deploy the AWS infrastructure as infrastructure-as-code using AWS SAM.
- Deploy isolated `dev`, `staging`, and `prod` CloudFormation stacks in `us-east-2` within one AWS account, tagged with `Application`, `Environment`, and `Owner`, with a $100 monthly application budget and reviewed production promotion.
- Maintain one nicely formatted, pinned office-information message per real office channel, including NWS office details, home/Weather Stories/region links, and a channel invite link; manage it through a separate on-demand Lambda.
- Host the source in a public GitHub repository with an explicit open-source license, contribution/security guidance, ownership rules, issue and pull-request templates, and protected default-branch governance.
- Establish the public GitHub remote, baseline pull-request checks, and default-branch protection before continuing MVP implementation; after the initial bootstrap, all source and policy changes merge through pull requests, and production deployments use only the approved GitHub OIDC workflow.
- Provide GitHub Actions CI/CD workflows for formatting, static analysis, unit/integration tests, SAM validation/builds, security and dependency checks, cost checks, environment-scoped deployments, smoke gates, and release evidence.
- Use Dependabot for dependency and GitHub Actions update proposals, with automated validation and review requirements for security-sensitive changes.
- Manage versioned releases with protected tags, generated release notes/changelog entries, signed release provenance, SBOMs, and traceability from a release to the reviewed CloudFormation change set and deployed artifact.
- Enable public-repository security controls including secret scanning/push protection where available, CodeQL or equivalent code scanning, dependency review, pinned/least-privileged Actions, and OIDC-based AWS authentication without long-lived deployment keys.
- Do not introduce SQS.

## Capabilities

### New Capabilities

- `weather-story-ingestion`: Retrieve and normalize Weather Stories and associated images from configured NWS offices, with MKX enabled first.
- `telegram-story-publishing`: Publish each newly discovered Weather Story with at most one automatic Telegram send attempt per reservation and explicit reconciliation for ambiguous outcomes.
- `story-history-analytics`: Persist queryable, durable Weather Story and publication history for operational analysis.
- `telegram-operations-alerting`: Monitor the scheduled publishing workflow and deliver actionable alerts to a private Telegram user.
- `aws-weather-story-deployment`: Provision the service and its operational dependencies on AWS through AWS SAM/CloudFormation, and govern its public GitHub source, CI/CD, security automation, environment protections, and release lifecycle.

### Modified Capabilities

None.

## Impact

- Adds an AWS-hosted scheduled workload, durable story/image storage, monitoring and alerting resources, and AWS SAM configuration.
- Adds a public GitHub repository contract, repository governance files, GitHub Actions workflows, Dependabot configuration, security scanning, protected environments, and release-management metadata.
- Integrates with the public NWS API (`/offices/MKX/weatherstories` and the absolute image-download URL returned in each story) and the Telegram Bot API.
- Requires securely configured, environment-specific Telegram bot credentials, destination channel identifiers, private alert-recipient identifiers, SNS/email fallback configuration, GitHub environment protections, and an AWS OIDC trust relationship for deployment workflows.
