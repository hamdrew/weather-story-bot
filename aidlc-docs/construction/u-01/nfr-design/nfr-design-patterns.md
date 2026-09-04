# U-01 NFR Design Patterns

## Classified Outcome and Single-Fallback Pattern

Every outbound private alert is classified as `acknowledged`, `definitive_failure`, or `ambiguous`.
The policy grants at most one Telegram attempt for an eligible decision. Only a definitive failure
permits one fallback SNS/email request. Ambiguous delivery is recorded as objective uncertainty and
does not permit a resend or fallback. Any fallback, renderer, or dispatcher failure terminates in a
safe observation and cannot re-enter the alert trigger path.

## Hybrid Alert-Suppression Pattern

- For CloudWatch-originated conditions, use CloudWatch alarm state-transition actions as the first
  suppression layer: a condition that persists in `ALARM` does not repeatedly invoke alarm actions.
- Use M-of-N alarm evaluation, explicit missing-data treatment, and composite/suppressor alarms only
  for alarm-condition noise reduction or declared maintenance/dependency suppression.
- For application-originated, protected-operation, Telegram-outcome, and cross-source events, derive
  a canonical application fingerprint and use an atomic four-hour cooldown state transition.
- The application layer remains the source of truth for bounded aggregation and safe outcome history;
  CloudWatch state is never treated as a general replacement for per-office/workflow fingerprints.

## Deadline-Propagation Pattern

The coordinator receives an invocation deadline and passes only remaining bounded time to each NWS,
Telegram, SNS, pin-verification, and state boundary. Before a new external action, it verifies that
the remaining budget meets the minimum configured attempt allowance. Insufficient time produces a
classified safe failure/deferral; no adapter may silently use an unlimited default timeout.

## Trust-Boundary and Data-Minimization Pattern

1. Validate commands and external data into typed bounded models at entry boundaries.
2. Convert protected identifiers and invite references to opaque values that cannot appear in normal
   output contracts.
3. Persist only safe state fields required for decision, cooldown, aggregation, and authorized
   correlation.
4. Pass all observations through one allowlisted sanitizer/schema before logs, metrics, alerts, or
   operator results. Re-sanitization is idempotent.
5. Reject or drop forbidden values before rendering/persistence; raw payloads are never an internal
   convenience representation.

## Conditional Idempotency Pattern

Office refresh reads the current office revision/reference, executes the required protected work,
then conditionally commits the verified result. Repeated equivalent refreshes converge on one managed
message/current record and do not create office snapshots or story publication attempts. A failed
condition prevents overwrite and returns a classified result for reconciliation.

## Pattern Acceptance and PBT Carry-Forward

| Pattern                 | Acceptance evidence                                                                                       | Property obligation                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Classified outcome      | Example tests cover acknowledged, definitive failure, ambiguity, fallback, and loop prevention.           | Stateful alert model never emits fallback for ambiguity and never emits more than one fallback.      |
| Hybrid suppression      | Tests distinguish CloudWatch state-transition inputs from application/cross-source fingerprint decisions. | Stateful model verifies at most one application dispatch per fingerprint cooldown window.            |
| Deadline propagation    | Tests exhaust remaining budget at each boundary and assert no later call begins.                          | Generated valid deadline/action sequences preserve non-negative remaining time and bounded starts.   |
| Data minimization       | Tests reject/drop forbidden values and allow only bounded safe schema fields.                             | Sanitizer is idempotent and output satisfies allowlist/bounds invariants.                            |
| Conditional idempotency | Tests repeat refreshes and race conditional commits.                                                      | Stateful office model retains one managed reference and zero story attempts for all valid sequences. |

## Security Compliance

SECURITY-01 through SECURITY-15 are incorporated by typed validation, deny-by-default protected
commands, opaque protected values, bounded state, allowlisted observations, and local fail-closed
errors. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A under the approved architecture. No
blocking finding remains.
