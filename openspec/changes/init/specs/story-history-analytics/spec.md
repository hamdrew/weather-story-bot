## Purpose

Maintain durable current Weather Story state, lightweight story facts, and publication outcomes for deduplication, operational audit, and fun-fact analysis.

## ADDED Requirements

### Requirement: Persist current Weather Story state and lightweight facts
The system SHALL durably retain one mutable current-story record for each canonical `(office_id, source_story_id)` identity. The record SHALL include its first-seen time; current revision hash; source `updateTime` and `endTime`; lifecycle status; current retained-image location and metadata when available; office-specific Telegram channel/message reference; and latest publication status. The record SHALL support fast deduplication and processing decisions, while first-seen time and publication outcomes support lightweight fun-fact analysis. The system SHALL NOT retain superseded story source content, metadata, or images.

#### Scenario: A story is first discovered
- **WHEN** the system processes a Weather Story identity not already present in history
- **THEN** it creates one current-story record with a revision hash and first-seen time

#### Scenario: A changed story is discovered
- **WHEN** the system processes a previously known story identity with a revision hash different from its current record
- **THEN** it conditionally replaces the current source and image state while preserving first-seen, message, and publication state; it does not retain the superseded source state or modify publication-attempt records

#### Scenario: An unchanged story is discovered again
- **WHEN** the system processes a story identity and revision hash already present in history
- **THEN** it records the observation or last-seen time without changing the current source state or creating a publication event

#### Scenario: A story expires
- **WHEN** the current time reaches or passes the source `endTime`
- **THEN** it marks the current-story record expired while retaining its committed image reference and S3 object, lightweight story facts, and Telegram publication history indefinitely

#### Scenario: A story is absent before expiration
- **WHEN** a story is absent from a successful collection and its source `endTime` is in the future
- **THEN** it remains in the current-story record and is not tombstoned or deleted

#### Scenario: Two offices expose the same source story ID
- **WHEN** two office entries return the same source story ID
- **THEN** the system retains separate current-story records and publication records for each `(office_id, source_story_id)` pair

#### Scenario: A story includes a downloaded image
- **WHEN** the system retrieves an image for a Weather Story
- **THEN** the current-story record retains the current image bytes and queryable image metadata indefinitely, including after expiration

### Requirement: Persist mutable current office operational state
The system SHALL retain exactly one conditionally mutable `OFFICE#{office_id}` / `CURRENT` record per configured office. The record SHALL contain current NWS-enriched office and region metadata, active configuration, and the managed pinned-message and invite references when present. Conditional updates SHALL prevent a stale enrichment or management invocation from replacing newer current state. The system SHALL NOT retain an office metadata audit trail, immutable office snapshots, raw NWS payloads, invite links in logs, or secret values.

#### Scenario: Office metadata is refreshed
- **WHEN** a successful enrichment or office-info invocation observes changed NWS office/region metadata or active configuration
- **THEN** it conditionally updates that office's `CURRENT` record in place without creating an office audit or snapshot record

#### Scenario: Managed office information is updated
- **WHEN** an office-info invocation creates or edits the managed pinned message or invite reference
- **THEN** it conditionally updates the same office's `CURRENT` record while retaining the newest known NWS-enriched metadata and without creating a publication attempt

### Requirement: Maintain an append-only publication-attempt audit log
The system SHALL create an immutable publication-attempt record for every create or edit reservation. Each attempt record SHALL contain an `attempt_id`, `run_id`, canonical story identity, revision hash, request type, reservation owner and lease data, target Telegram channel/message reference when known, and creation timestamp. The system SHALL record each attempt state transition as a separate immutable event linked to `attempt_id`, containing the prior state, resulting state, transition time, actor or reservation owner, completion timestamp and measured latency when applicable, error class when applicable, sanitized response metadata, and reconciliation reason when applicable. The final state of an attempt SHALL be derived from its latest transition event.

Sanitized response metadata SHALL be limited to HTTP status, Telegram error code and description, NWS or Telegram request/correlation IDs, latency, `retry_after` when present, retry ordinal, and retry/defer decision. The audit log SHALL NOT retain bot tokens, authorization headers, full request payloads, or raw response bodies.

