## Purpose

Notify the bot operator privately in Telegram when the Weather Story publishing service encounters conditions that require attention.

## ADDED Requirements

### Requirement: Send private operational alerts
The system SHALL send an alert message to the configured private Telegram user when a monitored processing or delivery failure occurs.

#### Scenario: A monitored failure fires an alert
- **WHEN** monitoring detects a failed scheduled processing run, NWS retrieval failure, quarantined malformed NWS item, or Telegram delivery failure
- **THEN** the configured private Telegram user receives an alert message

### Requirement: Deduplicate and aggregate operational alerts
The system SHALL assign every alert a severity and a deterministic fingerprint composed of fingerprint-schema version, severity, workflow, office ID, and normalized error class; story identity SHALL be included only for story-specific failures. Run and correlation IDs SHALL be alert context and SHALL NOT be fingerprint inputs. The system SHALL keep DynamoDB-backed alert state by fingerprint, including first-seen time, last-seen time, occurrence count, latest run/correlation ID, and cooldown expiry, using conditional writes to make concurrent duplicate events safe.

The first occurrence of a fingerprint SHALL notify immediately. Repeated occurrences during a four-hour cooldown SHALL be suppressed and accumulated. The first matching occurrence after that cooldown, if the condition persists, SHALL send one aggregated ongoing alert with the count and first/last-seen times, then begin a new cooldown. Severities SHALL be `critical` for ambiguous Telegram outcomes, `error` for NWS, malformed-item quarantine, image, definitive Telegram, and failed-run conditions, and `warning` for controlled deferrals; warnings remain metric-only and SHALL NOT create an operator alert.

#### Scenario: A scheduled NWS failure repeats
- **WHEN** the same normalized NWS failure occurs for the same office during the four-hour cooldown
- **THEN** the system increments its alert-state count without sending another private Telegram alert

#### Scenario: A failure persists beyond the cooldown
- **WHEN** the same fingerprint occurs after its cooldown expires
- **THEN** the system sends one alert marked ongoing with the accumulated count and first/last-seen times, then resets the cooldown

### Requirement: Emit measurable operational metrics
The publisher and alert dispatcher SHALL emit metrics in the `WeatherStoryBot` namespace with only `Environment` and `OfficeId` dimensions. They SHALL NOT use story IDs, run IDs, attempt IDs, Telegram IDs, URLs, or other high-cardinality identifiers as metric dimensions. Each office run SHALL emit count metrics `RunStarted`, `RunSucceeded`, `RunFailed`, `OfficeRetrievalFailed`, `StoriesDiscovered`, `StoriesPublished`, `StoriesEdited`, `ReservationsAmbiguous`, `ImageUploadFailed`, `Telegram429`, and `AlertFallbackUsed` when the corresponding event occurs. The publisher SHALL emit `RunDurationMs`, `NwsRequestDurationMs`, `ImageDownloadDurationMs`, and `TelegramRequestDurationMs` with unit `Milliseconds` for the applicable operation. Counts SHALL use unit `Count`; duration metrics SHALL support p50, p90, and p99 views.

Metric emission SHALL distinguish a valid zero-story run from the absence of a run: a successful empty collection emits `RunStarted`, `RunSucceeded`, and `StoriesDiscovered=0`. `RunFailed` SHALL be emitted for collection, required-outcome-persistence, or unresolved required-publication failure. `ReservationsAmbiguous`, `ImageUploadFailed`, `Telegram429`, and `AlertFallbackUsed` SHALL be emitted at the time of each event, including when the existing alert fingerprint suppresses a repeated notification.

#### Scenario: An office has no new stories
- **WHEN** an enabled office completes a valid empty collection
- **THEN** the metrics show a started and succeeded run with `StoriesDiscovered=0`, allowing operators to distinguish quiet source data from a missing invocation

#### Scenario: A repeated failure is alert-suppressed
- **WHEN** a repeated failure occurs during the four-hour alert cooldown
- **THEN** its metric is still emitted and incremented even though the duplicate private alert is suppressed

