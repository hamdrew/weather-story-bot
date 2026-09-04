# U-01 NFR Design Patterns

## CloudWatch Transition and Single-Fallback Pattern

CloudWatch evaluates actionable conditions using M-of-N, explicit missing-data treatment, optional
composite suppression, and alarm history. The dedicated SNS trigger supplies one bounded alarm
transition to the dispatcher. The dispatcher validates it, renders one private Telegram alert, and
classifies the single attempt. Only definitive failure permits one independent SNS/email fallback;
ambiguity, validation failure, rendering failure, dispatcher failure, and fallback failure terminate
locally without trigger-topic publication or recursive notification.

## Deadline and Bounded-Data Pattern

The office-refresh coordinator and dispatcher propagate remaining invocation time to each NWS,
Telegram, SNS, pin-verification, and state operation. They refuse operations that cannot start within
their bounded attempt allowance. Every trust boundary creates a typed bounded model, and a single
allowlisted sanitizer/schema controls logs, metrics, alerts, and operator results.

## Conditional Idempotency Pattern

Office refresh conditionally commits a verified message/pin result to one current office record.
Equivalent refreshes converge on one managed message and create neither story attempts nor snapshots.
Failure leaves the schedule disabled and emits safe logs/metrics only; CloudWatch is the sole route
to later notification.

## Acceptance and PBT Carry-Forward

| Pattern                 | Acceptance evidence                                                                                    | Property obligation                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| CloudWatch transition   | Examples cover accepted/rejected alarms, definitive failure, ambiguity, fallback, and loop prevention. | Stateful lifecycle never falls back for ambiguity, exceeds one fallback, or loops.           |
| Bounded data            | Tests reject forbidden fields and prevent an out-of-budget call.                                       | Sanitization is idempotent; accepted models and renders satisfy allowlist/bounds invariants. |
| Conditional idempotency | Tests repeat refreshes and conditional-write conflicts.                                                | Stateful office model retains one current reference and no story attempts.                   |

## Security Compliance

SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
incorporated through narrow trust boundaries, safe observations, and fail-closed behavior.
SECURITY-02, SECURITY-04, and SECURITY-07 are N/A. No blocking finding remains.
