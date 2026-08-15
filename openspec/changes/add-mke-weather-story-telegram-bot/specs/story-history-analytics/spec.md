## Purpose

Maintain a durable, queryable history of NWS Weather Stories and their publication outcomes for deduplication, audit, and analytics.

## ADDED Requirements

### Requirement: Persist Weather Story history
The system SHALL durably retain an immutable discovery snapshot for every distinct normalized Weather Story revision, keyed by canonical `(office_id, source_story_id)` and deterministic revision hash. The system SHALL also maintain a current-story projection derived from immutable history for each canonical identity, including the current revision, source `updateTime`, source `endTime`, lifecycle status, retained image location and metadata when available, the office-specific Telegram channel/message reference, and latest publication status. The projection SHALL be used for fast deduplication and processing decisions and SHALL NOT replace the immutable history.

#### Scenario: A story is first discovered
- **WHEN** the system processes a Weather Story identity not already present in history
- **THEN** it creates an immutable discovery snapshot, a current-story projection, and a revision hash for that story

#### Scenario: A changed story is discovered
- **WHEN** the system processes a previously known story identity with a revision hash not already present in history
- **THEN** it creates a new immutable snapshot and advances the current-story projection without modifying earlier snapshots or publication-attempt records

#### Scenario: An unchanged story is discovered again
- **WHEN** the system processes a story identity and revision hash already present in history
- **THEN** it records the observation or last-seen time without creating a duplicate snapshot or revision

#### Scenario: A story expires
- **WHEN** the current time reaches or passes the source `endTime`
- **THEN** it marks the current-story projection expired while retaining all snapshots, images, and Telegram publication history

#### Scenario: A story is absent before expiration
- **WHEN** a story is absent from a successful collection and its source `endTime` is in the future
- **THEN** it remains in the current-story projection and is not tombstoned or deleted

#### Scenario: Two offices expose the same source story ID
- **WHEN** two office entries return the same source story ID
- **THEN** history retains separate snapshots, current projections, and publication records for each `(office_id, source_story_id)` pair

#### Scenario: A story includes a downloaded image
- **WHEN** the system retrieves an image for a Weather Story
- **THEN** the story history retains the image bytes and queryable image metadata associated with that story

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
The system SHALL retain one immutable scheduled-run record for each office invocation, keyed by `run_id`, with exactly one `office_id`, start and completion times, elapsed time, `required_work_completed`, bounded failure reasons, final status (`success`, `success_with_deferred`, `success_with_quarantined_items`, or `failed`), collection outcome, per-office counts and aggregate invocation counts of stories discovered, published, edited, skipped, deferred, quarantined, rejected, and ambiguous. `success` requires all selected eligible revisions to have successful or explicitly skipped terminal outcomes; `success_with_deferred` permits only controlled unstarted deferrals; `success_with_quarantined_items` permits malformed-item quarantine while valid selected work completes; and unresolved selected rejected, ambiguous, or image-invalid work makes the run `failed`. A valid empty collection is successful with zero discovered stories and `required_work_completed=true`. The record SHALL retain sanitized failure context when applicable. Each controlled deferral SHALL identify its canonical story revision when known and use reason `story_cap` or `run_budget`. Each malformed collection item SHALL have an immutable quarantine record keyed by its run and array index, limited to its validation error code, affected field, and sanitizer-produced bounded summary; it SHALL not retain raw item content.

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
The system SHALL write a usable image reference to story history only after the corresponding S3 object has been uploaded successfully and verified by checksum, content type, and size. It SHALL promote the verified object from `staging/` to a deterministic retained-image key before committing that retained key as usable history; committed history SHALL never reference an object under `staging/`.

#### Scenario: Upload succeeds and history commit fails
- **WHEN** the S3 upload succeeds but the history commit fails
- **THEN** the image remains uncommitted under `staging/`, is not used for Telegram publication, and is eligible for cleanup or safe retry

#### Scenario: Image upload is partial or fails
- **WHEN** an image upload fails or produces an object that does not match the expected integrity metadata
- **THEN** the history does not expose the object as usable for publication and records the image failure

### Requirement: Reconcile incomplete image uploads
The system SHALL identify and clean up S3 `staging/` image objects that are not referenced by a committed story-history record. Current retained-image objects SHALL be retained indefinitely; S3 lifecycle management transitions them to colder storage rather than expiring them.

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

### Requirement: Support historical analysis
The system SHALL retain story history in a durable store that can be queried to analyze discovered stories, publication outcomes, and delivery timing.

#### Scenario: An operator investigates publishing activity
- **WHEN** an authorized operator queries the history store
- **THEN** they can retrieve story records and their associated publication outcomes

### Requirement: Retain and recover durable history
Committed DynamoDB story, attempt, transition, run, projection, and quarantine records SHALL have no TTL or automatic deletion. Current retained S3 image objects SHALL have no expiration, subject to the existing lifecycle transitions; S3 noncurrent versions and uncommitted staging objects SHALL retain their existing 30-day and 7-day lifecycle policies. Permanent deletion of committed history or retained images SHALL be a manual, authorized, audited operator procedure and SHALL NOT be performed by runtime functions.

The system SHALL enable DynamoDB point-in-time recovery with a 35-day recovery window and create one monthly AWS Backup snapshot retained for one year. An operator SHALL create an on-demand DynamoDB backup before any planned destructive migration or table replacement. The system SHALL document a same-Region recovery runbook and execute it quarterly: restore DynamoDB to a new isolated table, reapply required configuration, validate history and checksums against sampled retained S3 image versions, then destroy the isolated restore resources after recording the exercise result.

#### Scenario: An accidental table write or deletion is discovered
- **WHEN** an operator identifies unintended DynamoDB data loss or corruption within the prior 35 days
- **THEN** the operator restores the affected point in time to a new table using the documented recovery runbook without overwriting the source table

#### Scenario: A planned destructive change is required
- **WHEN** an operator plans a destructive DynamoDB migration or table replacement
- **THEN** the operator creates and records an on-demand backup before the change proceeds

#### Scenario: A quarterly recovery exercise occurs
- **WHEN** the scheduled quarterly recovery exercise is performed
- **THEN** the operator restores a new isolated table, reapplies required non-data settings, verifies sampled history and retained S3 image checksums, records the result, and removes the exercise resources
