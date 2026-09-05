# U-03 Functional Design Plan

## Scope

Design technology-agnostic business behavior for staging runtime composition and the complete
SAM-managed service boundary. U-03 composes the existing publisher and U-01 protected-operation
contracts; it does not implement a deployment control plane (U-04), cost estimation (U-02), or a
remote staging mutation (separate owner-approved work).

U-03 owns remaining implementation obligations for US-1.1, US-1.3, US-2.1, US-2.2, US-3.1,
US-3.3, US-4.1, US-5.1 through US-5.3, and US-6.3. It traces to FR-01, FR-03, FR-04, FR-06,
FR-09, and FR-12 plus NFR-01 through NFR-08.

## Approved Decisions Applied Without New Questions

The approved requirements and unit dependency map resolve the relevant functional decisions:

- The composition root exclusively binds validated packaged configuration, exact environment-scoped
  resource references, secrets, clocks, identifiers, and concrete adapters. Handlers validate
  bounded events and delegate; domain services neither construct clients nor read process state.
- Dev remains mock-only. Staging is one isolated `us-east-2` environment with distinct
  destinations; production contracts remain validated but deployment and activation are deferred.
- Validated configured active-office membership and registry active state determine eligibility. No
  code, seed validation, or IAM template may require a named office.
- Publisher invocations process exactly one configured active office under a 14-minute application
  deadline. One disabled Scheduler schedule exists per active office, with no retry and a bounded
  event age. Protected office-information work has no schedule and never enables one.
- U-01 ports are bound with trusted invocation authorization, concrete NWS and Telegram management
  adapters, current-office conditional state, private alert delivery, and independent fallback
  publication. Event-supplied identities never override configured resource bindings.
- State and media controls preserve conditional/transactional behavior, current projections,
  encrypted retained resources, and no scans. Alert fingerprint, cooldown, aggregation, and
  delivery state are not persisted.
- Reproducible packaging uses pinned Python 3.13 arm64 dependencies and emits package/SBOM/scan
  evidence. U-04 consumes evidence for controlled change-set planning; U-03 neither approves nor
  executes a change set.

No unresolved business decision requires an `[Answer]:` question. The unit has no frontend
components.

## Functional-Design Checklist

- [x] Model environment runtime assembly, immutable configuration/resource bindings, and
      cold-start-safe construction failure behavior.
- [x] Model scheduled publisher event admission, active-office eligibility, execution budget, and
      safe run outcomes.
- [x] Model concrete-port binding rules for NWS retrieval, retained media, durable state, public
      Telegram publication, U-01 protected operations, private alerts, and fallback.
- [x] Model durable-state and retained-media lifecycle rules, including current projections,
      conditional transitions, cleanup boundaries, and manual PITR restore preparation.
- [x] Model SAM resource lifecycle behavior: disabled schedules, encryption/retention, scoped
      identity/secrets, observability signals, and production-contract deferral.
- [x] Define domain entities, relationships, inputs/outputs, error classifications, and prohibited
      information flows without embedding AWS implementation details.
- [x] Define business rules for isolation, least privilege, secret/private-identifier handling,
      supply-chain evidence, and owner-only remote-action authorization.
- [x] Identify applicable PBT-01 properties and explicit N/A rationales, retaining example-test
      obligations for Code Generation.
- [x] Validate traceability and applicable Security Baseline controls.

## Extension Compliance Plan

- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, SECURITY-08 through SECURITY-15 apply and
  will be evaluated in the design artifacts. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A:
  the approved architecture has no network intermediary, HTML-serving endpoint, or
  customer-managed network.
- PBT-01 applies to configuration/handler admission, active-office eligibility, bounded safe
  projection, retained-state transitions, and current-media lifecycle. Round-trip, idempotence,
  state-model, and invariant properties will be selected where meaningful; categories lacking a
  meaningful operation will receive an explicit rationale. PBT-02 through PBT-10 are deferred by
  the extension stage matrix.
- Resiliency Baseline is disabled and is not evaluated.
