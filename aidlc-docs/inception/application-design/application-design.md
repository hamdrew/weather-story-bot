# Weather Story Bot Application Design

## Approved Design Decisions

The completed Application Design plan selected A/A/A:

1. Separate collaborating component groups for runtime application behavior, composition,
   infrastructure, delivery controls, observability, and runbooks.
2. A dedicated runtime-composition component with thin Lambda handlers and injected adapters.
3. A distinct infrastructure-and-delivery control plane with explicit evidence, policy, approval,
   and execution interfaces.

## Design Summary

The existing Python service remains a ports-and-adapters application. Validated configuration,
ingestion, durable state, media retention, Telegram publication, and single-office orchestration
form the runtime core. A dedicated composition root assembles real dependencies; handlers validate
events and delegate. Protected operator, alerting, office-information, and observability services
add bounded operational paths.

AWS SAM infrastructure and the GitHub-to-CodePipeline delivery system are distinct control-plane
components. They operate on scoped roles and immutable evidence, not on runtime business objects.
They create and classify exact change sets before requiring the owner's explicit approval for every
staging change; classification informs evidence and risk review but cannot bypass that gate.

The current Personal MVP keeps local development mock-only and deploys only one isolated staging
stack. Infracost supplies concise non-mutating staging visibility while AWS Budget remains the
operational spending control. DynamoDB PITR, S3 versioning/retention, and a documented manual
restore procedure remain; scheduled backups, formal recovery exercises, production deployment, and
production verification are deferred to their named maturity stages. Verification retains focused
example/property coverage and one representative staging smoke path.

## Artifact Index

| Artifact                  | Contents                                                             |
| ------------------------- | -------------------------------------------------------------------- |
| `components.md`           | Component responsibilities, interfaces, ownership, and traceability. |
| `component-methods.md`    | Existing and planned high-level method contracts.                    |
| `services.md`             | Runtime and delivery orchestration responsibilities.                 |
| `component-dependency.md` | Dependency graph, communication matrix, and data flows.              |

## Deferred Detail

Functional Design will define business rules, legal transitions, edge cases, and PBT-01 property
analysis for each work unit. NFR Requirements and NFR Design will define concrete performance,
logging, security, cost, retention, and testing controls. Infrastructure Design will define SAM,
IAM, CodePipeline/CodeBuild, Infracost, CloudFormation, recovery, and approval resource details.

## Extension Compliance

| Rules                           | Status                    | Rationale                                                                                                                                                                                                                                                                                                                            |
| ------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| SECURITY-01 through SECURITY-15 | Compliant or N/A          | The design assigns applicable controls to component boundaries: encrypted infrastructure, redacted logging, input validation, least privilege, deny-by-default operator actions, secure supply chain/integrity, monitoring, and fail-safe errors. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A under the approved architecture. |
| PBT-01 through PBT-10           | N/A at Application Design | The enabled PBT stage matrix begins enforcement in Functional Design, NFR Requirements, Code Generation, and Build and Test. The design preserves tested narrow ports and explicit domain contracts for those stages.                                                                                                                |
| Resiliency Baseline             | N/A                       | Disabled in the approved extension configuration.                                                                                                                                                                                                                                                                                    |

No blocking extension finding remains.
