# U-03 NFR Design Patterns

## Immutable Assembly and Fail-Closed Admission

Runtime assembly validates all versioned configuration, active-office agreement, exact
environment-scoped references, and non-secret resource bindings before resolving a secret or
constructing an adapter. A successful immutable assembly may be reused; any missing, malformed,
or mismatched input produces no partial runtime and no external action. Handler admission accepts
only its exact bounded event schema and delegates after validating active-office scope and budget.

## Budget Propagation and Bounded Effects

The publisher creates one 14-minute application budget with a 60-second completion reserve. Every
NWS, media, state, secret, Telegram, and notification adapter receives only the remaining bounded
allowance and refuses to start when it cannot finish safely. This pattern permits final persistence
and safe observation rather than unbounded retries or cleanup. U-01 retains its stricter
per-attempt protected-operation budget.

## Conditional Current-Fact and Verified-Media Pattern

Current office/story projections are the authoritative facts. A media reference becomes current only
after source validation, bounded retention, verification, promotion, and a successful conditional
state transition. A rejected transition preserves the prior current projection; replacement cleanup
occurs only after the replacement is authoritative. Ambiguous Telegram delivery is terminal until
authorized reconciliation, not an automatic retry.

## Isolated Lifecycle and Recovery-Preparation Pattern

Dev binds mocks only. Staging uses environment-isolated bindings and starts with schedules disabled;
neither a protected operation nor an ordinary runtime failure can enable a schedule. Production
configuration remains validated but inactive. Recovery preparation restores a retained state copy
into an isolated target, validates consistency, and documents a human cutover/rollback decision; it
does not overwrite source state or assert Telegram reversal.

## Safe Evidence and Authorization-Separation Pattern

Every boundary projects a bounded allowlisted observation with a safe correlation ID. Secret values,
private destinations, raw payloads/responses, and unbounded exceptions are excluded before logging,
metrics, handler outputs, and package evidence. Build evidence proves source/artifact and validation
identity but is non-authorizing. Change-set creation, owner approval, and controlled execution stay
outside U-03; runtime roles cannot gain those capabilities.

## PBT Carry-Forward

Code Generation must test deterministic assembly admission, active-office invariants, idempotent safe
projection, and stateful current-media transitions. State models compare a simplified current record
and media reference after each generated valid operation. Commutativity, separate algorithm oracle,
and structural induction are N/A because conditional transitions are ordered and no alternate
algorithm or recursive structure exists.

## Security Compliance

SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
incorporated by the patterns above. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A. No blocking
finding remains; Resiliency Baseline is disabled.
