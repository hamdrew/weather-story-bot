# U-03 Logical Components

| Component                       | Responsibility                                                                                                   | Boundary                                                                                                    |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Configuration Admission         | Load and validate registry, environment, operations, and non-secret binding documents.                           | Reject disagreement, missing values, inactive office scope, or cross-environment references before effects. |
| Runtime Assembly                | Construct immutable service graphs and bounded concrete ports once per execution environment.                    | Sole component allowed to resolve secrets and instantiate adapters; provides no deployment authority.       |
| Scheduled Command Validator     | Validate one scheduler-selected office command and invocation budget.                                            | Reject malformed, unknown, inactive, or unconfigured office input before processing.                        |
| Budget Propagator               | Allocate remaining deadline to external operations and terminal observation.                                     | No adapter starts without allowance; no unbounded retry.                                                    |
| Publisher Adapter Set           | Bind NWS acquisition, durable state, media retention, and public Telegram publication ports.                     | Uses existing conditional/verified contracts; no scans or caller-supplied resource overrides.               |
| Protected-Operations Binding    | Bind U-01 office-information and alert ports to trusted identity, current state, private Telegram, and fallback. | Maintains U-01's one-attempt/fallback and no-loop rules.                                                    |
| Safe Observation Mapper         | Project logs, metrics, handler outcomes, and evidence to allowlisted bounded data.                               | Drops secrets, private identifiers, raw bodies, URLs, responses, and unbounded diagnostics.                 |
| Package-Evidence Assembler      | Collect source/artifact, dependency, validation, SBOM, and scan summaries.                                       | Non-secret immutable evidence only; cannot approve or execute a change set.                                 |
| Restore-Preparation Coordinator | Prepare isolated restore validation, cutover, and rollback facts.                                                | Does not mutate retained source, reverse Telegram effects, or perform a recovery execution.                 |

## Permitted Information Flow

1. Configuration Admission → Runtime Assembly → Scheduled Command Validator → Budget Propagator →
   Publisher Adapter Set → Safe Observation Mapper.
2. Runtime Assembly → Protected-Operations Binding → Safe Observation Mapper.
3. Package-Evidence Assembler → U-04 delivery control plane, using only bounded evidence references.
4. Restore-Preparation Coordinator → owner runbook, using isolated target and consistency facts.

## Prohibited Coupling

- No handler, domain service, or evidence component constructs clients, reads process configuration,
  resolves secrets, or approves a deployment.
- No component introduces an alert record, queue, public endpoint, alternate deployment path, or
  production activation.
- Event content cannot select a secret, table, bucket, topic, function, destination, or schedule.
- No component can enable a schedule before separately authorized staging smoke checks and owner
  enablement.
