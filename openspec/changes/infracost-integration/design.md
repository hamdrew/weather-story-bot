## Context

The repository currently contains OpenSpec planning artifacts for an AWS SAM/CloudFormation service and its `dev`, `staging`, and `prod` environments, but no application source or CI workflow is present yet. The deployment design already establishes a $100 monthly application budget and CloudFormation change-set review, so this integration must add pre-deployment visibility without becoming a second deployment mechanism. See [proposal.md](proposal.md) for motivation and [the capability spec](specs/infracost-cost-estimation/spec.md) for the behavior contract.

Infracost supports CloudFormation YAML/JSON and the AWS SAM transform, making the SAM template the cost-analysis source rather than introducing a parallel Terraform representation. The workflow will use the Infracost CLI in CI and retain JSON output as the source for summaries and policy evaluation.

## Goals / Non-Goals

**Goals:**

- Run repeatable estimates for each configured environment from the same infrastructure inputs used for deployment.
- Compare pull-request infrastructure against a main-branch baseline and make the result visible in review.
- Keep policy thresholds, environment assumptions, and baseline updates explicit and reviewable.
- Produce bounded, secret-free evidence suitable for release/change-set review.
- Handle unsupported resources and usage-dependent assumptions visibly.

**Non-Goals:**

- Replacing CloudFormation change sets, SAM validation, deployment approvals, or the AWS Budget.
- Predicting actual usage, taxes, credits, data-transfer patterns, or account-wide billing with precision.
- Provisioning AWS resources or requiring the cost job to enable schedules or invoke application Lambdas.
- Adding Terraform solely to make cost estimation possible.

## Decisions

### Use a pinned GitHub Actions workflow with the SAM template as input

Add a dedicated workflow that runs on infrastructure pull requests and on explicitly requested deployment/release checks. Pin the Infracost CLI/action to a reviewed version and use the repository's SAM template plus environment-specific non-secret parameter/usage inputs. Run SAM/template validation before cost analysis, and fail the environment estimate if the input cannot be resolved.

Alternative considered: run cost estimation only during deployment. Rejected because it delays cost visibility until after review and makes the result less useful for pull-request decisions. A separate Terraform model is also rejected because it would drift from the CloudFormation source of truth.

### Generate one estimate per environment and enforce an aggregate application guardrail

Treat `dev`, `staging`, and `prod` as independent estimates. Environment-specific conditions, counts, schedules, retention settings, and usage assumptions are resolved before analysis. A combined summary is generated from the individual JSON results. Policy evaluation applies both to each environment, so a low-cost environment cannot hide a prod violation, and to the aggregate of all evaluated application environments, which MUST not exceed the $100 monthly application budget. The aggregate check is required pre-deployment and release evidence whenever all three environment estimates are evaluated; a missing environment estimate makes that aggregate result fail closed rather than omitting it.

Alternative considered: estimate only prod and multiply or infer other environments. Rejected because the existing design intentionally isolates environment resources and configurations.

### Keep baseline and policy configuration in the repository

Store the approved baseline reference and cost-policy configuration alongside the infrastructure. The pull-request job obtains the baseline from the target branch using the same inputs and compares it with the proposed revision. A separate reviewed workflow or explicit command updates the baseline after an approved infrastructure change; ordinary PR runs never rewrite it.

The policy has three independent controls: per-environment total estimated monthly cost, per-environment monthly increase, and the aggregate application total estimated monthly cost capped at $100. Initial per-environment thresholds and their aggregate allocation will be version-controlled during implementation, and their sum MUST not exceed the $100 aggregate cap. The policy output records that the AWS Budget is an account-level enforcement/notification mechanism and that Infracost is an estimate, not actual billing.

Alternative considered: use only Infracost's rendered PR comment as the policy source. Rejected because a stable machine-readable result is needed for artifacts, tests, and release evidence.

### Evaluate policy from normalized Infracost JSON

Use Infracost JSON as the raw evidence, then normalize only the fields needed by the policy and summary: environment, resource identifier/type, monthly total, monthly delta, unsupported/skipped resources, assumptions, source revision, and timestamp. A small repository-owned policy evaluator will produce pass/fail/overridden/error results and bounded messages. It will fail closed for missing baselines and malformed estimates, while unsupported or usage-dependent resources follow an explicit repository policy and remain visible in output.

Alternative considered: encode all thresholds in opaque CI conditionals. Rejected because it makes policy changes hard to review and test.

### Publish review comments and immutable workflow artifacts

Publish one replaceable PR comment containing the aggregate summary and links/identifiers for environment results. Upload per-environment raw/normalized JSON and policy results as workflow artifacts with retention appropriate to release review. Avoid embedding large raw outputs in comments. For non-PR runs, write the same summary to the workflow log and artifacts.

The workflow will use the minimum GitHub token permission needed to update its own PR comment and will avoid AWS credentials unless a later, explicitly approved usage-sync feature requires them. Infracost API keys, if required by the selected CLI mode, come from the CI secret store and are passed only through secret-bearing environment variables.

### Treat estimation as a pre-deployment gate

The cost check becomes a required status for infrastructure pull requests and a prerequisite to the existing change-set review path. It does not itself deploy or mutate the AWS account. Prod still requires the existing human approval, and a passing estimate does not authorize scheduler enablement.

## Risks / Trade-offs

- [Infracost prices and usage assumptions can differ from the AWS bill] → Label all output as estimated, keep assumptions visible, and retain the AWS Budget as the operational spend control.
- [SAM conditions or dynamic references may not resolve in a static estimate] → Validate a resolved, non-secret environment input; fail rather than emit a misleading zero; document unsupported constructs and required assumptions.
- [Resource support changes when Infracost is upgraded] → Pin the version, review upgrades, run fixture-based regression tests, and compare unsupported-resource counts.
- [A baseline can become stale] → Require an explicit baseline revision and age/compatibility check; update it only through a reviewed workflow.
- [PR comments or the pricing service can be unavailable] → Preserve artifacts and a clear failed/indeterminate result; do not silently pass a required check without the configured exception path.
- [Cost policy may block a necessary operational change] → Support narrowly scoped, unexpired reviewed exceptions that preserve the original violation in evidence.

## Migration Plan

1. Add the version-pinned workflow, environment inputs, policy configuration, evaluator, and test fixtures in a non-blocking observation mode.
2. Generate initial baselines for all supported environments from the reviewed infrastructure revision and verify estimates against the AWS Budget context.
3. Enable PR comments and artifact retention; exercise over-limit, missing-baseline, unsupported-resource, and secret-redaction cases.
4. Make the cost check required for infrastructure pull requests after the results are accepted by the service owner.
5. Add the cost check to the pre-deployment/release evidence path while retaining CloudFormation change-set and production-approval gates.

Rollback is configuration-only: disable the required status or workflow gate while preserving the workflow and artifacts for diagnosis. Removing the integration does not affect deployed AWS resources or the account budget.

## Open Questions

None that change the specified behavior or architecture. The exact initial per-environment thresholds and artifact retention period can be selected during implementation within the policy and security constraints above.
