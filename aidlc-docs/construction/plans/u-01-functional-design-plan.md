# U-01 Functional Design Reconciliation Plan

## Scope

Regenerate the technology-agnostic U-01 design for protected office-information management,
CloudWatch-alarm-driven private alert dispatch, definitive-failure-only fallback, safe
observability, and notification-loop prevention. This supersedes the prior design's removed
DynamoDB alert fingerprint, cooldown, aggregation, and delivery-state model. It covers US-2.3,
US-3.2, and US-4.2 through US-4.4; infrastructure, IAM policy, Lambda composition, and code remain
for their applicable stages.

## Approved Decisions Applied Without New Questions

The governing requirements resolve every decision that affects this functional-design boundary:

- CloudWatch alarm state transitions are the only operator-notification trigger. U-01 must not
  model a direct application alert-event path, SQS, or custom persisted alert state.
- CloudWatch M-of-N evaluation, explicit missing-data treatment, optional composite alarms, and
  alarm history provide notification-noise reduction.
- The alert-notification Lambda receives the bounded alarm transition, renders one redacted private
  Telegram alert, and invokes one separate SNS/email fallback only after definitive delivery
  failure. Ambiguous delivery is observed without resend or fallback; no failure may loop back to
  the trigger topic.
- Office refresh remains an authorized on-demand operation: it validates caller/environment/office,
  retrieves and validates current NWS data, creates or edits and verifies one pin, conditionally
  updates the current office record, and leaves the schedule disabled on failure.

No additional decision is ambiguous enough to need a `[Answer]:` question. Frontend Components are
N/A because U-01 has only protected Lambda and adapter contracts.

## Regeneration Checklist

- [x] Model the protected office-information workflow and its failure-closed transitions.
- [x] Model the bounded CloudWatch alarm-transition dispatcher and non-recursive fallback workflow.
- [x] Define U-01 domain entities, value objects, states, and relationships without custom alert
      fingerprint, cooldown, aggregation, or delivery-state entities.
- [x] Define authorization, validation, redaction, safe-observation, ambiguity, fallback, and
      failure rules.
- [x] Define safe input/output data flows and narrow integration contracts for NWS, Telegram,
      CloudWatch/SNS, durable current-office state, and observability.
- [x] Identify applicable PBT-01 properties and explicit N/A rationales; preserve them for Code
      Generation.
- [x] Validate traceability to US-2.3, US-3.2, US-4.2 through US-4.4, FR-03, FR-06 through FR-09,
      NFR-03, NFR-04, NFR-07, NFR-08, SECURITY-01 through SECURITY-15, and PBT-01.

## Extension Compliance Plan

- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, SECURITY-08 through SECURITY-15 apply to
  U-01's boundary design and must be explicitly evaluated. SECURITY-02, SECURITY-04, and
  SECURITY-07 are N/A because this architecture has no network intermediary, HTML endpoint, or
  customer-managed network configuration.
- PBT-01 applies: identify meaningful invariant, idempotence, bounded-transformation, and stateful
  model properties for the office-refresh and safe-rendering/sanitization paths. Record a rationale
  for any PBT category that is not meaningful; PBT-02 through PBT-10 are deferred by the stage
  matrix.
- Resiliency Baseline is disabled.
