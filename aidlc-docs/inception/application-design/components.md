# Application Components

## Design Boundary

The approved design keeps the existing ports-and-adapters Python application separate from runtime
composition, AWS infrastructure, delivery controls, observability, and operator evidence. Components
exchange validated, bounded domain models and safe result metadata; they never exchange raw external
payloads, secret values, private Telegram identifiers, or untrusted executable strings.

## Runtime Components

| Component                               | Purpose and responsibilities                                                                                                                                                                                                                                                                                                            | High-level interfaces                                                                                                             |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Configuration and Domain Contracts      | Load versioned non-secret configuration; validate environment isolation, office activation, source models, identifiers, destinations, and secret shape.                                                                                                                                                                                 | `load_seed_set`, `load_environment_config`, `validate_environment_isolation`, `validate_telegram_secret`; Pydantic domain models. |
| NWS Acquisition                         | Enrich office registry records, make bounded NWS requests, normalize current collections, and quarantine invalid items independently.                                                                                                                                                                                                   | `OfficeRegistrySeeder`, `NWSCollectionClient`, `OfficeWeatherStoryRetriever`, `normalize_collection`.                             |
| Durable State                           | Own current projections, append-only operational records, conditional publication reservations, transitions, reconciliation facts, TTL, and review queries.                                                                                                                                                                             | `HistoryStore` and typed publication/image/run models.                                                                            |
| Media Retention                         | Download, validate, stage, promote, reverify, commit, and safely clean up private image objects.                                                                                                                                                                                                                                        | `ImageRetainer`, `StagingReconciler`, `ValidatedImage`.                                                                           |
| Telegram Publication                    | Render bounded captions; revalidate retained media; make exactly one create or edit call per started reservation; classify and persist safe outcomes.                                                                                                                                                                                   | `render_caption`, `publish_photo`, `execute_reserved_publication`, `publish_with_retries`.                                        |
| Scheduled Publication Service           | Orchestrate one active-office run within bounded time/revision limits using injected acquisition, state, media, and publication ports.                                                                                                                                                                                                  | `OfficeScheduledProcessor.process_office`.                                                                                        |
| Protected Operator Services             | Reconcile an ambiguous publication, refresh office information, and initiate safe operational actions only after caller, environment, object, and state validation.                                                                                                                                                                     | Reconciliation handler/service exists in part; office-information and protected-operation services are planned.                   |
| Runtime Composition and Lambda Boundary | Construct validated settings and concrete adapters once per execution environment; handlers validate narrow events, invoke a service, and return safe results.                                                                                                                                                                          | `load_publisher_runtime_settings`, `publisher_handler`, `reconciliation_handler`; planned composition root.                       |
| Observability and Alerting              | Emit allowlisted structured logs, bounded metrics, concise dashboards, and actionable CloudWatch alarms. Alarm state transitions invoke a small alert-notification Lambda for one private Telegram alert and one definitive-failure SNS/email fallback; no DynamoDB alert fingerprint, cooldown, aggregation, or delivery state exists. | Planned logging, metrics, CloudWatch alarm-event, alert-notification, and runbook-facing ports.                                   |

## Infrastructure and Delivery Components

| Component                                    | Purpose and responsibilities                                                                                                                                                                                                                                       | High-level interfaces                                                                                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Environment Infrastructure                   | Define one isolated staging SAM stack for Lambda, Scheduler, DynamoDB PITR, S3 versioning/retention, Secrets Manager, SNS, CloudWatch, AWS Budget, and scoped IAM in `us-east-2`; production contracts remain validated but undeployed.                            | Environment parameters, template resources, stack outputs, and manual-restore/runbook contracts; planned.                                      |
| Delivery Control Plane                       | Consume a read-only exact GitHub revision, build it in CodeBuild, verify supply-chain evidence, produce a concise non-mutating Infracost staging estimate, create/classify a CloudFormation change set, and require owner approval before every staging execution. | Source-artifact identity, evidence manifest, Infracost estimate, change-set classification, owner approval record, execution request; planned. |
| Evidence, Runbooks, and Contributor Boundary | Retain safe release/recovery evidence, expose public-safe contributor guidance, and connect operator runbooks to protected controls.                                                                                                                               | Evidence references, runbook inputs, Issue/PR templates, repository-policy checks; partly present and partly planned.                          |

## Component Ownership Rules

- Domain/application components do not construct AWS clients, fetch secrets, read process
  environment directly, execute shell commands, or approve deployments.
- The composition root is the only runtime component that binds validated configuration to concrete
  AWS, HTTP, Telegram, clock, and identifier adapters.
- Lambda handlers do not contain orchestration policy; they validate their bounded event contract
  and delegate to a composed application service.
- Infrastructure declares resources and least-privilege roles but contains no runtime business
  rules. Delivery controls assemble immutable evidence and request only the authorized
  CloudFormation action for an exact plan.
- Approval remains outside build, agent, and deployment roles for every staging change and all
  production changes. Accepted Telegram effects are not treated as reversible deployment state.

## Traceability

These components cover FR-01 through FR-14 and NFR-01 through NFR-08. They directly support all
eight approved epics, especially E-03 durable recovery, E-05 infrastructure, E-06 governed
delivery, E-07 security/verification, and E-08 operational readiness.