#### Scenario: Channel publication succeeds
- **WHEN** Telegram confirms delivery of a Weather Story
- **THEN** the history records the immutable attempt, its append-only state transitions, successful completion time, latency, sanitized Telegram response metadata, and Telegram delivery reference

#### Scenario: Channel publication fails
- **WHEN** a Telegram publication attempt fails
- **THEN** the history records the immutable attempt, its append-only state transitions, error class, and sanitized error metadata without marking the story as published

#### Scenario: A state transition occurs
- **WHEN** a publication attempt changes state
- **THEN** the system appends a new transition event and does not overwrite any prior attempt or transition record

#### Scenario: A run processes multiple stories
- **WHEN** one scheduled run creates or edits multiple stories
- **THEN** every resulting publication attempt retains that run's shared `run_id` while preserving its distinct `attempt_id`

#### Scenario: Audit data is persisted
- **WHEN** a publication attempt has request or response metadata
- **THEN** the history retains only the permitted sanitized metadata and excludes credentials, authorization headers, full request payloads, and raw response bodies

### Requirement: Retain run outcomes and controlled deferrals
The system SHALL retain one immutable scheduled-run result for each office invocation at `RUN#{run_id}` / `RESULT`, with exactly one `office_id`, start and completion times, elapsed time, `required_work_completed`, bounded failure reasons, final status (`success`, `success_with_deferred`, `success_with_quarantined_items`, or `failed`), collection outcome, per-office counts and aggregate invocation counts of stories discovered, published, edited, skipped, deferred, quarantined, rejected, and ambiguous. `success` requires all selected eligible revisions to have successful or explicitly skipped terminal outcomes; `success_with_deferred` permits only controlled unstarted deferrals; `success_with_quarantined_items` permits malformed-item quarantine while valid selected work completes; and unresolved selected rejected, ambiguous, or image-invalid work makes the run `failed`. A valid empty collection is successful with zero discovered stories and `required_work_completed=true`. The record SHALL retain sanitized failure context when applicable. Each controlled deferral SHALL be an immutable child at `RUN#{run_id}` / `DEFERRAL#{office_id}#{source_story_id}`, identify its canonical story revision when known, and use reason `story_cap` or `run_budget`. Each malformed collection item SHALL have an immutable quarantine record keyed by its run and array index, limited to its validation error code, affected field, and sanitizer-produced bounded summary; it SHALL not retain raw item content.

#### Scenario: A run reaches a controlled limit
- **WHEN** a run defers otherwise eligible work because of its story cap or processing deadline
- **THEN** history retains the deferral reason and the run completes as `success_with_deferred` unless an independent failure occurs

#### Scenario: An office collection fails
- **WHEN** an active office collection fails during its scheduled invocation
- **THEN** history retains that office's collection failure and the run completes as `failed`

#### Scenario: A run completes with no stories
- **WHEN** an active office collection succeeds with an empty `stories` array
- **THEN** history records `success`, zero discovered stories, and the elapsed time, distinguishing the outcome from a collection failure

#### Scenario: A run quarantines malformed items
- **WHEN** a valid collection envelope contains malformed items and valid items can be processed
- **THEN** history retains one bounded quarantine record per malformed array item, increments the run's `quarantined` count, and records `success_with_quarantined_items` unless an independent failure occurs

### Requirement: Retain alert deduplication state
The system SHALL retain DynamoDB alert-state records keyed by deterministic alert fingerprint, including severity, first-seen and last-seen times, occurrence count, latest run/correlation ID, cooldown expiry, and latest dispatch outcome. Alert state SHALL be conditionally updated so concurrent matching failures do not cause duplicate notifications.

#### Scenario: Concurrent matching failures are received
- **WHEN** two matching alert events are processed concurrently
- **THEN** only one event obtains the immediate-notification decision and the alert-state occurrence count reflects both events

### Requirement: Commit image references only after verified upload
The system SHALL write a usable current-image reference only after the corresponding S3 object has been uploaded successfully and verified by checksum, content type, and size. It SHALL promote the verified object from `staging/` to a deterministic current-image key before committing that key to the current-story record; a committed current-story record SHALL never reference an object under `staging/`.

