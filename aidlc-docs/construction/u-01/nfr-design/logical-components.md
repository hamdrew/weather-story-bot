# U-01 Logical Components

## Components and Contracts

| Component                    | Responsibility                                                                                           | Inputs                                                                | Outputs                                              | Constraint                                                                                  |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Protected Command Validator  | Authenticate/authorize and validate environment, office, and command shape.                              | Raw handler event plus trusted caller context.                        | `OfficeInformationRefreshCommand` or safe rejection. | Reject scheduler/publication/cross-environment commands before external work.               |
| Office Refresh Coordinator   | Orchestrate current NWS profile, invite/message/pin verification, and conditional current-record commit. | Valid command, remaining deadline, narrow ports.                      | `OfficeRefreshResult`, safe event candidate.         | Never creates a story attempt, audit snapshot, or unverified reference.                     |
| Operational Event Normalizer | Convert failures and monitored inputs to safe classified events.                                         | Allowlisted boundary outcome.                                         | `OperationalEvent`.                                  | Drops raw bodies, private IDs, URLs, secrets, and unbounded text.                           |
| Fingerprint Policy           | Derive fingerprint and atomically decide dispatch/suppression/metric-only.                               | Safe event, time, fingerprint-state port.                             | `AlertDecision` and safe state update.               | Per-fingerprint; application cooldown is four hours.                                        |
| CloudWatch Alarm Adapter     | Translate CloudWatch state transitions into safe operational events.                                     | Alarm transition with allowlisted alarm metadata.                     | `OperationalEvent`.                                  | Relies on CloudWatch transition behavior for source-level persistent-condition suppression. |
| Alert Renderer               | Render bounded private alert text/entities.                                                              | Safe event, safe fingerprint/context.                                 | Validated alert payload.                             | At most 3,500 grapheme clusters; no parse mode or untrusted markup.                         |
| Alert Dispatcher             | Execute one eligible private alert and conditional one fallback.                                         | `AlertDecision`, alert payload, bounded deadline, Telegram/SNS ports. | `AlertDispatchOutcome`, safe event candidate.        | No loop back to trigger topic; ambiguity does not fallback.                                 |
| Sanitized Observation Mapper | Validate and emit safe logs/metrics/results.                                                             | Safe candidate plus environment log policy.                           | Structured observation/result.                       | One allowlisted schema; prod rejects DEBUG.                                                 |

## Allowed Information Flow

1. Handler boundary → Protected Command Validator → Office Refresh Coordinator → NWS/Telegram/state
   ports → Sanitized Observation Mapper.
2. Application/CloudWatch boundary → Operational Event Normalizer → Fingerprint Policy → Alert
   Renderer → Alert Dispatcher → Sanitized Observation Mapper.
3. CloudWatch may suppress repeated source alarm actions through its own state transitions. The
   normalized event still uses the application fingerprint policy whenever its alert must be
   correlated with application-originated events.

## Prohibited Coupling

- Coordinators and policy components do not construct AWS clients, read secrets, execute deployment
  actions, or access unbounded request/response bodies.
- CloudWatch alarm configuration is not an application-state store and cannot authorize a fallback,
  replace four-hour cross-source aggregation, or expose private alert identifiers.
- Alert Dispatcher and fallback paths cannot invoke the alert-trigger topic, create a new alert event,
  or publish to the public Weather Story channel.
- No component introduces a queue, cache, global process lock, separately deployable service, or
  untyped arbitrary event mapping.

## Infrastructure-Design Handoff

Infrastructure Design must map the ports above to Lambda handlers, DynamoDB conditional state,
CloudWatch metrics/alarms/composites, SNS trigger/fallback topics, log groups, environment
parameters, and least-privilege roles. It must preserve this logical separation and define exact
resource/IAM details without changing business policy.
