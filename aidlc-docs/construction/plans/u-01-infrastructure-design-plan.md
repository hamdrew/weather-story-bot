# U-01 Infrastructure Design Plan

## Scope

Map U-01 protected office-information, alerting, fingerprint state, and safe observability patterns
to the approved AWS SAM architecture. This is a design artifact only: it does not authorize AWS,
GitHub, or resource mutations.

## Design Checklist

- [ ] Map U-01 logical components to environment-isolated AWS services and roles.
- [ ] Define compute, storage, messaging, networking, monitoring, and shared-infrastructure
      boundaries.
- [ ] Define deployment-architecture flow and non-mutating validation evidence.
- [ ] Validate least privilege, retention, redaction, and deployment-authorization constraints.

## Infrastructure Questions

### Question 1: Deployment Environment

Which deployment environment model should U-01 use?

**Recommendation: A.** It follows the approved single-account `us-east-2` SAM model while keeping
dev mock-only and all resource names, destinations, and roles environment-isolated.

A) **Recommended** — Use environment-scoped SAM stacks in the authorized `us-east-2` account for
dev, staging, and prod, with unique names/tags and dev mock-only Telegram operations

B) Use one shared stack and destination for every environment

C) Deploy U-01 as a local-only service with no SAM integration

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Compute Infrastructure

How should U-01 logical boundaries map to Lambda compute?

**Recommendation: A.** Separate least-privilege Lambda entry points preserve the protected
office-information and alert-dispatch responsibilities while keeping handlers thin and composed.

A) **Recommended** — Use dedicated Python 3.13 arm64 Lambda functions for office information and
alert dispatch, plus the existing publisher/reconciliation boundaries, with composition-root wiring

B) Put all U-01 operations in the publisher Lambda handler

C) Deploy an always-on container service for alert dispatch

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Storage Infrastructure

How should U-01 persist current office and alert-cooldown state?

**Recommendation: A.** The approved DynamoDB current-record and `ALERT#` key families provide
conditional atomicity, bounded TTL operational state, and no scan requirement.

A) **Recommended** — Use the existing environment-isolated DynamoDB table with
`OFFICE#{office_id}/CURRENT` and `ALERT#` records, conditional writes, TTL where approved, and no
table scans

B) Add an independent relational database for alert cooldowns

C) Keep cooldown state only in Lambda process memory

X) Other (please describe after the `[Answer]:` tag below)

### Question 4: Messaging Infrastructure

How should U-01 connect application/CloudWatch failures to alert handling?

**Recommendation: A.** Separate SNS trigger and fallback topics implement the approved no-SQS,
loop-free boundary and support a dedicated alert-dispatch Lambda.

A) **Recommended** — Route eligible application and CloudWatch alarm signals to a dedicated SNS
trigger topic and use a separate SNS/email fallback topic only after definitive private-alert failure

B) Add SQS between all alert components

C) Send every CloudWatch alarm directly to the public Telegram destination

X) Other (please describe after the `[Answer]:` tag below)

### Question 5: Networking Infrastructure

What network exposure should U-01 require?

**Recommendation: A.** U-01 is event-driven and needs only bounded outbound access to approved AWS,
NWS, and Telegram endpoints; it has no public HTTP/API Gateway endpoint or customer-managed network.

A) **Recommended** — No public API Gateway, load balancer, or customer-managed VPC; use scoped
outbound service adapters and approved HTTPS endpoints

B) Expose office-information refresh through a public unauthenticated HTTP API

C) Add a customer-managed VPC and public load balancer for Lambda operations

X) Other (please describe after the `[Answer]:` tag below)

### Question 6: Monitoring Infrastructure

How should U-01 monitor and suppress alerts?

**Recommendation: A.** CloudWatch metrics/alarms/composites provide source-alarm evaluation and
state-transition suppression, while application `ALERT#` state supplies the required cross-source
four-hour policy and aggregation.

A) **Recommended** — Use CloudWatch logs, metrics, alarms, dashboards, and optional composite
suppression for CloudWatch sources; retain application fingerprint state for cross-source cooldown
and route safe signals through SNS

B) Use only CloudWatch alarms as the entire alert-history and cooldown system

C) Use application logs only, without CloudWatch metrics or alarms

X) Other (please describe after the `[Answer]:` tag below)

### Question 7: Shared Infrastructure

How should U-01 share services with the rest of Weather Story Bot?

**Recommendation: A.** Sharing only environment-scoped table, topics, logs, metrics, and secrets
through explicit references preserves cost and operational simplicity without mixing runtime IAM.

A) **Recommended** — Share only approved environment-scoped resources through explicit SAM
references; grant each runtime role its narrow key/prefix/topic/version-stage permissions

B) Let every Lambda use one broad shared runtime role

C) Create cross-environment shared tables, topics, and secrets

X) Other (please describe after the `[Answer]:` tag below)

## Extension Constraints

- SECURITY-01 through SECURITY-15 remain enforced where applicable. SECURITY-02, SECURITY-04, and
  SECURITY-07 remain N/A because no network intermediary, HTML endpoint, or customer-managed network
  is selected.
- PBT obligations carry into Code Generation; Infrastructure Design must keep integration boundaries
  testable with deterministic mocks.
- Resiliency Baseline is disabled.
