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
6. Equivalent successful refreshes reuse/edit the single managed message and retain one current
   reference. They create neither duplicate messages nor office audit/snapshot records.
7. Any required-data, Telegram-management, pin-verification, or conditional-write failure emits a
   safe alert, returns a classified failure, and leaves the office schedule disabled.
8. Invite links and Telegram tokens/private identifiers are opaque protected-boundary values. They
   never appear in logs, outputs, fixtures, documentation, captions, or public evidence.

## Alert Normalization and Deduplication

1. Alert inputs are normalized before any persistence or rendering; raw error/request/response
   bodies are discarded.
2. A fingerprint uses only environment, workflow, stable failure class/code, and optional office ID.
   Rendering text, timestamps, run IDs, arbitrary exception text, URLs, and private IDs cannot
   change its identity.
3. Fingerprint state updates are atomic. A four-hour cooldown suppresses repeat notification while
   retaining bounded aggregation and ongoing metrics.
4. `critical` and `error` may dispatch if eligible. `warning` is metric-only unless a later approved
   policy changes that classification.
5. One eligible decision authorizes at most one private Telegram alert attempt.
6. Fallback occurs once only after definitive private Telegram alert failure. Ambiguous delivery is
   not definitive failure. Fallback/dispatcher failures cannot trigger alerts or fallback again.
7. Private alert text has a 3,500-grapheme maximum and contains only the approved safe fields.

## Logging and Error Handling

1. U-01 log events may include timestamp, level, type, component, safe office/run/attempt/revision
   correlations, classification, status, bounded sanitized summary, latency, retry data, and
   aggregate counts only when applicable.
2. Log events must exclude secrets, token-bearing URLs, headers, raw request/response bodies, raw
   stack traces, story/image content, S3 keys, Telegram chat/message identifiers, and unbounded
   upstream errors.
3. Production rejects DEBUG. Dev/staging may use DEBUG only for the approved allowlisted additions.
4. Unexpected boundary exceptions become safe classified operational events; they do not bypass
   authorization, pin verification, cooldown state, or loop prevention.

## Security Compliance

| Rule                    | Status              | U-01 application                                                                                                                  |
| ----------------------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| SECURITY-01, 03, 05, 06 | Compliant by design | Validated command/profile/event models, bounded transformations, opaque protected values, and safe error boundaries.              |
| SECURITY-02, 04, 07     | N/A                 | No network intermediary, HTML endpoint, or customer-managed network is in the approved architecture.                              |
| SECURITY-08, 09, 12     | Compliant by design | Protected command authorization, environment/office scoping, deny-by-default behavior, and secure dev/mock defaults.              |
| SECURITY-10, 13         | Compliant by design | Immutable safe evidence references and verified conditional state transitions; supply-chain details remain in delivery units.     |
| SECURITY-11, 14, 15     | Compliant by design | Explicit trust boundaries, allowlisted logging/monitoring, bounded failure classification, and fail-closed/loop-free error paths. |

## Traceability

- US-4.4: Rules 1-8 in Authorization and Office Information.
- US-4.2: Alert normalization and dispatch rules 1-7.
- US-4.3 and US-7.4: Logging and Error Handling rules 1-4.
- FR-03, FR-06, FR-07, FR-08, FR-09, FR-10, FR-13; NFR-01 through NFR-04, NFR-07, and NFR-08;
  US-2.3, US-3.2, US-4.2, US-4.3, and US-4.4.
