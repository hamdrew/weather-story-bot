## Why

The weather-story service is designed to run as an AWS-hosted, environment-isolated workload with a fixed monthly application budget, but infrastructure changes currently have no automated cost visibility before deployment. Integrating Infracost into the infrastructure delivery workflow will make estimated cost changes reviewable and provide a policy guardrail against unexpected spend before a CloudFormation change set is applied.

## What Changes

- Add an Infracost-based cost-estimation workflow for the AWS SAM/CloudFormation infrastructure.
- Estimate costs for infrastructure changes in pull requests and for deployable environment configurations, including dev, staging, and prod where their configurations differ.
- Publish a concise cost summary containing monthly baseline cost, monthly change, and the principal resource contributors as review evidence.
- Enforce configurable cost policies: report estimates for all valid plans, fail the check when an environment's configured monthly increase or total monthly estimate exceeds its limit or when the aggregate application estimate exceeds $100 per month, and allow documented reviewed exceptions.
- Make a current, successful cost-policy result for the exact infrastructure revision and target environment a hard prerequisite for every AWS deployment path, including the first resource deployment, workstation bootstrap, and CI verification stacks.
- Store machine-readable Infracost output and policy results as workflow artifacts for audit and release review.
- Keep credentials, Infracost API keys, and environment-specific secret values out of logs, comments, artifacts, and generated CloudFormation outputs.
- Document local and CI usage, baseline management, expected handling of unsupported or usage-dependent resources, and the relationship between Infracost estimates and the existing $100 monthly AWS Budget.

## Capabilities

### New Capabilities

- `infracost-cost-estimation`: Estimate, report, persist, and policy-check AWS infrastructure cost changes for the service's SAM/CloudFormation delivery workflow.

### Modified Capabilities

None.

## Impact

- Adds CI/workflow configuration, Infracost configuration, policy thresholds, and documentation alongside the AWS SAM infrastructure.
- Requires a deterministic cost-estimation input for each supported environment and a maintained cost baseline for meaningful diffs.
- Adds Infracost CLI/API integration and workflow artifacts/checks; it does not provision AWS resources or replace the account-level AWS Budget.
- Deployment and production approval remain governed by CloudFormation change sets and existing environment controls; cost estimation is a mandatory pre-deployment gate, including before the first AWS resource is created.