#### Scenario: Upload succeeds and history commit fails
- **WHEN** the S3 upload succeeds but the history commit fails
- **THEN** the image remains uncommitted under `staging/`, is not used for Telegram publication, and is eligible for cleanup or safe retry

#### Scenario: Image upload is partial or fails
- **WHEN** an image upload fails or produces an object that does not match the expected integrity metadata
- **THEN** the history does not expose the object as usable for publication and records the image failure

### Requirement: Reconcile incomplete image uploads
The system SHALL identify and clean up S3 `staging/` image objects that are not referenced by a committed current-story record. A current image SHALL be deleted only when it is replaced; expiration SHALL retain the current image indefinitely. S3 versioning retains noncurrent versions for 30 days for recovery.

#### Scenario: Orphan staging object exists
- **WHEN** an S3 staging object has no corresponding committed history reference after 7 days
- **THEN** the system deletes the object and records the cleanup outcome

### Requirement: Validate committed image references
The system SHALL verify that every committed image reference resolves to an S3 object with matching checksum and metadata before publication.

#### Scenario: Committed object is missing or invalid
- **WHEN** a committed image cannot be retrieved or fails integrity validation
- **THEN** the system does not publish the image, records the failure, and raises an operational alert

### Requirement: Retain publication state transitions and reconciliation audit
The system SHALL retain every append-only publication-attempt state transition, lease timestamp, and operator reconciliation action with the linked attempt and run records.

#### Scenario: An operator reconciles an ambiguous attempt
- **WHEN** an operator changes an ambiguous attempt to `confirmed_received` or `confirmed_not_received`
- **THEN** the history appends a transition event that records the operator identity, action time, prior state, resulting state, and reconciliation reason

### Requirement: Support lightweight story analysis
The system SHALL retain durable first-discovered story facts, current state, publication outcomes, and delivery timing that can be queried for fun and interesting facts. The system SHALL NOT support analysis of superseded story revisions or historical image versions.

#### Scenario: An operator investigates publishing activity
- **WHEN** an authorized operator queries the history store
- **THEN** they can retrieve a story's first-discovered/current facts and its associated publication outcomes

### Requirement: Retain and recover durable history
Committed `OFFICE#{office_id}/CURRENT` and current-story records SHALL have no TTL or automatic deletion. Publication attempts, transition events, run results, quarantine records, and alert-fingerprint state SHALL set one table-wide TTL attribute to a numeric Unix-epoch timestamp 30 days after creation or latest update; consumers SHALL treat items past that timestamp as expired before asynchronous TTL deletion completes. Current S3 image objects SHALL be deleted only when replaced, never because their story expires; S3 noncurrent versions and uncommitted staging objects SHALL retain their 30-day and 7-day lifecycle policies. Permanent deletion of retained office/story records SHALL be a manual, authorized, audited operator procedure and SHALL NOT be performed by runtime functions.

The system SHALL enable DynamoDB point-in-time recovery with a 35-day recovery window and create one monthly AWS Backup snapshot retained for one year. An operator SHALL create an on-demand DynamoDB backup before any planned destructive migration or table replacement. The system SHALL document a same-Region recovery runbook and execute it quarterly: restore DynamoDB to a new isolated table, reapply required configuration, validate sampled current-story and operational audit records, then destroy the isolated restore resources after recording the exercise result.

#### Scenario: An accidental table write or deletion is discovered
- **WHEN** an operator identifies unintended DynamoDB data loss or corruption within the prior 35 days
- **THEN** the operator restores the affected point in time to a new table using the documented recovery runbook without overwriting the source table

#### Scenario: A planned destructive change is required
- **WHEN** an operator plans a destructive DynamoDB migration or table replacement
- **THEN** the operator creates and records an on-demand backup before the change proceeds

#### Scenario: A quarterly recovery exercise occurs
- **WHEN** the scheduled quarterly recovery exercise is performed
- **THEN** the operator restores a new isolated table, reapplies required non-data settings, verifies sampled history and retained S3 image checksums, records the result, and removes the exercise resources
