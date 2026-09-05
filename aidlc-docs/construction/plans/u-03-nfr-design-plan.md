# U-03 NFR Design Plan

## Scope and Approved Decisions

Translate U-03 NFR Requirements into design patterns and logical components for real runtime
composition, bounded external adapters, retained state/media, safe evidence, and isolated staging.
This stage does not map components to concrete AWS resources, deploy infrastructure, enable a
schedule, or send a real Telegram message.

All NFR-design categories are resolved by approved requirements and the U-03 Functional Design:

- **Resilience:** Fail-closed assembly and admission, conditional state transitions, verified media
  commit, terminal ambiguity, disabled-by-default schedules, isolated restore preparation, and no
  notification loop.
- **Scalability and performance:** One office/invocation, 25-revision cap, 14-minute deadline,
  60-second completion reserve, and per-adapter timeout/budget propagation. Multi-office readiness
  is deferred.
- **Security:** Typed bounded inputs, immutable environment bindings, exact secret/resource scope,
  TLS/encryption, safe observations, and no event-supplied authority. No public endpoint,
  intermediary, or customer-managed network exists.
- **Logical components:** Runtime assembly, configuration admission, budget propagation, publisher
  adapter set, state/media coordinator, safe observation mapper, package-evidence assembler, and
  restore-preparation coordinator. U-01 alert/office contracts remain separately bounded.

No unresolved NFR-design decision requires an `[Answer]:` question.

## Design Checklist

- [x] Define resilience, isolation, and recovery-preparation patterns for assembly, state/media, and
      schedule lifecycle.
- [x] Define capacity, deadline, budget-propagation, and bounded-adapter patterns.
- [x] Define security, safe-observation, evidence-integrity, and authorization-boundary patterns.
- [x] Define logical components, narrow interfaces, and permitted/prohibited information flows.
- [x] Define pattern-level acceptance evidence and PBT carry-forward.
- [x] Validate Security Baseline applicability and N/A determinations.

## Extension Compliance Plan

- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 apply.
  SECURITY-02, SECURITY-04, and SECURITY-07 are N/A because the approved architecture has no
  network intermediary, HTML-serving endpoint, or customer-managed network.
- PBT-01 properties remain a Code Generation obligation. PBT-02 through PBT-10 follow their
  applicable later-stage requirements; PBT-09 selection is already compliant.
- Resiliency Baseline is disabled.
