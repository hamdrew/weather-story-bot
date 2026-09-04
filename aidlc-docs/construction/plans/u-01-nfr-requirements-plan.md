# U-01 NFR Requirements Plan

## Scope

Assess non-functional requirements and technology decisions for U-01 Protected Runtime Operations
and Observability. This plan applies the approved single-service, mock-only dev, security, and
Property-Based Testing decisions to office-information refresh, alert dispatch, deduplication, and
safe logs/metrics.

## Assessment Checklist

- [x] Define U-01 scalability, performance, availability, security, reliability, maintainability,
      and operator-usability requirements.
- [x] Select and document U-01-compatible technologies and testing framework decisions.
- [x] Confirm PBT-09 framework selection and downstream PBT reproducibility obligations.
- [x] Define measurable acceptance evidence and traceability.
- [x] Validate Security Baseline applicability and N/A determinations.

## NFR Questions

### Question 1: Scalability Requirements

How should U-01 handle a burst of equivalent operational events?

**Recommendation: A.** Atomic per-fingerprint state and bounded aggregation preserve the four-hour
deduplication contract without requiring an unapproved queue or separate service.

A) **Recommended** — Use atomic per-fingerprint decisions with bounded aggregation; continue safe
metrics while suppressing duplicate notifications and do not add a queue

B) Queue every event for separate asynchronous alert delivery

C) Send every event immediately regardless of cooldown state

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Performance Requirements

What performance boundary should U-01 enforce for protected operations and alert dispatch?

**Recommendation: A.** Each external interaction already requires a bounded deadline; the service
must fail safely within its handler budget rather than wait indefinitely for NWS, Telegram, SNS, or
pin verification.

A) **Recommended** — Apply bounded per-operation deadlines and return a classified safe outcome
within the invoking Lambda's configured execution budget

B) Retry external calls without a time budget until they succeed

C) Treat office refresh and alert delivery as latency-unbounded best-effort work

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Availability Requirements

What availability/recovery approach should apply when private alert delivery is unavailable?

**Recommendation: A.** The approved design has one bounded SNS/email fallback and durable safe
fingerprint state; it deliberately does not introduce cross-Region replication or notification loops.

A) **Recommended** — Record the classified outcome durably, use one independent fallback after
definitive Telegram failure, and rely on later eligible events/recovery procedures rather than loops

B) Add cross-Region alert replication now

C) Retry indefinitely until the private Telegram alert is acknowledged

X) Other (please describe after the `[Answer]:` tag below)

### Question 4: Security Requirements

Which data-protection rule should govern U-01 diagnostics and operator results?

**Recommendation: A.** An allowlisted bounded schema implements the approved redaction and
least-data requirements while retaining safe correlation needed for operations.

A) **Recommended** — Permit only validated allowlisted safe fields; drop/reject secrets, private
Telegram identifiers, invite links, raw bodies, token-bearing URLs, and unbounded exceptions

B) Log full request/response payloads only at DEBUG for troubleshooting

C) Encrypt raw diagnostic payloads and retain them with normal logs

X) Other (please describe after the `[Answer]:` tag below)

### Question 5: Tech Stack Selection

Which technology approach should U-01 use?

**Recommendation: A.** It preserves the existing Python 3.13, Pydantic, typed-port, AWS Lambda,
CloudWatch/SNS, and Hypothesis foundations without adding a second runtime or test framework.

A) **Recommended** — Use existing Python 3.13/Pydantic typed models and ports, AWS Lambda adapters,
CloudWatch/SNS integrations, and Hypothesis with pytest for properties

B) Add a separate alert microservice and a second property-testing framework

C) Implement untyped dictionaries and ad hoc print logging to minimize dependencies

X) Other (please describe after the `[Answer]:` tag below)

### Question 6: Reliability Requirements

How should U-01 treat ambiguous private-alert delivery outcomes?

**Recommendation: A.** Ambiguity is not evidence of non-delivery; recording it without fallback or
automatic resend prevents duplicate private alerts and preserves objective state.

A) **Recommended** — Persist a safe ambiguous outcome, emit metrics/logs, and do not retry or invoke
fallback automatically

B) Treat every ambiguous outcome as definitive failure and immediately use fallback

C) Repeatedly resend private alerts until acknowledgement

X) Other (please describe after the `[Answer]:` tag below)

### Question 7: Maintainability Requirements

How should U-01 preserve supportability as alert classes and office fields evolve?

**Recommendation: A.** Versioned typed schemas, explicit classifications, narrow ports, and
deterministic tests make additions reviewable while preventing unbounded diagnostic-field growth.

A) **Recommended** — Version and validate safe event/configuration models; use narrow ports,
documented classifications, focused examples, and reusable Hypothesis strategies

B) Permit arbitrary new event fields and error strings without schema updates

C) Centralize all U-01 logic in Lambda handlers without domain contracts or tests

X) Other (please describe after the `[Answer]:` tag below)

### Question 8: Usability Requirements

What operator-facing result should protected U-01 operations return?

**Recommendation: A.** A short safe correlation and classified outcome lets the sole
Owner/Operator/Maintainer act without exposing invite links, private IDs, or raw diagnostics.

A) **Recommended** — Return a bounded status, safe correlation ID, classification, and next-action
guidance; retain sensitive details only behind authorized operational access

B) Return the full Telegram response, invite link, and current private identifiers to the caller

C) Return no result or status from protected operations

X) Other (please describe after the `[Answer]:` tag below)

## Extension Constraints

- SECURITY-01 through SECURITY-15 remain enforced where applicable; SECURITY-02, SECURITY-04, and
  SECURITY-07 remain N/A under the approved architecture.
- PBT-09 is mandatory at this stage. Hypothesis is the selected Python framework and must remain a
  declared development dependency integrated with pytest, custom strategies, shrinking, and
  reproducible failure reporting. PBT-01 properties from U-01 Functional Design remain binding for
  Code Generation.
- Resiliency Baseline is disabled.
