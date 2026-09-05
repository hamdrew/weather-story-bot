# U-03 Domain Entities

| Entity or value object    | Core fields                                                                                    | Invariants and ownership                                                                                               |
| ------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `EnvironmentContract`     | environment name, Telegram mode, active office IDs, office destinations, alert destination     | Versioned and non-secret; dev is mock-only; staging and production live destinations are distinct.                     |
| `OfficeRegistry`          | version, enriched office records, active state, canonical source endpoint, destination         | IDs and active destinations are unique; an active record matches the environment contract; no named office is special. |
| `ResourceBindings`        | environment-scoped table, media, secret, alert, function, schedule, and observation references | Loaded only by runtime assembly; exact environment scope; immutable for the invocation; never accepted from an event.  |
| `RuntimeAssembly`         | validated contracts, resource bindings, clock/budget factory, concrete bounded ports           | Exists only after complete validation; supplies no deployment authority and no raw secret output.                      |
| `ScheduledOfficeCommand`  | office ID, invocation correlation                                                              | Contains exactly one office ID; must identify a configured active registry member.                                     |
| `InvocationBudget`        | remaining time, operation reserve, deadline                                                    | An outbound operation starts only when its bounded allowance and terminal-observation reserve remain.                  |
| `CurrentOfficeProjection` | office identity, verified information reference, conditional version                           | One current projection per office; updates require expected version and verified managed reference.                    |
| `CurrentStoryProjection`  | office-scoped story/revision identity, current media reference, publication facts              | Current facts are conditional/transactional; never merged across offices.                                              |
| `VerifiedMediaReference`  | deterministic current reference, digest, size/type metadata                                    | Represents verified accepted media only; replacement cleanup follows a successful state change.                        |
| `SafeObservation`         | correlation ID, timestamp, level, classification, allowlisted dimensions                       | Bounded and sanitizer-produced; excludes tokens, destinations, raw payloads, private IDs, and stack traces.            |
| `BuildEvidence`           | source/artifact identity, locked dependency result, SBOM/scan/validation summaries             | Immutable, bounded, non-secret, and non-authorizing; passed to U-04 only as evidence.                                  |
| `RestorePreparation`      | isolated target identity, consistency findings, cutover/rollback readiness                     | Does not alter the source table or assert Telegram reversal; a human-approved recovery procedure controls execution.   |

## Relationships

- One `EnvironmentContract` selects zero or more active `OfficeRegistry` records. Every selected
  record has exactly one environment destination, while inactive records require none.
- One `RuntimeAssembly` binds one environment to one immutable `ResourceBindings` set and produces
  one service graph. It may create many bounded invocation budgets, never a cross-environment graph.
- A `ScheduledOfficeCommand` selects exactly one active `CurrentOfficeProjection` and may create or
  revise office-scoped `CurrentStoryProjection` values through existing conditional contracts.
- A `CurrentStoryProjection` references at most one `VerifiedMediaReference` as current. A
  superseded reference is eligible for cleanup only after a replacement commits.
- Every terminal operation produces zero or more `SafeObservation` values and may update current
  state only through its owned conditional transition.
- `BuildEvidence` and `RestorePreparation` are evidence objects; neither carries credentials,
  deployment approval, or a mutable runtime reference.

## Prohibited Entities

U-03 must not introduce an alert fingerprint, cooldown, aggregation, alert-delivery record, queue,
public endpoint, production activation record, or user/session identity model. Cloud alarm history,
safe logs, metrics, SNS evidence, existing run facts, and owner-controlled change-set evidence are
the approved evidence boundaries.
