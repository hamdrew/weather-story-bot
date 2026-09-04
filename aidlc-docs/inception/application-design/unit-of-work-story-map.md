# Unit of Work Story Map

## Mapping Rules

- Every approved child story maps to one or more units responsible for its remaining implementation
  or verification work.
- Existing completed baseline behavior remains covered by its approved requirements and is not
  reassigned as new work unless a remaining obligation below explicitly extends it.
- U-05 provides verification coverage for every mapped unit; it does not replace the primary
  implementation owner.

| Epic | Story                                                       | Primary unit | Supporting units       | Mapping rationale                                                                    |
| ---- | ----------------------------------------------------------- | ------------ | ---------------------- | ------------------------------------------------------------------------------------ |
| E-01 | US-1.1 Maintain the Active Office Contract                  | U-03         | U-05                   | Environment parameters, packaged configuration, and isolation verification remain.   |
| E-01 | US-1.2 Retrieve and Normalize Current Stories               | U-05         | U-03                   | Existing implementation needs remaining contract and deployed-boundary verification. |
| E-01 | US-1.3 Retain a Verified Story Image                        | U-03         | U-05                   | Bucket/IAM/lifecycle controls and verification remain.                               |
| E-02 | US-2.1 Publish a New Story Once                             | U-03         | U-05                   | Runtime composition, scoped roles, and integration verification remain.              |
| E-02 | US-2.2 Update a Changed Story                               | U-03         | U-05                   | Runtime composition and deterministic integration verification remain.               |
| E-02 | US-2.3 Contain Ambiguous Delivery                           | U-01         | U-03, U-05             | Alerts, protected operations, composition, and state verification remain.            |
| E-02 | US-2.4 Render a Safe Bounded Caption                        | U-05         | U-03                   | Remaining Unicode, entity, redaction, and property verification remains.             |
| E-03 | US-3.1 Record Current State and Append-Only History         | U-03         | U-05                   | DynamoDB retention/IAM design and verification remain.                               |
| E-03 | US-3.2 Reconcile Incomplete Operations                      | U-01         | U-03, U-05             | Protected operational handling, role binding, and tests remain.                      |
| E-03 | US-3.3 Restore Durable History Safely                       | U-03         | U-05                   | PITR/manual-restore preparation remains; formal exercises are deferred.              |
| E-04 | US-4.1 Process One Bounded Scheduled Run                    | U-03         | U-05                   | Scheduler/runtime composition and boundary verification remain.                      |
| E-04 | US-4.2 Deliver Actionable Operational Alerts                | U-01         | U-03, U-05             | CloudWatch-driven dispatcher, definitive-failure SNS fallback, and tests remain.     |
| E-04 | US-4.3 Observe Service Health Safely                        | U-01         | U-03, U-05             | Sanitized logs/metrics and CloudWatch resource verification remain.                  |
| E-04 | US-4.4 Refresh Office Information Safely                    | U-01         | U-03, U-05             | Office-info Lambda, IAM/composition, and smoke tests remain.                         |
| E-05 | US-5.1 Define the Service as SAM Stacks                     | U-03         | U-02, U-04, U-05       | One staging SAM stack is owner-gated, cost-visible, and verified.                    |
| E-05 | US-5.2 Protect Durable Resources                            | U-03         | U-05                   | PITR, retention, encryption, lifecycle, and IAM tests remain.                        |
| E-05 | US-5.3 Enforce Environment-Scoped Identity and Secrets      | U-03         | U-04, U-05             | Runtime/deployment roles, OIDC, and boundary verification remain.                    |
| E-06 | US-6.1 Consume GitHub as the Sole Source                    | U-04         | U-05                   | CodeConnections/OIDC and no-write source control verification remain.                |
| E-06 | US-6.2 Review Estimated Staging Cost                        | U-02         | U-04, U-05             | Concise non-mutating visibility informs review without gating deployment.            |
| E-06 | US-6.3 Produce Reproducible Build and Supply-Chain Evidence | U-03         | U-04, U-05             | Reproducible artifacts feed release evidence and verification.                       |
| E-06 | US-6.4 Create and Classify a CloudFormation Plan            | U-04         | U-02, U-03, U-05       | Exact revisions, cost evidence, and SAM artifacts feed classification.               |
| E-06 | US-6.5 Pause Every Staging Change for Owner Approval        | U-04         | U-02, U-03, U-05       | Every staging plan pauses for owner approval; classification cannot bypass it.       |
| E-06 | US-6.6 Execute Only an Owner-Approved Staging Change        | U-04         | U-05                   | The exact owner-approved plan executes without substitution or direct mutation.      |
| E-06 | US-6.7 Human-Approve and Execute Production                 | U-04         | U-05                   | Deferred Public-Channel Readiness work remains traceable.                            |
| E-06 | US-6.8 Retain Release, Rollback, and Break-Glass Evidence   | U-04         | U-03, U-05             | Lean staging evidence remains; advanced release evidence is deferred.                |
| E-07 | US-7.1 Verify Examples and Properties                       | U-05         | U-01, U-02, U-03, U-04 | Tests complement every implementation unit.                                          |
| E-07 | US-7.2 Verify Contracts and Deployed Boundaries             | U-05         | U-03, U-04             | Contract, integration, smoke, and deployment boundary verification remains.          |
| E-07 | US-7.3 Enforce Security Boundaries                          | U-04         | U-01, U-02, U-03, U-05 | Delivery security is primary; all units supply controls and tests.                   |
| E-07 | US-7.4 Operate Securely by Default                          | U-01         | U-03, U-04, U-05       | Safe logging/alerts and secure runtime/control-plane defaults remain.                |
| E-08 | US-8.1 Preserve AI-DLC Traceability                         | U-05         | U-01, U-02, U-03, U-04 | Completion evidence links requirements, units, tests, and releases.                  |
| E-08 | US-8.2 Maintain Operational Readiness                       | U-05         | U-01, U-03, U-04       | Recovery, runbooks, smoke, and release evidence remain.                              |
| E-08 | US-8.3 Propose an Issue or Source Change                    | U-04         | U-05                   | Contributor workflow safeguards and validation remain.                               |

## Coverage Check

- [x] All 32 approved child stories are assigned to at least one unit.
- [x] All delivery, cost, infrastructure, runtime, and verification stories preserve separated
      authority boundaries.
- [x] U-05 is included wherever a story has remaining focused, property, integration, or deployed
      verification obligations.
