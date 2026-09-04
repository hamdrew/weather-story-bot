# Requirements Amendment Clarification Questions

> **Status:** Superseded after the Resiliency Baseline was disabled and the user clarified that
> OpenSpec will be completely replaced by AI-DLC. The active questions are in
> `openspec-retirement-clarification-questions.md`; no answers are required in this file.

The amended verification answers enabled the Security Baseline and Resiliency Baseline extensions.
The resiliency rules require the decisions below before Requirements Analysis can be finalized.
Question 1 also resolves the remaining conflict between the OpenSpec answer and the repository's
contributor guide. Enter one letter after every `[Answer]:` tag. For an **Other** answer, include the
custom decision after the letter.

## Question 1: OpenSpec Governance Reconciliation

The current answer to Requirements Question 2 makes OpenSpec advisory, while `AGENTS.md` says
implementation is governed by the active OpenSpec change and its task list. How should these
instructions be reconciled?

**Recommendation: A.** This preserves the repository's mandatory spec-driven workflow while still
allowing AI-DLC to identify and propose changes to stale or unsuitable OpenSpec requirements before
implementation.

A) **Recommended** - Keep active OpenSpec requirements and tasks binding; AI-DLC may propose
revisions, but the relevant OpenSpec artifacts must be updated, approved, and strictly validated
before implementing behavior that differs

B) Let AI-DLC requirements supersede OpenSpec only for individually approved conflicts, then
reconcile and strictly validate OpenSpec before implementing the differing behavior

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 2: RTO, RPO, and Disaster Recovery Strategy

What Recovery Time Objective (RTO), Recovery Point Objective (RPO), and Disaster Recovery strategy
should govern the workload?

**Recommendation: A.** Weather Story Bot is useful but not an emergency-alerting service. A
single-region backup-and-restore posture is proportionate to its impact and matches the existing
same-Region PITR, monthly backup, S3 versioning, and $100 cost constraints.

A) **Recommended** - RPO/RTO measured in hours using Backup and Restore; redeploy from IaC and
restore from retained same-Region backups, PITR, and object versions

B) RPO/RTO measured in tens of minutes using a Pilot Light strategy with live data and idle
services

C) RPO/RTO measured in minutes using a Warm Standby strategy with live data and reduced-capacity
services

D) Near-real-time RPO/RTO using multi-region Active/Active services

E) Single-region service with no defined recovery objectives beyond multi-zone managed-service
availability

X) Other (please describe exact RTO/RPO goals and strategy after the `[Answer]:` tag below)

[Answer]:

## Question 3: Change Management Process

How should production changes for this workload be governed?

**Recommendation: B.** No external organizational change-management system is documented, while
the existing design already expects reviewed pull requests, change sets, approval evidence, and
rollback notes. A lightweight repository-owned process makes those expectations explicit.

A) Use an existing organizational change-management process and identify its name or tool after
the `[Answer]:` tag

B) **Recommended** - Have AI-DLC propose a lightweight change-management process with a change
record, approval evidence, deployment verification, and rollback note

C) Exempt this workload from formal change management and document the rationale after the
`[Answer]:` tag

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 4: CI/CD and Deployment Tooling

What CI/CD tooling and deployment process should this workload use?

**Recommendation: A.** The repository already uses GitHub Actions, and the approved requirements
select GitHub OIDC, SAM/CloudFormation change sets, environment protections, and pinned Actions.

A) **Recommended** - Extend the existing GitHub Actions pipeline with AWS SAM/CloudFormation,
GitHub OIDC, Infracost, security evidence, environment gates, and release workflows

B) Treat no suitable pipeline as existing and have AI-DLC propose a different CI/CD pipeline

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 5: Rollback Mechanism

How should a failed production deployment be rolled back?

**Recommendation: A.** Version-pinned IaC and artifact redeployment matches the existing
CloudFormation rollback, retained-state, immutable release-evidence, and prior-artifact design.

A) **Recommended** - Redeploy the previous version-pinned IaC and application artifacts, preserving
retained state and separately reconciling any external Telegram effects

B) Blue/green swap back to a fully provisioned previous environment

C) Canary auto-rollback on health or metric regression

D) Use a database-aware schema/data migration reversal process

E) Use an existing organizational rollback procedure and identify it after the `[Answer]:` tag

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 6: Deployment Style

What deployment strategy is acceptable for this workload's risk and cost profile?

**Recommendation: A.** Lambda/SAM updates with schedules disabled, reviewed change sets, retained
state, and smoke-gated re-enablement provide a proportionate low-cost path for this non-emergency
service; blue/green or canary capacity would add cost and complexity without a stated availability
need.

A) **Recommended** - Direct/in-place CloudFormation update with schedules disabled, normal
CloudFormation rollback, environment smoke checks, and authorized re-enablement

B) Rolling replacement

C) Blue/green deployment

D) Canary deployment with automated rollback

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 7: Regional Topology

Does this workload require multi-region deployment, or is single-region with managed multi-zone
redundancy sufficient?

**Recommendation: A.** The approved MVP explicitly targets `us-east-2`, prohibits cross-Region
replication, and uses managed serverless services that provide multi-zone operation within the
Region. This is consistent with the recommended backup-and-restore posture and cost cap.

A) **Recommended** - Single-region in `us-east-2` using the inherent multi-zone behavior of the
selected managed serverless services

B) Multi-region active-passive with a secondary failover Region

C) Multi-region active-active

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:

## Question 8: Incident Response and Correction of Errors

How should production incidents be handled for this workload?

**Recommendation: B.** No existing incident-management system or on-call process is documented. A
lightweight repository-owned process can connect Telegram/SNS alerts, operator runbooks, issue
tracking, post-incident review, and corrective-action follow-up without inventing enterprise
overhead.

A) Use an existing incident-response process and identify its name or tool after the `[Answer]:`
tag

B) **Recommended** - Have AI-DLC propose a lightweight incident-response and Correction of Errors
process integrated with the repository's alerts, runbooks, and issue tracking

X) Other (please describe after the `[Answer]:` tag below)

[Answer]:
