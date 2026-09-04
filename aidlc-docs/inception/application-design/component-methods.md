# Component Methods and Contracts

## Contract Conventions

- Inputs are typed, validated, bounded value objects or explicitly allowlisted mappings.
- Outputs contain domain results, safe classifications, or opaque references; methods do not return
  raw NWS/Telegram responses, tokens, private destinations, or secret-bearing URLs.
- Failure contracts are typed or classified. Unexpected boundary failures are converted to safe
  events at the handler/composition boundary.
- Detailed preconditions, algorithms, state-machine transitions, retries, and property definitions
  are deferred to Functional Design.

## Existing and Extended Runtime Methods

| Component             | Method                                    | Inputs                               | Outputs                                        | Purpose                                                                  |
| --------------------- | ----------------------------------------- | ------------------------------------ | ---------------------------------------------- | ------------------------------------------------------------------------ |
| Configuration         | `load_environment_config`                 | Versioned path                       | `EnvironmentConfig`                            | Parse non-secret configuration through Pydantic validation.              |
| Configuration         | `validate_environment_isolation`          | Environment configurations           | `None` or validation error                     | Enforce dev/staging/prod isolation and distinct live destinations.       |
| NWS Acquisition       | `OfficeRegistrySeeder.seed`               | Seed set, environment                | `OfficeRegistry`                               | Build the permitted office registry and activation set.                  |
| NWS Acquisition       | `OfficeWeatherStoryRetriever.retrieve`    | Registry, office ID, deadline        | `NormalizedCollection`                         | Retrieve one authorized office collection.                               |
| NWS Acquisition       | `normalize_collection`                    | Validated HTTP response, office ID   | `NormalizedCollection`                         | Separate valid stories from bounded quarantines.                         |
| Durable State         | `observe_story`                           | Story, image digest                  | Current-state result                           | Conditionally observe a revision without claiming publication.           |
| Durable State         | `reserve_publication`                     | Story/revision/run/operation context | `PublicationReservation` or safe no-op outcome | Acquire a lease for a possible create/edit effect.                       |
| Durable State         | `start_publication_send`                  | Reservation                          | Boolean/typed authorization result             | Permit at most one outbound call for a reservation.                      |
| Durable State         | `transition_publication`                  | Reservation, classified outcome      | Updated terminal/ambiguous state               | Append a legal transition and update current facts.                      |
| Durable State         | `reconcile_ambiguous_attempt`             | Authorized reconciliation command    | Safe reconciliation result                     | Conditionally record a confirmed outcome.                                |
| Media Retention       | `ImageRetainer.download`                  | Validated HTTPS URL                  | `ValidatedImage`                               | Enforce network and decoded-image bounds.                                |
| Media Retention       | `ImageRetainer.retain`                    | Story/revision/image context         | `ImageMetadata`                                | Stage, verify, promote, and commit a current object.                     |
| Telegram Publication  | `render_caption`                          | Title, description, alt text         | `Caption`                                      | Produce deterministic UTF-16-bounded text and entities.                  |
| Telegram Publication  | `execute_reserved_publication`            | Reservation, media, caption          | `PublicationResult`                            | Make the one allowed Telegram create/edit call and classify its outcome. |
| Scheduled Publication | `OfficeScheduledProcessor.process_office` | Active office ID                     | `ScheduledRun`                                 | Coordinate a single bounded office run.                                  |
| Lambda Boundary       | `publisher_handler`                       | Exact scheduler event, context       | `None` or safe failure                         | Validate and delegate scheduled publication.                             |
| Lambda Boundary       | `reconciliation_handler`                  | Validated operator event, context    | Safe result mapping                            | Validate and delegate an authorized reconciliation.                      |

## Planned Methods

| Component                  | Method                         | Inputs                                               | Outputs                                   | Purpose                                                                                                                    |
| -------------------------- | ------------------------------ | ---------------------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Runtime Composition        | `build_publisher_service`      | Validated runtime settings and factories             | `PublisherRuntime`                        | Bind production adapters to the application service without leaking dependencies into domain logic.                        |
| Runtime Composition        | `build_reconciliation_service` | Validated runtime settings and authorization adapter | Protected reconciliation service          | Bind the protected operator path to scoped resources.                                                                      |
| Office Information Service | `refresh_office_information`   | Authorized environment/office command                | Safe message-reference result             | Create or edit and pin dedicated office information without publishing a story.                                            |
| Alerting Service           | `report_operational_event`     | Classified CloudWatch alarm-state-transition event   | Safe dispatch result                      | Emit one safe Telegram alert and a non-recursive SNS/email fallback only after definitive failure.                         |
| Observability              | `record_run_observation`       | Safe run/result event                                | `None`                                    | Emit structured logs and bounded metrics.                                                                                  |
| Delivery Evidence          | `verify_revision_evidence`     | Source artifact, resolved inputs, tool results       | Immutable evidence manifest or failure    | Prove the exact revision passed required build, scan, test, and package checks; retain a concise non-gating cost estimate. |
| Change-Set Planner         | `create_and_classify_plan`     | Evidence manifest, environment, parameters           | Immutable plan classification             | Create without executing an exact CloudFormation change set.                                                               |
| Approval Selector          | `authorize_plan_execution`     | Plan classification, environment, approval evidence  | Authorized execution request or denial    | Require explicit owner approval for every staging plan and human approval for every production plan.                       |
| Change-Set Executor        | `execute_exact_plan`           | Authorized immutable execution request               | Safe deployment result/evidence reference | Execute only the reviewed plan without rebuilding or parameter substitution.                                               |

## Boundary Rules for Planned Methods

- `refresh_office_information`, reconciliation, and every protected operation must deny by default
  on caller, environment, identifier, state, or resource mismatch.
- Delivery methods must fail closed on absent, stale, malformed, mismatched, or over-limit evidence.
- No component method may broaden the remote-action authorization boundary: cloud plan or execution
  calls require the separately authorized route specified by the approved requirements.
