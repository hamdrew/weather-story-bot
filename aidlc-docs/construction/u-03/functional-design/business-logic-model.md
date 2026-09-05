# U-03 Business Logic Model

## Runtime Assembly

`RuntimeAssembly` is the sole composition boundary. On a cold start it loads the versioned office
registry and non-secret environment configuration, validates their active-office and destination
agreement, validates exact non-secret resource references, obtains secret material only through a
dedicated secret port, and constructs bounded adapters. It then exposes independently composed
publisher, reconciliation, office-information, and alert-dispatch services.

Assembly is all-or-nothing. A missing, malformed, cross-environment, or inconsistent input yields
a classified construction failure before any NWS, Telegram, durable-state, media, or notification
operation begins. An invocation may reuse a successfully assembled immutable runtime; it may never
reuse a partly constructed runtime or let an event override its bindings.

## Scheduled Publisher Flow

1. The scheduled-handler boundary admits only one event whose complete schema contains an office
   identifier. It rejects an unknown, inactive, unconfigured, or mismatched identifier.
2. The runtime creates a 14-minute application budget and delegates the single validated office to
   the existing scheduled-publication service.
3. That service retrieves one bounded NWS collection, processes eligible stories according to
   existing durable-state, media, and Telegram contracts, and persists a classified run outcome.
4. It emits only allowlisted observations and metrics. It does not dispatch an operator alert;
   an alarm transition is the sole alert trigger.
5. Handler failure preserves the defined persistence boundary and exposes a safe failure outcome.
   It never converts an ambiguous Telegram outcome into a retry or a successful run.

## Protected and Alert Flows

The runtime binds U-01's protected-operation contracts to concrete ports without widening their
authority.

- An office-information request must pass trusted-invocation authorization, exact function and
  environment checks, configured active-office membership, registry active state, and the remaining
  invocation budget before it retrieves profile data or manages a Telegram message. It commits only
  a verified, conditionally current reference. Failure leaves the schedule disabled.
- An alert request must originate from the configured alarm-transition path and match the configured
  account, environment, topic, and alarm set. It makes at most one private Telegram attempt. Only a
  definitive failure permits one independent fallback attempt; ambiguity, rejection, rendering
  failure, and fallback failure terminate locally.

## Current State and Media Flow

The assembled publisher retains the existing current-office and current-story projections as the
authoritative current facts. Each durable transition uses its existing conditional or transactional
contract; no adapter broadens access into scans or unrelated key families. Media is accepted only
after bounded source validation, verification, digesting, staged retention, post-store validation,
promotion to the deterministic current reference, and successful conditional state commit. Cleanup
can remove replaced current media only after the state transition identifies its replacement.

PITR restoration is intentionally a preparation workflow: restore into a distinct isolated target,
validate key/version and current-reference consistency, prepare a documented cutover decision, and
retain a rollback path. It never claims to reverse an accepted Telegram effect.

## Packaging Evidence Flow

The reproducible-build workflow consumes a pinned source revision and locked dependencies, creates
an arm64 Python package, and emits bounded artifact, dependency, SBOM, scan, and validation
evidence. Evidence identifies inputs and results but excludes tokens, private identifiers, and raw
tool output. U-03 provides this evidence to U-04; it has no approval, change-set execution, or
alternate deployment path.

## Failure Classification

| Boundary                  | Classifications                                                 | Required response                                                      |
| ------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Configuration or assembly | invalid, missing, inconsistent, unavailable                     | Fail closed before external work; emit a safe observation.             |
| Scheduled event           | malformed, unauthorized office, exhausted budget                | Reject before processing; no substitute office is selected.            |
| Publisher service         | success, quarantined, deferred, failed                          | Persist the defined safe result; emit bounded signals.                 |
| State/media transition    | conditional conflict, invalid source/media, persistence failure | Preserve authoritative current fact; classify without raw diagnostics. |
| U-01 operation            | rejected, failed, definitive failure, ambiguous, delivered      | Preserve U-01 terminal behavior; never create a notification loop.     |
| Package evidence          | missing, mismatched, failed validation                          | Emit failed evidence; do not authorize or execute deployment.          |

## PBT-01 Properties

- Configuration admission is deterministic: equivalent valid registry/configuration/reference
  inputs construct an equivalent immutable binding set; invalid inputs never produce a runtime.
- Active-office filtering is an invariant: every admitted scheduled or protected-office operation
  targets one configured active registry member, and changing inactive entries cannot make them
  eligible.
- Safe observation projection is idempotent and bounded: projecting it again does not add fields or
  reveal prohibited material.
- Current-state/media transitions maintain referential integrity: a successful current record points
  to exactly one verified current media reference, while a rejected transition preserves the prior
  current reference.
- Stateful property tests shall model sequences of observation, retention, commit, replacement, and
  rejection events. Commutativity, a separate algorithm oracle, and structural induction are N/A:
  these operations are ordered conditional state transitions, not interchangeable or recursive
  algorithms.
