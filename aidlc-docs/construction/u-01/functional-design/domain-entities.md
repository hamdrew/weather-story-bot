# U-01 Domain Entities

## Protected Office-Information Entities

| Entity                            | Meaning                                                                               | Required invariants                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `OfficeInformationRefreshCommand` | An authorized request to refresh one configured office's managed information message. | Contains a validated environment, office ID, caller authorization context, and correlation ID; cannot request story publication.  |
| `CurrentOfficeProfile`            | The validated current NWS office/region facts used for message rendering.             | Required fields are present and bounded; coordinates are never rendered in the message.                                           |
| `ManagedOfficeMessage`            | Opaque managed-message reference plus verified pin status.                            | There is at most one current managed message per office; private message and chat identifiers never leave the protected boundary. |
| `InviteReference`                 | Opaque current channel-invite reference.                                              | It is create-or-reuse only at the protected Telegram boundary and is never logged, returned, or stored in public evidence.        |
| `OfficeRefreshResult`             | Safe outcome of a refresh request.                                                    | Is one of `refreshed`, `unchanged`, `rejected`, or `failed`; carries only safe correlation and classification data.               |

`OFFICE#{office_id}/CURRENT` remains the sole mutable office record. It may be conditionally updated
only after NWS validation, message create/edit, pin verification, and optimistic-current-state checks
succeed. No office audit or snapshot entity exists.

## Operational Alert Entities

| Entity                  | Meaning                                                     | Required invariants                                                                                                                                           |
| ----------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OperationalEvent`      | Normalized, bounded signal eligible for alert policy.       | Has environment, workflow, stable severity, failure class/code, timestamp, optional office ID, and safe context only.                                         |
| `AlertFingerprint`      | Canonical identity for deduplication.                       | Derived only from environment, workflow, stable failure class/code, and optional office ID; excludes text, raw errors, URLs, tokens, and private IDs.         |
| `AlertFingerprintState` | Current cooldown and aggregation facts for one fingerprint. | Contains last dispatch time, suppressed count, aggregation count, and latest safe event summary; updates are atomic.                                          |
| `AlertDecision`         | Policy result before a notification attempt.                | Is `dispatch`, `suppress`, or `metric_only`; a suppressed event still permits metrics and safe logs.                                                          |
| `AlertDispatchOutcome`  | Classified notification result.                             | Is `acknowledged`, `definitive_failure`, or `ambiguous`; only definitive failure permits one fallback attempt.                                                |
| `SafeLogEvent`          | Allowlisted structured diagnostic event.                    | Has timestamp, level, type, component, safe IDs, classification, bounded summary, latency/retry/counts as applicable; never has raw request/response content. |

## Relationships

- One `OperationalEvent` deterministically derives one `AlertFingerprint`.
- One `AlertFingerprint` owns at most one mutable `AlertFingerprintState`.
- One `AlertFingerprintState` yields one `AlertDecision` per event evaluation.
- A `dispatch` decision yields at most one private Telegram attempt and, only after a definitive
  failure, at most one independent fallback attempt.
- An `OfficeInformationRefreshCommand` produces one `OfficeRefreshResult`; it never produces a
  Weather Story publication reservation, attempt, or run record.

## State Models

### Alert Fingerprint State

`new` → `eligible` → `dispatched` → `cooling_down` → `eligible`

- A new event creates or atomically observes state.
- A dispatch records `dispatched` before or with the safe outcome facts required to prevent duplicate
  notification decisions.
- Events inside the four-hour cooldown enter `cooling_down`, increment bounded aggregation facts,
  and continue metrics/logging without another notification.
- An ambiguous private-alert result is recorded as ambiguous; it is not evidence of non-delivery and
  does not trigger fallback.

### Office Information Refresh State

`authorized` → `profile_validated` → `message_verified` → `pin_verified` → `current_committed`

Any validation, Telegram-management, pin-verification, or conditional-write failure transitions to
`failed`. A failed refresh never advances the current office references and requires a safe alert;
the office schedule remains disabled.

## Testable Properties (PBT-01)

| Component                  | Category                          | Property to carry to Code Generation                                                                                                                                       |
| -------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fingerprint derivation     | Idempotence, invariant            | Canonicalizing an already canonical fingerprint is unchanged; identical safe identity inputs yield identical fingerprints, and changing excluded fields cannot change it.  |
| Safe sanitizer/schema      | Idempotence, invariant            | Sanitizing twice equals sanitizing once; output contains only allowed keys, bounded values, and no forbidden sensitive patterns.                                           |
| Alert rendering            | Invariant                         | Rendered alert text is at most 3,500 grapheme clusters and contains only the approved safe fields.                                                                         |
| Cooldown policy            | Stateful model-based              | Random valid sequences of events/time advances match a simple fingerprint-state model after every command; no sequence yields more than one dispatch per four-hour window. |
| Office-information refresh | Stateful model-based, idempotence | Repeated equivalent successful commands retain one managed message/current reference and do not create publication attempts or office snapshots.                           |
| Telegram entity rendering  | Invariant                         | Explicit entities have valid UTF-16 offsets and no untrusted input selects a formatting mode or executable markup.                                                         |

No round-trip or oracle property is currently identified for U-01: it has no logical inverse
serialization operation and no independent known-correct implementation. This rationale must be
revisited if a reversible format or reference policy implementation is introduced.
