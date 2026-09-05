# U-03 NFR Requirements Plan

## Scope

Assess U-03 non-functional requirements for the real AWS and Telegram runtime composition, staging
SAM service boundary, durable-resource protection, reproducible package evidence, and manual
restore preparation. U-03 does not deploy staging, execute a change set, activate a schedule, or
perform a real Telegram operation.

## Approved Decisions Applied Without New Questions

The functional design and approved requirements resolve all NFR assessment categories:

- **Scalability:** Personal MVP processes one configured active office per publisher invocation,
  caps work at 25 changed/new revisions, and creates one disabled schedule per active office.
  Multi-office operational readiness is deferred.
- **Performance:** Publisher work has a 14-minute deadline and a 60-second completion reserve.
  Every external adapter has a bounded timeout; metrics capture latency, duration, and memory.
- **Availability and reliability:** Current state uses conditional/transactional transitions; media
  is verified before current commit; ambiguous Telegram delivery is not automatically retried; PITR
  restore preparation targets a separate isolated table. Formal recovery exercises are deferred.
- **Security:** Full Security Baseline applies. Staging is isolated in `us-east-2`; state is retained
  and encrypted; all traffic uses TLS; exact scoped IAM and version-stage secret access apply; no
  public endpoint or customer-managed VPC exists.
- **Technology:** Python 3.13 arm64, uv-locked dependencies, Pydantic, boto3, existing typed ports,
  SAM/CloudFormation, CloudWatch/SNS, Secrets Manager, DynamoDB, S3, pytest, and Hypothesis remain
  selected. No new runtime, queue, database, test framework, or microservice is approved.
- **Maintainability and usability:** Strict typing, Ruff, deterministic injected effects, safe
  observations, concise runbooks, and owner-only change-set approval remain binding. Operator
  outputs are bounded and non-sensitive; no frontend exists.

No unresolved NFR or technology choice requires an `[Answer]:` question.

## Assessment Checklist

- [x] Define capacity, concurrency, deadline, and resource-bound requirements for the composed
      publisher and U-01 operation runtimes.
- [x] Define reliability, recovery-preparation, and delivery-semantics requirements for state,
      media, schedules, and bounded external adapters.
- [x] Define security/privacy, observability, environment isolation, and least-privilege
      requirements at the U-03 runtime boundary.
- [x] Define reproducibility, package-evidence, maintainability, and operator-usability requirements.
- [x] Document U-03-compatible technology decisions and PBT-09 framework evidence.
- [x] Define measurable acceptance evidence and traceability to U-03 obligations.
- [x] Validate Security Baseline applicability and N/A determinations.

## Extension Compliance Plan

- PBT-09 applies: Hypothesis remains declared, locked, pytest-integrated, shrinking-enabled, and
  seed-reproducible. PBT-01 properties from U-03 Functional Design remain mandatory for Code
  Generation; PBT-02 through PBT-08 and PBT-10 follow their applicable later-stage requirements.
- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 apply.
  SECURITY-02, SECURITY-04, and SECURITY-07 are N/A because the approved architecture has no
  network intermediary, HTML-serving endpoint, or customer-managed network.
- Resiliency Baseline is disabled.
