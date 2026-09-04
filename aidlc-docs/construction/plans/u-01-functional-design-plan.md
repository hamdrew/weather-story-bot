# U-01 Functional Design Plan

## Scope

Design the technology-agnostic domain behavior for protected office-information management, private
operational alerting, alert deduplication, structured safe observability, and alert-loop prevention.
This covers US-2.3, US-3.2, and US-4.2 through US-4.4; infrastructure resources, IAM policies,
runtime composition, and code are deferred to their applicable stages.

## Design Checklist

- [x] Model the protected office-information and operational-alert workflows.
- [x] Define U-01 domain entities, value objects, states, and relationships.
- [x] Define validation, authorization, deduplication, fallback, redaction, and failure rules.
- [x] Define safe input/output data flows and integration contracts.
- [x] Identify applicable testable properties for PBT-01 and preserve them for Code Generation.
- [x] Validate requirements, story, unit, Security Baseline, and PBT traceability.

## Functional Design Questions

### Question 1: Business Logic Modeling

How should alerting model an operational event before delivery?

**Recommendation: A.** A classified safe event separates detection from notification and lets the
fingerprint/cooldown policy suppress duplicate notifications while metrics continue.

A) **Recommended** — Normalize every eligible signal into a bounded classified operational event,
then apply fingerprint, cooldown, aggregation, and delivery decisions

B) Let each handler independently format and send alert text without a shared event model

C) Persist every raw upstream failure and format it only when an alert is sent

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Domain Model

What identity should define an alert fingerprint?

**Recommendation: A.** Environment, workflow, stable failure class, and optional office scope
provide meaningful four-hour deduplication without embedding private identifiers or unbounded text.

A) **Recommended** — Use environment, workflow, stable failure class/code, and optional office ID;
exclude tokens, chat/message IDs, URLs, raw messages, and arbitrary exception text

B) Fingerprint the rendered Telegram alert text

C) Use one global fingerprint for every alert in an environment

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Business Rules

When should private-alert fallback be attempted?

**Recommendation: A.** The approved requirements call for exactly one separate SNS/email fallback
only after a definitive alert-delivery failure; this avoids loops and does not treat an ambiguous
outcome as proof of non-delivery.

A) **Recommended** — Attempt the fallback once only after a definitive private-Telegram alert
failure; never route fallback or dispatcher failures back to the alert trigger

B) Attempt fallback for every alert alongside Telegram delivery

C) Retry ambiguous Telegram alert results indefinitely before fallback

X) Other (please describe after the `[Answer]:` tag below)

### Question 4: Data Flow

How should office-information refresh obtain and persist current office data?

**Recommendation: A.** The requirement calls for current NWS office/region data and one
conditionally updated current office record, preventing stale managed-message references or an
unapproved audit/snapshot history.

A) **Recommended** — Retrieve and validate current NWS office/region data for an authorized
request, then conditionally update only `OFFICE#{office_id}/CURRENT` after message/pin verification

B) Reuse cached office data without an NWS retrieval

C) Create a new immutable office snapshot for every refresh before Telegram work

X) Other (please describe after the `[Answer]:` tag below)

### Question 5: Integration Points

What external authority should be required to invoke office-information refresh?

**Recommendation: A.** A protected, on-demand command with validated caller, environment, and
office scope is consistent with the existing reconciliation boundary and keeps it separate from
scheduled story publication.

A) **Recommended** — Require a validated protected operator command; reject scheduler events,
cross-environment targets, and commands that request story publication

B) Permit every publisher scheduler invocation to refresh office information

C) Expose a public unauthenticated HTTP endpoint for refreshes

X) Other (please describe after the `[Answer]:` tag below)

### Question 6: Error Handling

What should happen when a required office-information step fails?

**Recommendation: A.** Failing closed preserves the managed-message contract: do not write a new
current reference, trigger a bounded alert, and leave the schedule disabled rather than claiming a
verified managed state.

A) **Recommended** — Do not commit office references; emit a safe alert; leave the office schedule
disabled; return a classified failure after durable safe state is recorded

B) Commit any successfully created invite/message reference even when pin verification fails

C) Enable the schedule so the next publisher run can repair the office information

X) Other (please describe after the `[Answer]:` tag below)

### Question 7: Business Scenarios

How should repeated successful office-information refreshes behave?

**Recommendation: A.** The managed message should be idempotent: conditional current-state update
and create-or-edit behavior prevent duplicate messages and preserve exactly one verified pin.

A) **Recommended** — Reuse or edit one managed message and conditionally update the current record;
repeated equivalent refreshes do not create another message or audit/snapshot record

B) Create and pin a new information message for every refresh

C) Skip conditional state checks whenever an existing message reference is present

X) Other (please describe after the `[Answer]:` tag below)

## Evaluated Non-Applicable Category

- Frontend Components: N/A. U-01 exposes protected Lambda/adapter contracts and no browser or
  client UI.

## Extension Constraints

- SECURITY-01 through SECURITY-15 are enforced where applicable. U-01 must validate all external
  inputs, protect private identifiers/secrets, preserve least privilege and secure defaults, emit
  allowlisted logs, and fail closed. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A.
- PBT-01 is mandatory for U-01: the generated Functional Design must identify testable properties
  for its deterministic transformations and stateful alert lifecycle, or record a specific N/A
  rationale per component. PBT-02 through PBT-10 are not yet enforced at this stage.
- Resiliency Baseline is disabled.
