# U-03 Technology Decisions

| Area                 | Decision                                                                                           | Rationale                                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Runtime              | Python 3.13 on arm64 Lambda                                                                        | Required project runtime; preserves the single-service design and proportional staging cost.                      |
| Configuration        | Existing Pydantic versioned models and packaged JSON                                               | Validates non-secret environment, registry, and operation boundaries before assembly.                             |
| Composition          | Existing typed ports with one explicit runtime factory                                             | Binds real adapters once while retaining thin handlers and mock-only dev.                                         |
| AWS integration      | boto3 adapters for DynamoDB, S3, SNS, CloudWatch, Secrets Manager, and Scheduler-facing boundaries | Matches approved AWS scope and supports exact resource/IAM boundaries.                                            |
| External integration | Existing bounded NWS HTTP and Telegram adapters                                                    | Preserves validation, timeout, media, and delivery-classification behavior.                                       |
| Infrastructure       | SAM and CloudFormation                                                                             | Defines validated staging contracts; U-04 owns controlled change-set execution.                                   |
| Observability        | Structured allowlisted logs, CloudWatch metrics, alarms, and dashboard                             | Provides safe actionable evidence without custom alert persistence.                                               |
| Packaging evidence   | uv locked dependencies, pinned arm64 build inputs, SBOM and scans                                  | Makes the source-to-artifact chain reviewable without authorizing deployment.                                     |
| Testing              | pytest, pytest-cov, and Hypothesis                                                                 | Provides deterministic examples, coverage enforcement, custom strategies, shrinking, and reproducible properties. |

## Constraints

- Do not add a queue, database, microservice, public endpoint, customer-managed VPC, alternate
  deployment path, or production activation.
- Do not bypass Pydantic configuration, typed ports, mock-only dev, conditional state behavior,
  CloudWatch-only alert initiation, or owner approval for staging mutation.
- Production packaging, controls, and configuration remain validated contracts, but U-03 does not
  deploy them.

## PBT-09 Framework Decision

Hypothesis remains the selected Python property-testing framework and is a locked development
dependency integrated with pytest. It supports bounded domain strategies, automatic shrinking, and
seed-based reproduction. U-03 code generation must use it alongside focused example tests for the
PBT-01 admission, safe-projection, active-office, and current-state/media properties.
