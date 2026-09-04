# U-01 Non-Functional Requirements

## Scalability and Capacity

1. CloudWatch owns alarm evaluation and notification noise reduction through M-of-N evaluation,
   explicit missing-data treatment, optional composite alarms, and alarm history. U-01 shall not
   create a queue, custom fingerprint/cooldown/aggregation policy, alert record, or separately
   deployable alert service.
2. The alert-notification Lambda shall process one validated alarm transition at a time with bounded
   safe input and rendering. Rejected, malformed, or non-actionable transitions consume no Telegram
   or fallback attempt.
3. U-01 logs, metrics, alert renderings, NWS profiles, and operator results shall remain explicitly
   bounded; no scan-based alert-state access or unbounded diagnostic retention is permitted.

## Performance

1. Every NWS, Telegram, SNS, pin-verification, and current-record interaction shall have an explicit
   bounded deadline within its invoking Lambda execution budget.
2. Office refresh and alarm dispatch shall return a classified safe outcome rather than wait
   indefinitely for external acknowledgement.
3. Private-alert rendering shall enforce a defined bounded length before any outbound attempt;
   implementation shall set the exact limit no higher than the Telegram API limit and test it.

## Availability and Reliability

1. CloudWatch alarm history, logs, metrics, SNS evidence, and existing safe run/reconciliation facts
   are the approved alert evidence. U-01 does not persist custom alert delivery, cooldown, or
   aggregation facts.
2. One independent fallback attempt is permitted only after definitive private-Telegram alert
   failure. Ambiguous delivery is observed and measured without automatic resend or fallback.
3. Fallback, dispatcher, and rendering failures shall terminate locally and cannot create a
   notification loop, publish to the public channel, or return to the trigger topic.
4. Required office-information failure shall leave the schedule disabled, avoid current-reference
   commit, record safe logs/metrics, and return a classified failure. A later CloudWatch alarm
   transition is the only path to operator notification.

## Security and Privacy

1. Commands, profiles, alarm transitions, and output results shall be validated typed bounded models.
2. Diagnostics and operator results shall permit only allowlisted safe fields; secrets, private
   Telegram identifiers, invite links, raw bodies, headers, token-bearing URLs, raw stack traces,
   and unbounded exceptions are prohibited.
3. Protected operations shall deny by default for caller, environment, office, command, resource, or
   state mismatch. Dev Telegram management shall remain mock-only.
4. Production shall reject DEBUG. Dev/staging DEBUG is limited to approved safe diagnostic additions
   and never changes the data-protection rule.

## Maintainability and Operator Usability

1. Safe event/configuration models, alarm classifications, and interfaces shall be versioned and
   documented. New fields require validation and tests rather than arbitrary mappings.
2. U-01 shall expose narrow ports and explicit boundary contracts; Lambda handlers shall not contain
   domain policy or direct unbounded diagnostic handling.
3. Protected outcomes shall return a bounded status, safe correlation ID, classification, and
   next-action guidance. Sensitive facts remain available only through authorized operational paths.
4. Focused example tests document critical scenarios; property tests cover Functional Design
   invariants with reusable domain strategies.

## Acceptance Evidence

| Requirement area          | Evidence                                                                                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CloudWatch capacity       | Tests show only validated actionable alarm transitions render a private alert; no direct application alert path, custom state, or queue is reachable.                 |
| Performance/reliability   | Tests inject timeout, definitive failure, ambiguity, fallback failure, and malformed alarm outcomes and assert bounded, classified, loop-free results.                |
| Security/privacy          | Tests assert schema rejection/sanitization, no forbidden values in logs/results, dev mock-only behavior, and production DEBUG rejection.                              |
| Office information        | Tests assert authorization, required-data validation, one managed message, pin verification, conditional commit, no story attempts, and disabled schedule on failure. |
| Maintainability/usability | Strict typing, Ruff, mypy, focused examples, Hypothesis strategies, and safe operator-result tests pass through `make check`.                                         |

## Traceability

These requirements support US-2.3, US-3.2, and US-4.2 through US-4.4, plus FR-03, FR-06 through
FR-09, NFR-03, NFR-04, NFR-07, and NFR-08.

## Security Compliance

SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
compliant by these requirements. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A because U-01
introduces no network intermediary, HTML endpoint, or customer-managed network. No blocking security
finding remains.
