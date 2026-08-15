## Purpose

Provide consistent, reviewable AWS cost estimates for infrastructure changes before deployment, with explicit policy outcomes and durable evidence for the weather-story service's environment and budget controls.

## ADDED Requirements

### Requirement: Estimate supported infrastructure configurations

The cost workflow MUST produce an Infracost estimate for each supported environment configuration that is requested by the workflow, using the repository's deployable AWS infrastructure as its source. An estimate MUST identify the environment, the input revision, the estimate timestamp, the estimated monthly total, and whether the result represents a baseline, a change, or an error.

#### Scenario: Estimate a valid environment

- **WHEN** a supported `dev`, `staging`, or `prod` infrastructure configuration is evaluated
- **THEN** the workflow produces a machine-readable estimate with the environment name, monthly total, and resource-level cost data

#### Scenario: Reject an invalid configuration

- **WHEN** the workflow receives an unsupported environment or an infrastructure input that cannot be parsed
- **THEN** it marks that environment's estimate as failed, reports a bounded actionable error, and does not present the result as a zero-cost estimate

### Requirement: Report cost changes for review

The workflow MUST publish a human-readable summary for every successful change estimate, including the monthly baseline, proposed monthly total, absolute monthly difference, percentage difference when calculable, and the largest contributing resource changes. The summary MUST distinguish estimated cost from actual AWS billing.

#### Scenario: Infrastructure cost increases

- **WHEN** a valid proposed configuration costs more than its recorded baseline
- **THEN** the review summary shows the positive monthly delta and identifies the principal resource contributors

#### Scenario: Infrastructure cost is unchanged or reduced

- **WHEN** a valid proposed configuration has no increase or costs less than its recorded baseline
- **THEN** the review summary shows the zero or negative monthly delta and does not report a false increase

### Requirement: Enforce configurable cost policy

The workflow MUST evaluate successful estimates against configured per-environment limits for total estimated monthly cost and monthly increase, and against an aggregate application total estimated monthly cost limit of `$100` across `dev`, `staging`, and `prod`. It MUST fail the cost check when a configured limit is exceeded, pass when all applicable limits are satisfied, and report the exact exceeded limit and measured value. Policy limits and per-environment allocations MUST be version-controlled; the sum of allocations MUST NOT exceed the `$100` aggregate cap.

#### Scenario: Cost policy passes

- **WHEN** all successful environment estimates are within their configured total and delta limits
- **THEN** the cost check passes and records the evaluated limits and values

#### Scenario: Cost policy blocks an over-budget change

- **WHEN** an estimate exceeds its configured total monthly cost or monthly increase limit
- **THEN** the cost check fails, identifies the environment and exceeded limit, and prevents the cost gate from being reported as successful

#### Scenario: Aggregate application estimate exceeds the budget

- **WHEN** the combined `dev`, `staging`, and `prod` estimates exceed `$100` per month
- **THEN** the cost check fails, identifies the aggregate application limit and measured total, and prevents the cost gate from being reported as successful even when every individual environment is within its own limit

#### Scenario: Aggregate evidence is incomplete

- **WHEN** a deployment or release check requires the aggregate application estimate and any of `dev`, `staging`, or `prod` cannot be estimated
- **THEN** the aggregate cost result fails closed and reports the missing or failed environment rather than omitting it from the `$100` comparison

#### Scenario: Reviewed exception is applied

- **WHEN** an authorized, unexpired exception references the specific environment, limit, and change context
- **THEN** the workflow records the exception reason and approver context, marks the policy result as overridden, and preserves the underlying estimate and violation

### Requirement: Maintain and validate baselines

The workflow MUST use an explicitly identified baseline for change comparisons and MUST fail closed when a required baseline is missing, stale according to the repository's defined policy, or incompatible with the proposed environment configuration. Updating a baseline MUST be a deliberate reviewable change and MUST NOT silently occur as a side effect of an ordinary pull-request estimate.

#### Scenario: Baseline is available

- **WHEN** a compatible baseline exists for the same environment and comparison mode
- **THEN** the workflow computes and reports a cost diff against that baseline

#### Scenario: Baseline is missing or incompatible

- **WHEN** no compatible baseline can be found
- **THEN** the workflow reports that the comparison is unavailable and fails the required cost check rather than assuming a zero baseline

### Requirement: Preserve cost evidence

The workflow MUST retain machine-readable estimate, diff, and policy-result artifacts for each evaluated environment. Artifacts MUST include the source revision and environment, exclude credentials and secret values, and be associated with the review or deployment evidence for the change.

#### Scenario: Successful estimate artifacts

- **WHEN** an environment estimate completes
- **THEN** the workflow stores the raw supported output, normalized summary, and policy result as reviewable artifacts

#### Scenario: Failed estimate artifacts

- **WHEN** parsing, pricing, or policy evaluation fails
- **THEN** the workflow stores a bounded failure result with environment and revision context, without storing secrets or unrestricted command output

### Requirement: Keep cost integration secure and non-deploying

The cost workflow MUST use least-privilege credentials, MUST redact tokens and secret values from logs and review output, and MUST NOT create, update, delete, or enable AWS application resources as part of estimation. It MUST distinguish pricing-service or unsupported-resource limitations from zero cost.

#### Scenario: Cost estimation runs

- **WHEN** the cost workflow evaluates an infrastructure change
- **THEN** it performs analysis and policy evaluation only, and no application deployment is initiated

#### Scenario: Pricing is unavailable or incomplete

- **WHEN** a provider price is unavailable, a resource is unsupported, or usage assumptions are required
- **THEN** the workflow reports the limitation and assumption explicitly and applies the configured fail-open or fail-closed policy, never silently treating the resource as free

### Requirement: Gate every AWS application-resource deployment

Before any mechanism creates, updates, or deletes an AWS application resource, it MUST verify a current cost-policy result for the exact deployable infrastructure revision and target environment. The result MUST be `pass` or a documented authorized, unexpired override that preserves the underlying result. Missing, stale, malformed, failed, unauthorized-overridden, or revision/environment-mismatched evidence MUST block the deployment before an AWS application mutation is attempted. This requirement applies to the first AWS application-resource deployment, workstation bootstrap, CI verification stacks, and ordinary deployment/release workflows; local template authoring, validation, and non-mutating estimation remain permitted before the gate is established.

#### Scenario: First AWS application resource is requested

- **WHEN** a deployment mechanism would create the first AWS application resource for an environment
- **THEN** it verifies the required exact-revision/environment cost-policy result and performs no AWS application mutation unless that result passes or has a documented authorized override

#### Scenario: Deployment evidence is absent or mismatched

- **WHEN** a deployment mechanism cannot obtain a current successful or authorized-overridden cost-policy result for its exact infrastructure revision and target environment
- **THEN** it fails before obtaining or using an AWS apply path and reports bounded actionable diagnostics
