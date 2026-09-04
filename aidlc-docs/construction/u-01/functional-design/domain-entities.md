# U-01 Domain Entities

## Protected Office-Information Entities

| Entity                            | Meaning                                                                               | Required invariants                                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `OfficeInformationRefreshCommand` | An authorized request to refresh one configured office's managed information message. | Contains a validated environment, office ID, caller authorization context, and correlation ID; cannot request story publication. |
| `CurrentOfficeProfile`            | The validated current NWS office/region facts used for message rendering.             | Required fields are present and bounded; coordinates are never rendered in the message.                                          |
| `ManagedOfficeMessage`            | Opaque managed-message reference plus verified pin status.                            | At most one current managed message exists per office; private message and chat identifiers never leave the protected boundary.  |
| `InviteReference`                 | Opaque current channel-invite reference.                                              | It is create-or-reuse only at the protected Telegram boundary and is never logged, returned, or stored in public evidence.       |
| `OfficeRefreshResult`             | Safe outcome of a refresh request.                                                    | Is `refreshed`, `unchanged`, `rejected`, or `failed`; carries only safe correlation and classification data.                     |

`OFFICE#{office_id}/CURRENT` remains the sole mutable office record. It may be conditionally updated
only after NWS validation, message create/edit, pin verification, and optimistic-current-state checks
succeed. No office audit or snapshot entity exists.

## CloudWatch Alarm Notification Entities

| Entity                      | Meaning                                                                                | Required invariants                                                                                                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CloudWatchAlarmTransition` | A bounded validated alarm state transition received through the dedicated SNS trigger. | Has an approved source, schema/version, alarm identity, environment, actionable state, timestamp, and safe context only. It never retains the raw notification body.                    |
| `PrivateAlert`              | A bounded redacted rendering of one accepted alarm transition.                         | Contains only approved alarm identity/state, severity, timestamp, and safe run/reconciliation context; excludes secrets, private identifiers, URLs, raw payloads, and unbounded errors. |
| `AlertDispatchOutcome`      | Classified result of one private-alert attempt.                                        | Is `acknowledged`, `definitive_failure`, or `ambiguous`; only definitive failure permits one fallback attempt.                                                                          |
| `FallbackOutcome`           | Classified result of the independent fallback.                                         | Is recorded only as bounded safe observation and never causes another alert or fallback.                                                                                                |
| `SafeLogEvent`              | Allowlisted structured diagnostic event.                                               | Has timestamp, level, type, component, safe IDs, classification, bounded summary, latency/retry/counts as applicable; never has raw request/response content.                           |

There is no `AlertFingerprint`, `AlertFingerprintState`, `AlertDecision`, cooldown, aggregation,
custom alert record, or persistent alert-delivery entity. CloudWatch alarm evaluation and history
retain the approved noise-reduction and evidence responsibilities.

## Relationships and State Models

- One `OfficeInformationRefreshCommand` produces one `OfficeRefreshResult`; it never produces a
  Weather Story publication reservation, attempt, or run record.
- One accepted `CloudWatchAlarmTransition` produces at most one `PrivateAlert` and one Telegram
  attempt. A definitive failure permits at most one `FallbackOutcome`.
- A rejected or ambiguous alarm transition produces safe logs and metrics only; it cannot create a
  new notification attempt.

### Office Information Refresh State

`authorized` → `profile_validated` → `message_verified` → `pin_verified` → `current_committed`

Any validation, Telegram-management, pin-verification, or conditional-write failure transitions to
`failed`. A failed refresh never advances current office references; its schedule remains disabled.

### Alarm Dispatch Lifecycle

`received` → `validated` → `rendered` → `telegram_attempted` → (`acknowledged` | `ambiguous` |
`definitive_failure` → `fallback_attempted` → `terminal`)

This is a single-notification lifecycle, not persisted alert state. Any rejection or local failure
is terminal and cannot return to `received` or publish to the trigger topic.

## Testable Properties (PBT-01)

| Component                  | Category                          | Property to carry to Code Generation                                                                                                                                                                                                         |
| -------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Safe sanitizer/schema      | Idempotence, invariant            | Sanitizing twice equals sanitizing once; output has only allowlisted keys, bounded values, and no forbidden sensitive patterns.                                                                                                              |
| Alarm-transition validator | Invariant                         | Every accepted generated transition has an approved source/schema/environment/actionable state and only bounded safe fields; all others are rejected before rendering.                                                                       |
| Private-alert renderer     | Invariant, easy verification      | Rendering contains only approved fields and remains within its defined length/format bounds; a simple allowlist/length verifier accepts every rendered result.                                                                               |
| Office-information refresh | Stateful model-based, idempotence | Random valid command sequences match a simplified one-current-record model after each step; repeating an equivalent successful command retains one managed message/current reference and creates neither publication attempts nor snapshots. |
| Telegram entity rendering  | Invariant                         | Explicit entities have valid UTF-16 offsets and no untrusted input selects a formatting mode or executable markup.                                                                                                                           |
| Alarm dispatch lifecycle   | Stateful model-based              | Generated valid result sequences match the single-notification lifecycle: no ambiguous result permits fallback, no definitive failure permits more than one fallback, and no terminal result creates a trigger-loop transition.              |

Round-trip, commutativity, oracle, and induction properties are N/A: U-01 has no reversible
formatting contract, independently reorderable business operations, separate known-correct policy
implementation, or recursive/inductive algorithm. This assessment must be revisited if one is
introduced. Example-based tests remain required for the business-critical successful refresh,
rejected command, definitive fallback, ambiguous alert, and loop-prevention scenarios.
