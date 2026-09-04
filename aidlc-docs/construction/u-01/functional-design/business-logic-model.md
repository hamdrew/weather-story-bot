# U-01 Business Logic Model

## Office-Information Refresh Workflow

1. Accept a protected on-demand command and validate caller authorization, target environment,
   office scope, and command shape before external work.
2. Reject scheduler-shaped events, cross-environment commands, inactive/unconfigured office IDs,
   and any request that includes story-publication behavior.
3. Retrieve current NWS office/region data, validate it into `CurrentOfficeProfile`, and classify
   invalid/missing required data without retaining raw upstream bodies.
4. At the protected Telegram boundary, create or reuse the channel invite; render the explicit-entity
   information message; then create or edit the one managed message.
5. Pin the managed message and independently verify the pin before considering the message current.
6. Conditionally write the new opaque message/invite references and refreshed safe metadata to the
   one current office record. A failed conditional write is a failure, not permission to overwrite.
7. On success, return a safe `refreshed` or `unchanged` result and record allowlisted observation.
8. On any required-step failure, do not commit new office references; emit a classified operational
   event; leave the office schedule disabled; and return a safe failure. The workflow never creates
   a story publication attempt, office audit record, or office snapshot.

## Operational Alert Workflow

1. An application failure, protected-operation result, or monitored CloudWatch transition supplies
   a bounded classified input to the normalizer.
2. The normalizer creates an `OperationalEvent` using only allowlisted values and a stable severity:
   `critical`, `error`, or metric-only `warning`.
3. Derive the canonical fingerprint from environment, workflow, failure class/code, and optional
   office ID. Persist or update its state atomically.
4. Evaluate the four-hour cooldown. A warning becomes `metric_only`; an in-cooldown duplicate becomes
   `suppress`; otherwise it becomes `dispatch`.
5. For suppression or metric-only, emit safe logs and ongoing metrics without a Telegram attempt.
6. For dispatch, render a private alert containing only severity, fingerprint, workflow, safe failure
   summary, optional office ID, event time, and available safe run context. Enforce the 3,500-grapheme
   limit before the attempt.
7. Classify private Telegram delivery. On acknowledgement, record the safe outcome. On a definitive
   failure, invoke the separate fallback once. On an ambiguous result, record ambiguity and do not
   claim non-delivery or invoke fallback.
8. Fallback, dispatcher, and rendering failures terminate locally with safe observations; none may
   publish to the alert-trigger topic or initiate another Telegram alert.

## Structured Observation Workflow

1. Each U-01 boundary submits a `SafeLogEvent` candidate.
2. The sanitizer drops unsupported fields, classifies errors, bounds strings/counts, and rejects
   secret-bearing/private identifiers, raw bodies, headers, unbounded exception text, URLs, story
   content, S3 keys, and Telegram chat/message IDs.
3. The schema validates the remaining allowlisted event shape and emits the safe log/metric record.
4. DEBUG adds only approved boundary timing, validation, retry-budget, and deduplication decision
   information. It never enables protected values or raw exception data.

## Business Outcomes

| Workflow       | Successful outcome                                                  | Controlled non-success outcome                                                   |
| -------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Office refresh | One verified pinned message and conditionally current references    | Safe failure, alert, no reference commit, schedule disabled.                     |
| Alert policy   | One private alert per eligible fingerprint window; metrics continue | Suppression, metric-only event, definitive fallback once, or recorded ambiguity. |
| Observation    | Allowlisted bounded log/metric event                                | Sensitive/invalid field is dropped or causes a safe boundary failure.            |
