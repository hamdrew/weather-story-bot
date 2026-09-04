# Services and Orchestration

## Application Services

### Registry Service

Builds the validated office registry from the versioned seed and environment configuration. It uses
NWS and geocoding ports only during the explicitly selected enrichment workflow, returns records
with scoped activation/destination data, and delegates durable persistence to Durable State.

### Scheduled Publication Service

`OfficeScheduledProcessor` is the primary application orchestrator. For one active office it expires
due state, retrieves and normalizes the collection, records quarantines, observes revisions, retains
new media, reserves publication, invokes the publication port once per started reservation, and
persists a terminal run summary. It owns no AWS client construction and does not decide deployment
approval.

### Publication Service

Coordinates a pre-authorized `PublicationReservation`, retained media, a safe caption, and the
Telegram adapter. It distinguishes definitive rejection from ambiguous external outcome, delegates
state transitions to Durable State, and permits a retry only through a new reservation within the
run budget.

### Protected Operator Service

Receives an authenticated, schema-validated command from the Lambda boundary. It reconciles only
permitted ambiguous attempts, refreshes office information without publication, or routes bounded
operations to their dedicated service. It never asserts reversal of an accepted Telegram effect.

### Alerting and Observability Service

Converts classified internal events into allowlisted logs, metrics, concise dashboards, and a small
actionable CloudWatch alarm set. Only CloudWatch alarm state transitions invoke the dedicated
alert-notification Lambda, which posts one bounded private Telegram alert. A definitive Telegram
failure invokes SNS/email once; ambiguous delivery is logged and measured without resend or
fallback, and no DynamoDB alert fingerprint, cooldown, aggregation, or delivery state is kept.

## Runtime Composition Service

The composition root reads validated packaged configuration and environment references, resolves
secrets only at the protected boundary, creates concrete AWS/HTTP/Telegram adapters, injects them
into application services, configures redacted structured logging, and caches safe construction
state for the Lambda execution environment. Handlers remain thin adapters for scheduler and
operator-event contracts.

## Delivery Control-Plane Services

### Revision Verification Service

Receives the read-only CodeConnections artifact, validates revision/digest identity, and coordinates
locked dependency installation, formatting, lint/type/test, packaging, template validation, scans,
SBOM, and packaged-image evidence. It emits an immutable safe evidence manifest or fails closed.

### Cost and Change-Set Planning Service

Runs pinned Infracost against the exact artifact and resolved inputs and retains a concise staging
estimate for owner review. A missing or failed estimate is visible but is not a custom policy or
machine-enforced mutation gate. The service creates a CloudFormation change set without execution
and classifies resource, permission, secret, environment, deployment-role, and ambiguity changes.

### Approval and Execution Service

Uses immutable classification and evidence to prepare, but never bypass, the approval gate: every
staging plan pauses for the owner's explicit cloud-native approval, regardless of classification;
every production plan also pauses for human approval when that deferred stage is authorized.
Execution uses the same immutable change-set identity and does not rebuild or mutate through an
alternate path.

## Orchestration Ownership

| Orchestration                               | Owner                                          | Explicitly excluded                                                                |
| ------------------------------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------- |
| Story discovery through run result          | Scheduled Publication Service                  | AWS client construction, deployment approval                                       |
| One Telegram effect and outcome recording   | Publication Service with Durable State         | Automatic retry of ambiguity, raw response retention                               |
| Protected correction and office information | Protected Operator Service                     | Cross-environment action, unauthenticated invocation                               |
| AWS dependency assembly                     | Runtime Composition Service                    | Domain policy and delivery approval                                                |
| Evidence through change-set classification  | Delivery planning services                     | Resource mutation before all gates pass                                            |
| Approval and execution                      | Approval and Execution Service plus owner gate | Build, agent, or deployment-role self-approval of any staging or production change |
