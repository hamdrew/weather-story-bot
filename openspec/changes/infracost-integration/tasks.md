## 1. Cost-estimation inputs and configuration

- [ ] 1.1 Add a version-pinned Infracost CLI/action configuration and document the supported `dev`, `staging`, and `prod` estimate inputs.
- [ ] 1.2 Add non-secret environment parameter/usage assumptions for the SAM/CloudFormation template, with validation that required values are present and environment names are supported.
- [ ] 1.3 Add version-controlled cost-policy configuration for per-environment total-monthly and monthly-increase limits, an aggregate application total-monthly limit of $100 with allocations whose sum does not exceed that cap, unsupported-resource handling, baseline freshness, exceptions, and artifact retention.
- [ ] 1.4 Add initial reviewed baseline metadata and a deliberate baseline-update procedure that never rewrites baselines during ordinary pull-request estimation.
- [ ] 1.5 Define and document the cross-change sequencing contract: SAM template authoring and non-mutating local estimation may proceed, but no AWS application resource may be created, updated, or deleted until this change's required cost gate has passed or has a documented approved override for the exact template revision and target environment.

## 2. Estimation workflow

- [ ] 2.1 Add the GitHub Actions workflow for infrastructure pull requests, explicit release/deployment checks, and manual reruns.
- [ ] 2.2 Validate the SAM/CloudFormation input before estimation and run one independent estimate for each requested environment.
- [ ] 2.3 Generate machine-readable Infracost output with source revision, environment, timestamp, monthly total, resource details, assumptions, and unsupported/skipped-resource information.
- [ ] 2.4 Compute each environment's diff against the compatible target-branch baseline and fail closed for missing, stale, incompatible, or malformed baselines.
- [ ] 2.5 Ensure the workflow performs cost analysis only and has no AWS application deployment, scheduler enablement, or resource mutation path.

## 3. Reporting and policy evaluation

- [ ] 3.1 Implement the normalized estimate model and repository-owned policy evaluator for per-environment total cost, monthly delta, aggregate application total cost capped at $100, unsupported resources, pricing limitations, and malformed inputs.
- [ ] 3.2 Implement narrowly scoped, unexpired reviewed exceptions that preserve the underlying violation and record reason, approver context, environment, and change context.
- [ ] 3.3 Render a concise replaceable pull-request comment and non-PR summary showing each environment baseline, proposed total, delta, percentage delta, top contributors, assumptions, the aggregate application total against the $100 cap, and the estimated-cost disclaimer.
- [ ] 3.4 Make the workflow status pass, fail, overridden, or error according to the policy result, with exact environment and limit diagnostics.
- [ ] 3.5 Upload per-environment raw output, normalized summary, diff, policy result, and bounded failure evidence as retained workflow artifacts.

## 4. Security and operational documentation

- [ ] 4.1 Configure least-privilege repository token permissions and secret-store handling for any Infracost API key; verify tokens, secret values, and unrestricted command output cannot appear in logs, comments, or artifacts.
- [ ] 4.2 Document local invocation, CI invocation, baseline creation/update, environment assumptions, unsupported resources, usage-based estimates, aggregate $100-cap evaluation, and the distinction between Infracost estimates and the $100 AWS Budget.
- [ ] 4.3 Integrate the cost status into every deployment entry point before AWS credentials or a CloudFormation apply path is used, including the first dev deployment, workstation bootstrap, and CI verification stacks. Require a current exact-revision/environment pass or documented approved override; fail closed for missing, stale, malformed, or mismatched evidence while preserving SAM validation, CloudFormation change sets, human production approval, and scheduler smoke gates.
- [ ] 4.4 Document configuration-only rollback and the procedure for diagnosing pricing-service, comment-publication, baseline, or policy failures without touching deployed resources.

## 5. Verification

- [ ] 5.1 Add fixtures and tests for valid SAM/CloudFormation estimates for each environment, invalid inputs, missing/stale/incompatible baselines, unchanged/reduced/increased costs, and source-revision metadata.
- [ ] 5.2 Add policy tests for per-environment total-cost and monthly-delta thresholds, the aggregate $100 application cap, allocation sums, missing-environment aggregate failures, environment isolation, exact violation reporting, reviewed exceptions, unsupported-resource handling, pricing limitations, and fail-closed errors.
- [ ] 5.3 Add reporting tests for top contributors, percentage calculations, estimated-cost disclaimers, replaceable PR comments, bounded failure summaries, and artifact contents.
- [ ] 5.4 Add security tests that assert no API keys, secret values, tokens, or unrestricted command output are present in logs, comments, or artifacts, and that the workflow cannot deploy or mutate AWS resources.
- [ ] 5.5 Run the workflow in observation mode only against local/rendered or otherwise non-mutating reviewed infrastructure inputs; validate the initial baselines and aggregate estimate against the $100 AWS Budget context, then capture evidence and make the cost check required before any AWS application resource deployment.
- [ ] 5.6 Verify that every deployment mechanism rejects missing, stale, malformed, mismatched, failed, and unauthorized-overridden cost evidence before it can create, update, or delete an AWS application resource; cover the first dev deployment, workstation bootstrap, and CI verification-stack paths.