### Requirement: Route monitored failures through the alert trigger
The system SHALL publish monitored processing failures and application-detected failures to an alert-trigger notification path consumed by the alert-dispatcher, rather than relying on a direct CloudWatch Alarm to Lambda action.

#### Scenario: CloudWatch alarm enters an alert state
- **WHEN** a configured CloudWatch alarm enters its alert state
- **THEN** the alarm publishes an event to the alert-trigger notification path and the alert-dispatcher receives it

#### Scenario: Application detects a failure
- **WHEN** the publisher detects an NWS, malformed-item quarantine, image, Telegram, or reconciliation failure
- **THEN** it publishes the failure context to the same alert-trigger notification path

### Requirement: Alert on incomplete persisted runs
The system SHALL treat a persisted run with status `failed`, `required_work_completed=false`, or a nonzero unresolved rejected/ambiguous/image-invalid outcome as an operational failure. It SHALL publish that run context to the alert-trigger path, subject to the existing severity, fingerprint, four-hour cooldown, and aggregation rules. A normally returned Lambda invocation SHALL not suppress an alert when the durable run result is failed.

#### Scenario: A handler returns after recording failure
- **WHEN** the handler persists a `failed` run and returns normally because persistence succeeded
- **THEN** the monitoring and alerting path still identifies the run as failed and alerts according to the configured fingerprint policy

### Requirement: Exercise alert delivery boundaries
Verification SHALL use deterministic fault injection for Telegram `429`, `5xx`, timeout, and accepted-then-lost-response cases, and SHALL verify retry, defer, ambiguity, alert-fingerprint, and fallback behavior without intentionally rate-limiting or losing a live production/staging message. A staging smoke test SHALL verify only successful real delivery to the dedicated test recipient/channel. Verification SHALL also confirm the SNS subscription, alert-trigger-to-dispatcher path, fallback topic/email path, and loop prevention.

#### Scenario: A deterministic alert fault is exercised
- **WHEN** the test injects a Telegram rate limit, server error, timeout, or accepted-then-lost response
- **THEN** the test verifies the specified retry/defer or ambiguity transition, metric emission, alert fingerprint behavior, and fallback/loop boundary without sending an unintended live message

### Requirement: Include actionable alert context
The system SHALL include severity, fingerprint, affected workflow, failure summary, event time, affected office ID, run ID when available, final run status when available, elapsed time when available, and relevant story-outcome counts in each operational alert. The rendered private Telegram alert SHALL be at most 3,500 Unicode grapheme clusters; if needed, it SHALL truncate only at a grapheme-cluster boundary and append `…`.

#### Scenario: Operator receives an alert
- **WHEN** an operational alert is delivered
- **THEN** the message identifies what failed, when it occurred, the affected office ID, and the available run summary context

### Requirement: Isolate alerts from public publications
The system SHALL send operational alerts only to the configured private recipient and SHALL NOT send them to the public Weather Story channel.

#### Scenario: Publishing workflow fails
- **WHEN** a publishing workflow failure generates an alert
- **THEN** the alert is sent to the private recipient instead of the channel audience

### Requirement: Provide a fallback when Telegram alert delivery fails
The system SHALL publish a notification to a separate SNS fallback topic with a configured email subscription when delivery of an operational alert to the private Telegram user fails. Alert-dispatcher and fallback-delivery failures SHALL emit only structured logs and CloudWatch metrics; they SHALL NOT publish to the alert-trigger topic or generate another private Telegram alert. The fallback topic SHALL have no subscription or route back to the alert dispatcher.

#### Scenario: Private Telegram alert delivery fails
- **WHEN** the alert dispatcher cannot deliver an operational alert to the configured private Telegram user
- **THEN** the system publishes an SNS fallback notification containing the alert-delivery failure context for delivery by email

#### Scenario: The fallback notification cannot be delivered
- **WHEN** fallback SNS/email delivery fails
- **THEN** the system records the failure in logs and metrics without re-entering the alert-trigger or Telegram-alert paths
