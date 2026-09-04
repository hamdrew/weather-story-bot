# U-01 Non-Functional Requirements

## Scalability and Capacity

1. Alert decisions shall be independent per canonical fingerprint and use atomic state updates.
2. The service shall retain only bounded aggregation/cooldown facts for a fingerprint and shall
   continue metrics for suppressed equivalent events.
3. U-01 shall not introduce a queue, separately deployable alert service, scan-based state access,
   or unbounded diagnostic retention.

## Performance

1. Every NWS, Telegram, SNS, pin-verification, and state interaction shall have a bounded deadline
   within the invoking Lambda execution budget.
2. Office refresh and alert dispatch shall return a classified safe outcome rather than wait
   indefinitely for an external acknowledgement.
3. Private alert rendering shall be bounded to 3,500 grapheme clusters before an outbound attempt.

## Availability and Reliability

1. Fingerprint state shall persist safe cooldown, suppression, aggregation, and delivery facts so a
   later invocation can make an objective decision after interruption.
2. One independent fallback attempt is permitted only after definitive private-Telegram alert
   failure. Ambiguous delivery is recorded and does not cause a resend or fallback.
3. Fallback, dispatcher, and rendering failures shall terminate locally and cannot create a
   notification loop or publish to the public channel.
4. Required office-information failure shall leave the schedule disabled, avoid current-reference
   commit, emit a safe alert, and return a classified failure.

## Security and Privacy

1. Commands, profiles, events, and output results shall be validated typed bounded models.
2. Diagnostics and operator results shall permit only allowlisted safe fields; secrets, private
   Telegram identifiers, invite links, raw bodies, headers, token-bearing URLs, raw stack traces,
   and unbounded exceptions are prohibited.
3. Protected operations shall deny by default for caller, environment, office, command, resource,
   or state mismatch. Dev Telegram management shall remain mock-only.
4. Production shall reject DEBUG. Dev/staging DEBUG is limited to the approved safe diagnostic
   additions and never changes the data-protection rule.

## Maintainability and Operator Usability

1. Safe event/configuration models, event classifications, and interfaces shall be versioned and
   documented. New fields require validation and tests rather than arbitrary mappings.
2. U-01 shall expose narrow ports and explicit boundary contracts; Lambda handlers shall not contain
   domain policy or direct unbounded diagnostic handling.
3. Protected outcomes shall return a bounded status, safe correlation ID, classification, and
   next-action guidance. Sensitive facts remain available only through authorized operational paths.
4. Focused example tests document critical scenarios; property tests cover the Functional Design
   invariants with reusable domain strategies.

## Acceptance Evidence

| Requirement area          | Evidence                                                                                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cooldown/capacity         | Deterministic unit and stateful property tests show one dispatch per fingerprint window, bounded aggregation, and ongoing metrics.                                    |
| Performance/reliability   | Tests inject timeout, definitive failure, ambiguity, fallback failure, and interruption outcomes and assert classified, loop-free results.                            |
| Security/privacy          | Tests assert schema rejection/sanitization, no forbidden values in logs/results, dev mock-only behavior, and production DEBUG rejection.                              |
| Office information        | Tests assert authorization, required-data validation, one managed message, pin verification, conditional commit, no story attempts, and disabled schedule on failure. |
| Maintainability/usability | Strict typing, Ruff, mypy, focused examples, Hypothesis strategies, and safe operator-result tests pass through `make check`.                                         |

## Traceability

These requirements support US-2.3, US-3.2, and US-4.2 through US-4.4, plus FR-03, FR-06, FR-07,
FR-08, FR-09, FR-10, FR-13, NFR-01 through NFR-04, NFR-07, and NFR-08.

## Security Compliance

SECURITY-01 through SECURITY-15 are compliant by these requirements where applicable. SECURITY-02,
SECURITY-04, and SECURITY-07 are N/A because U-01 introduces no network intermediary, HTML endpoint,
or customer-managed network. No blocking security finding remains.
