# U-01 Business Logic Model

## Office-Information Refresh Workflow

1. Accept a protected on-demand command and validate caller authorization, target environment,
   office scope, and command shape before external work.
2. Reject scheduler-shaped events, cross-environment commands, inactive or unconfigured office IDs,
   and any request that includes story-publication behavior.
3. Retrieve current NWS office/region data, validate it into `CurrentOfficeProfile`, and classify
   invalid or missing required data without retaining raw upstream bodies.
4. At the protected Telegram boundary, create or reuse the channel invite; render the explicit-entity
   information message; then create or edit the one managed message.
5. Pin the managed message and independently verify the pin before considering the message current.
6. Conditionally write new opaque message/invite references and refreshed safe metadata to the one
   current office record. A failed conditional write is a failure, not permission to overwrite.
7. On success, return a safe `refreshed` or `unchanged` result and record allowlisted logs and
   metrics. Those signals may later cause a CloudWatch alarm transition; the workflow does not send
   an alert directly.
8. On a required-step failure, do not commit new office references, leave the office schedule
   disabled, return a classified safe failure, and emit only bounded logs and metrics. It never
   creates a story publication attempt, office audit record, or office snapshot.

## CloudWatch Alarm Notification Workflow

1. The alert-notification boundary accepts only a bounded CloudWatch alarm state-transition
   notification received from the dedicated SNS trigger path.
2. Validate notification source, schema/version, alarm identity, target environment, state, and
   bounded safe fields before rendering. Reject malformed, cross-environment, unrecognized, or
   non-actionable notifications without forwarding them.
3. CloudWatch's M-of-N evaluation, explicit missing-data treatment, optional composite suppression,
   and alarm history determine whether a notification exists. U-01 does not derive fingerprints,
   maintain cooldowns or aggregations, or persist alert delivery state.
4. Render one bounded redacted private Telegram alert from the accepted alarm transition and safe
   run/reconciliation context. No raw payload, secret, private destination, URL, or unbounded error
   text enters the rendered message.
5. Attempt one private Telegram delivery and classify its outcome as `acknowledged`,
   `definitive_failure`, or `ambiguous`.
6. On acknowledgement, record safe dispatch observation. On an ambiguous outcome, record bounded
   ambiguity logs and metrics but neither resend nor invoke fallback.
7. On a definitive Telegram-delivery failure, invoke the separate SNS/email fallback once and
   record its safe outcome.
8. Rendering, dispatcher, and fallback failures terminate locally with safe observations. None may
   publish to the trigger topic, create another alert notification, or invoke another fallback.

## Structured Observation Workflow

1. Each U-01 boundary submits a `SafeLogEvent` candidate.
2. The sanitizer drops unsupported fields, classifies errors, bounds strings and counts, and rejects
   secret-bearing/private identifiers, raw bodies, headers, unbounded exception text, URLs, story
   content, S3 keys, and Telegram chat/message identifiers.
3. The schema validates the remaining allowlisted event shape and emits the safe log/metric record.
4. DEBUG adds only approved boundary timing, validation, retry-budget, and alarm-state information
   in permitted environments. It never enables protected values or raw exception data.

## Business Outcomes

| Workflow           | Successful outcome                                               | Controlled non-success outcome                                                           |
| ------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Office refresh     | One verified pinned message and conditionally current references | Safe failure, no reference commit, schedule disabled, bounded metrics/logs only          |
| Alarm notification | One redacted private alert for an accepted actionable transition | Rejection, recorded ambiguity, one definitive-failure fallback, or terminal safe failure |
| Observation        | Allowlisted bounded log/metric event                             | Sensitive/invalid field is dropped or causes a safe boundary failure                     |
