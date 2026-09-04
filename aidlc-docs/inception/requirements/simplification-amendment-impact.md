# Personal-Project Simplification Amendment Impact

## Decision Summary

The user approved all six alerting answers as A and explicitly requested every simplification from
the 2026-09-03 specification review. The amendment therefore preserves high-value AWS learning and
publication safety while moving advanced operational controls into named maturity stages.

## Current Personal MVP

- Local development is mock-only; one isolated staging stack is the real AWS integration target.
- Every staging change set, including a routine in-place update, pauses for the owner's explicit
  cloud-native approval; AI-DLC may plan but cannot approve or directly mutate staging resources.
- SAM, Lambda, DynamoDB, S3, EventBridge Scheduler, CloudWatch, SNS, Secrets Manager,
  CodeConnections, CodePipeline, CodeBuild, and CloudFormation change sets remain in scope.
- CloudWatch alarms are the sole alert trigger. A small alert-notification Lambda posts to the
  dedicated private Telegram alert channel; one separate SNS/email fallback follows only a
  definitive Telegram failure.
- DynamoDB alert fingerprints, four-hour cooldown state, aggregation, and alert-delivery records are
  removed from the target design.
- Infracost remains pinned, non-mutating, and visible as a concise staging estimate; AWS Budget is the
  operational spending control. The custom policy/baseline/exception/gate system is deferred.
- DynamoDB PITR, S3 versioning/retention, and a documented manual restore procedure remain. Scheduled
  backups and recurring formal recovery exercises are deferred.
- Verification concentrates on publication safety, ambiguity/reconciliation, sanitization,
  configuration/environment boundaries, applicable properties, and one representative staging
  smoke path.

## Deferred Maturity Work

| Stage                    | Deferred capabilities                                                                                                                                               | Activation trigger                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Public-Channel Readiness | First production deployment/activation, production approval checks, richer release provenance, formal recovery exercise, and production verification.               | Separate AI-DLC approval before publishing to a broader audience or creating production resources.        |
| Production Maturity      | Scheduled monthly backups, quarterly recovery exercises, expanded release/evidence automation, multi-office operations, and additional controls justified by scale. | More offices/operators, materially larger audience, more frequent releases, or observed operational risk. |

## Personal MVP Scope Disposition

AI-DLC requirements, stories, units, construction artifacts, and tests are the sole active
traceability chain. OpenSpec-derived work labels and mapping inventory are retired.

| Scope area                  | Personal MVP disposition                                                                                                                                                                              |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alerting and observability  | CloudWatch-triggered Telegram notification, one SNS/email fallback, safe logs/metrics, and loop prevention; custom fingerprint persistence/aggregation is excluded.                                   |
| Cost visibility             | Pinned non-mutating staging estimate and AWS Budget; custom baselines, delta policy, exceptions, pull-request comments, and universal mutation gating are deferred.                                   |
| Infrastructure and recovery | Retain SAM/runtime/staging foundations, PITR/manual restore, and concise alarms/dashboard/runbooks; scheduled backups and deployed production concerns are deferred.                                  |
| Verification                | Retain focused critical-path, property, security, integration, and staging-smoke evidence; exhaustive equivalent matrices, recurring recovery exercises, and ephemeral dev verification are deferred. |
| Delivery and release        | Retain a lean staging CodeConnections/CodePipeline/CodeBuild/change-set path with owner approval for every staging mutation and security checks; production/release provenance portions are deferred. |

## Downstream Reconciliation Progress

1. [x] Remove OpenSpec-derived labels and mapping language from active user stories, Application
       Design, Units Generation, and drafted U-01 construction artifacts.
2. [x] Remove the retired migration inventory and residual active repository references.
3. [ ] Supersede and regenerate all drafted U-01 Functional Design, NFR Requirements, NFR Design, and
       Infrastructure Design artifacts under the AI-DLC-only contract.
4. [ ] Resume Construction only after the reconciled downstream artifacts pass their normal approval
       gates.

## Extension Compliance

- Security Baseline remains fully enabled. The amendment retains boundary validation, secrets,
  least privilege, safe logging, supply-chain checks, integrity, security alerts, and fail-closed
  behavior; it removes redundant mechanisms rather than security outcomes.
- Property-Based Testing remains fully enabled. Applicable high-risk properties remain mandatory;
  the amendment narrows applicability by removing custom alert state and custom cost-policy state.
- Resiliency Baseline remains disabled.
