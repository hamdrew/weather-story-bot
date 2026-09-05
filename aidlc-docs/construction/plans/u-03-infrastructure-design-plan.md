# U-03 Infrastructure Design Plan

## Scope

Map U-03 runtime composition and staging service boundaries to a complete SAM/CloudFormation
contract. The design will extend the existing U-01 protected office/alert resources with publisher,
reconciliation, retained state/media, disabled schedules, secrets, observability, recovery
preparation, package inputs, and exact IAM boundaries. It authorizes no deployment, schedule
enablement, AWS mutation, or Telegram effect.

## Approved Decisions Applied Without New Questions

- One isolated staging stack exists only in `us-east-2`. Dev remains local/mock-only; production
  parameters/configuration remain validated but are not deployed or activated.
- Every Python function uses Python 3.13 on arm64. Publisher begins at 1024 MB with a 900-second
  timeout; protected operations retain their U-01 explicit bounds. No provisioned concurrency,
  SnapStart, VPC, public endpoint, queue, DLQ, or additional service is approved for Personal MVP.
- The staging DynamoDB table has TTL, 35-day PITR, encryption, retain protections, exact-key access,
  and no scans. S3 has Block Public Access, bucket-owner ownership, TLS enforcement, SSE-S3,
  versioning, retain protections, seven-day staging expiration, and 30-day noncurrent expiration.
- One disabled Scheduler `ScheduleV2` exists per configured active office: UTC `rate(15 minutes)`,
  flexible windows off, no retries, 60-second maximum event age, explicit execution role, and an
  input containing exactly that office ID. No configured office ID is special or hardcoded.
- Separate per-function roles have exact action/resource/prefix/key-family/version-stage/source
  boundaries. Runtime, build, approval, and deployment roles remain separate; U-03 has no
  deployment approval authority.
- U-01's encrypted CloudWatch-to-SNS alert transition and independent fallback persist. Publisher,
  security, and resource failure alarms enrich the concise dashboard without creating a self-loop.
- SAM source/package contracts use locked dependencies and immutable inputs. U-04 later owns
  CodePipeline/CodeBuild and CloudFormation change-set execution.

No unresolved infrastructure choice requires an `[Answer]:` question.

## Design Checklist

- [x] Map runtime functions, execution settings, environment bindings, secret references, and
      adapter permissions to staged SAM resources.
- [x] Map durable DynamoDB and S3 lifecycle, encryption, retention, key-family, and recovery
      preparation requirements.
- [x] Map one disabled per-active-office Scheduler schedule and its exact invocation/execution-role
      boundary without named-office assumptions.
- [x] Map SNS, CloudWatch logs/metrics/alarms/dashboard, alert-loop prevention, and evidence
      retention.
- [x] Define least-privilege roles, IAM trust/resource conditions, tags, outputs, and prohibited
      authorities.
- [x] Define the non-mutating deployment architecture, local validation, and U-04 handoff.
- [x] Validate Security Baseline applicability, PBT carry-forward, and traceability.

## Extension Compliance Plan

- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 apply.
  SECURITY-02, SECURITY-04, and SECURITY-07 are N/A because no network intermediary,
  HTML-serving endpoint, or customer-managed network is provisioned.
- PBT-01 properties remain mandatory for U-03 Code Generation. PBT-02 through PBT-10 follow their
  applicable later stages; PBT-09 framework selection remains compliant.
- Resiliency Baseline is disabled.
