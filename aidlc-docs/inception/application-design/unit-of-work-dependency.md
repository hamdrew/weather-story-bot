# Unit of Work Dependencies

## Dependency Matrix

| Unit                                                    | Depends on                                          | Supplies                                                                                  | Dependency rule                                                                                                                              |
| ------------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| U-01 Protected Runtime Operations and Observability     | Existing approved runtime contracts                 | Typed protected-operation, CloudWatch alert-event, metric, and sanitized-event interfaces | No AWS client construction or delivery approval.                                                                                             |
| U-02 Infracost Staging Visibility                       | Approved staging SAM input and environment contract | Concise revision/environment estimate and bounded evidence                                | No custom cost policy, deployment gate, credentials, or AWS application-resource mutation.                                                   |
| U-03 Staging SAM Infrastructure and Runtime Composition | U-01 contracts                                      | Staging SAM/resource contracts, scoped references, and composed handlers                  | Template authoring and local validation may proceed independently of Infracost; no remote mutation occurs before the approved delivery path. |
| U-04 Lean Staging Delivery Control Plane                | U-02 estimate evidence; U-03 SAM/resource contracts | Exact change-set orchestration, owner-approval evidence, and concise release evidence     | Every staging mutation requires owner approval; the estimate is visible evidence, not a gate.                                                |
| U-05 Focused Verification and Recovery Evidence         | U-01, U-02, U-03, and U-04                          | Test results, staging-smoke/manual-restore evidence, defects, and acceptance proof        | Remote staging verification requires separate authorization and the exact-plan/owner-approval controls.                                      |

## Construction Sequence

1. Design U-01 first so protected-operation and CloudWatch alert interfaces are stable.
2. Design U-03 after U-01 interfaces are available; local template authoring and validation stay
   mock-only/non-mutating until a staging plan is approved.
3. Design U-02 independently once the staging SAM inputs are known; its concise estimate informs
   U-04 owner review but does not block U-03 design or staging approval.
4. Design U-04 after U-03 resource/role contracts and U-02 estimate evidence are available.
5. Complete U-05 incrementally with each unit's code changes; perform its one authorized staging
   smoke path only after U-04 creates an exact approved change set.

## Permitted Cross-Unit Communication

| From | To        | Permitted data                                                           | Prohibited data or authority                                                       |
| ---- | --------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| U-01 | U-03      | Validated settings, narrow ports, safe metric/CloudWatch-alert contracts | Raw payloads, secrets, direct deployment control.                                  |
| U-02 | U-04/U-05 | Concise revision/environment estimate and bounded evidence reference     | API keys, mutable baselines, custom policy decisions, AWS mutation authority.      |
| U-03 | U-04/U-05 | Template digest, artifact digest, resource references, change-set inputs | Runtime business objects, secret values, approval decisions.                       |
| U-04 | U-05      | Exact plan identity, owner approval record, release evidence references  | Rebuilt/substituted plan, non-human self-approval, production approval delegation. |
| U-05 | all units | Test result, safe defect/evidence reference                              | Unredacted fixtures, private Telegram data, direct state mutation.                 |

## Security and Test Constraints

- SECURITY-01 through SECURITY-15 apply where relevant to each dependency. SECURITY-02,
  SECURITY-04, and SECURITY-07 are N/A because the approved architecture has no network
  intermediary, HTML endpoint, or customer-managed network.
- PBT-01 property identification is mandatory during Functional Design for U-01 and every other
  unit containing business logic or state. PBT-09 applies in NFR Requirements; all relevant PBT
  obligations carry into Code Generation and Build and Test.
- The dependency graph is acyclic. U-04 never becomes a runtime dependency; U-02 evidence never
  grants approval or direct mutation authority; no non-human role can approve a staging mutation.
