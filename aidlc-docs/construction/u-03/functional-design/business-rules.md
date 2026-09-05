# U-03 Business Rules

## Configuration and Isolation

1. Runtime assembly shall validate every versioned non-secret document through the established
   configuration models before constructing an adapter or resolving a secret.
2. The active ID set in the registry and environment contract shall agree exactly. Every active
   office shall have one distinct destination; inactive offices shall be ineligible and need no
   destination.
3. Dev shall bind only mock Telegram ports. Staging and production destinations shall be live,
   non-mock, and mutually distinct. Production remains a validated contract and is not activated by
   U-03.
4. A resource binding shall belong to the selected environment. Event data, request labels, and
   caller-supplied identifiers shall not replace a binding.

## Invocation Admission and Runtime Boundaries

1. The scheduled publisher accepts exactly one office identifier and processes no fallback or
   inferred office. It denies an inactive, unconfigured, malformed, or unexpected event before
   external work.
2. The publisher's 14-minute budget reserves time for final persistence and safe observation. Each
   external adapter receives a bounded remaining deadline; no unbounded retry or blocking cleanup is
   permitted.
3. Handlers validate and delegate only. Business orchestration, client construction, secret
   resolution, deployment approval, and shell execution are prohibited at handler boundaries.
4. U-01 office authorization uses a trusted invocation identity. An `operator_id` event field is a
   label for safe audit facts only, never evidence of authorization.

## State, Media, and Publication

1. Current office and story facts remain office-scoped. Writes, reservations, leases, revisions,
   and reconciliation use the existing conditional or transactional contract; scan access is
   forbidden.
2. A current media reference is committed only after source and stored-object verification. On
   validation, retention, or conditional-write failure, the prior current projection remains
   authoritative.
3. A started publication reservation authorizes no more than one Telegram API call. An ambiguous
   outcome is not retried until an authorized reconciliation records a definitive non-receipt.
4. Protected office-information work cannot create story attempts, publish a story, create an
   office snapshot, or enable a schedule. It commits only a verified managed reference.

## Observability, Security, and Evidence

1. Observations, metrics, handler results, and build evidence use an allowlisted bounded schema.
   They shall not contain a secret, token-bearing URL, raw body, private chat/message/invite ID,
   unbounded exception, or raw external response.
2. A configuration, authorization, source, state, or evidence mismatch fails closed. No rejected
   result triggers public publication, a substitute action, alert re-entry, or deployment.
3. Only CloudWatch alarm transitions initiate private operator alerting. U-01 preserves one private
   attempt and its definitive-failure-only independent fallback; no outcome publishes to the
   trigger path.
4. Build/package evidence proves source and artifact identity and required local validation. It is
   not deployment permission: U-04 must create an exact change set and obtain owner approval for
   every staging mutation.
5. Restore preparation uses an isolated target and a documented validation/cutover/rollback decision.
   It cannot overwrite a retained source or represent accepted Telegram effects as reversible.

## Security Baseline Compliance

| Rule        | Status    | Functional-design treatment                                                                                                     |
| ----------- | --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| SECURITY-01 | Compliant | Retained state/media and secret/adaptor flows require encrypted/TLS boundaries; concrete controls map in Infrastructure Design. |
| SECURITY-02 | N/A       | No network intermediary is part of the approved architecture.                                                                   |
| SECURITY-03 | Compliant | `SafeObservation` requires centralized structured, redacted logging fields.                                                     |
| SECURITY-04 | N/A       | No HTML-serving endpoint exists.                                                                                                |
| SECURITY-05 | Compliant | Every event, document, and resource binding is bounded and validated before processing.                                         |
| SECURITY-06 | Compliant | Assembly receives only exact scoped bindings; later Infrastructure Design maps least privilege.                                 |
| SECURITY-07 | N/A       | No customer-managed network exists.                                                                                             |
| SECURITY-08 | Compliant | Trusted invocation authorization and exact environment/resource scope deny by default.                                          |
| SECURITY-09 | Compliant | Missing/invalid assembly fails closed without a public default or alternate path.                                               |
| SECURITY-10 | Compliant | Locked dependencies and source/artifact evidence are explicit U-03 behavior.                                                    |
| SECURITY-11 | Compliant | Trust admission precedes every external operation and terminal outcomes prevent notification loops.                             |
| SECURITY-12 | Compliant | Secret material remains behind a dedicated port and never enters models, outputs, or evidence.                                  |
| SECURITY-13 | Compliant | Typed parsing, conditional state, verified media, and exact evidence preserve integrity.                                        |
| SECURITY-14 | Compliant | Safe failure observations and retained evidence support detection without mutable alert state.                                  |
| SECURITY-15 | Compliant | Budgets, bounded adapters, and terminal classifications prevent runaway or unsafe recovery.                                     |

No blocking Security Baseline finding remains. Resiliency Baseline is disabled. PBT-01 is addressed
in the business-logic model; PBT-02 through PBT-10 are deferred until their applicable stages.
