# U-01 Business Rules

## Authorization and Office Information

1. Office-information refresh is on-demand and protected; it accepts only an authorized command for
   the configured environment and in-scope office.
2. Scheduler events and requests to publish a Weather Story are always rejected by this service.
3. Dev Telegram management is mock-only. A real destination cannot be substituted across
   environments.
4. Current NWS office/region facts must validate before invite/message work; required missing data
   fails closed.
5. Message creation/edit and pin verification are both required before conditional current-record
   commit. Partial success never commits an unverified reference.
6. Equivalent successful refreshes reuse or edit the single managed message and retain one current
   reference. They create neither duplicate messages nor office audit/snapshot records.
7. A required-data, Telegram-management, pin-verification, or conditional-write failure returns a
   classified safe failure, leaves the office schedule disabled, and records bounded logs/metrics.
   Operator notification can occur only through a later CloudWatch alarm transition.
8. Invite links and Telegram tokens/private identifiers are opaque protected-boundary values. They
   never appear in logs, outputs, fixtures, documentation, captions, or public evidence.

## CloudWatch Alarm Dispatch and Fallback

1. Only a validated CloudWatch alarm state-transition notification received via the dedicated SNS
   trigger is eligible for private operator notification. Application components never directly
   invoke the dispatcher with operational events.
2. Alarm identity, source, schema/version, environment, state, and safe context must validate before
   rendering or delivery. Cross-environment, malformed, unknown, and non-actionable notifications
   fail closed.
3. CloudWatch M-of-N evaluation, explicit missing-data treatment, optional composite suppression,
   and alarm history are the sole notification-noise-reduction mechanism. No custom fingerprint,
   cooldown, aggregation, DynamoDB alert record, or alert-delivery state exists.
4. One accepted alarm transition authorizes at most one private Telegram delivery attempt.
5. Fallback occurs once only after definitive private Telegram-delivery failure. Ambiguous delivery
   is not definitive failure and receives neither automatic resend nor fallback.
6. Fallback, dispatcher, rendering, and notification-validation failures cannot publish to the
   trigger topic, invoke another private alert, or invoke fallback again.
7. Private alert text is bounded and contains only approved safe alarm identity/state, severity,
   event time, and safe run/reconciliation context.

## Logging and Error Handling

1. U-01 log events may include timestamp, level, type, component, safe office/run/attempt/revision
   correlations, alarm identity/state, classification, status, bounded sanitized summary, latency,
   retry data, and aggregate counts only when applicable.
2. Log events must exclude secrets, token-bearing URLs, headers, raw request/response bodies, raw
   stack traces, story/image content, S3 keys, Telegram chat/message identifiers, and unbounded
   upstream errors.
3. Production rejects DEBUG. Dev/staging may use DEBUG only for approved allowlisted additions.
4. Unexpected boundary exceptions become safe classified logs and metrics; they do not bypass
   authorization, pin verification, CloudWatch-only notification triggering, or loop prevention.

## Security Compliance

| Rule        | Status              | U-01 application                                                                                                                   |
| ----------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| SECURITY-01 | Compliant by design | Later infrastructure design must enforce encrypted state and TLS; U-01 contracts require protected transport-boundary values only. |
| SECURITY-02 | N/A                 | No network intermediary is in the approved architecture.                                                                           |
| SECURITY-03 | Compliant by design | Every boundary emits only centralized, structured, allowlisted safe events.                                                        |
| SECURITY-04 | N/A                 | The service has no HTML-serving endpoint.                                                                                          |
| SECURITY-05 | Compliant by design | Protected commands, NWS profiles, and alarm notifications have typed, bounded validation before use.                               |
| SECURITY-06 | Compliant by design | Narrow adapter contracts preserve least-privilege implementation boundaries for the Infrastructure Design stage.                   |
| SECURITY-07 | N/A                 | No customer-managed network configuration is planned.                                                                              |
| SECURITY-08 | Compliant by design | Protected refresh denies by default and verifies caller, environment, and office scope.                                            |
| SECURITY-09 | Compliant by design | Safe generic outcomes and no default destination/credential behavior are required.                                                 |
| SECURITY-10 | Compliant by design | Integrity/supply-chain implementation is assigned to later infrastructure and delivery units; no unsafe bypass is introduced.      |
| SECURITY-11 | Compliant by design | Protected and notification boundaries have explicit trust, validation, and loop-prevention controls.                               |
| SECURITY-12 | Compliant by design | Tokens and private identifiers remain opaque and must come from the approved secret boundary.                                      |
| SECURITY-13 | Compliant by design | Untrusted notifications and upstream data are schema-validated; conditional state transitions preserve integrity.                  |
| SECURITY-14 | Compliant by design | Safe logs and metrics support CloudWatch alarms; application code cannot delete audit records.                                     |
| SECURITY-15 | Compliant by design | External calls are bounded, classified, fail closed, and terminate without recursive notification.                                 |

## Traceability

- US-4.4: Authorization and Office Information rules 1-8.
- US-4.2: CloudWatch Alarm Dispatch and Fallback rules 1-7.
- US-4.3 and US-7.4: Logging and Error Handling rules 1-4.
- US-2.3 and US-3.2: protected failure/reconciliation observations that reach operators only through
  the CloudWatch alarm path.
- FR-03, FR-06 through FR-09; NFR-03, NFR-04, NFR-07, and NFR-08.
