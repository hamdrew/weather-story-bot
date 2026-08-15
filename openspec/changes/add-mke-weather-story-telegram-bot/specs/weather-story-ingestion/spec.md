## Purpose

Retrieve current Weather Stories from configured NWS offices and make their content and images available for reliable automated publishing, while enabling MKX first.

## ADDED Requirements

### Requirement: Maintain versioned source-contract fixtures
The test plan SHALL maintain sanitized, versioned NWS collection fixtures captured from representative successful and error responses. Fixtures SHALL cover complete collections, empty collections, unsupported pagination, missing required fields, unknown fields, changed revisions, and story omission from a later successful collection. Contract tests SHALL validate that normalization, identity, revision detection, expiration/omission handling, quarantine, and run-result classification remain compatible with those fixtures. Fixtures SHALL contain no credentials or sensitive operational identifiers.

#### Scenario: An NWS contract changes unexpectedly
- **WHEN** a captured response no longer satisfies the supported envelope or item contract
- **THEN** the contract test fails with the affected fixture and the implementation does not silently claim complete retrieval

### Requirement: Maintain a seeded and validated office registry
The system SHALL seed one registry entry for every NWS office from a versioned office-ID seed set and SHALL use `https://api.weather.gov/offices/{office_id}` and the referenced region resource to verify and enrich each entry. Each entry SHALL contain a unique `office_id`, absolute HTTPS `weather_stories_url`, `display_name`, postal address, geocoded latitude and longitude, IANA `timezone` derived from those coordinates, distinct `telegram_channel_id`, and `active` state, plus the NWS telephone, email, office-home URL, region name, and region-home URL when supplied. An inactive entry MAY have no Telegram channel identifier; an active entry SHALL have a non-empty, distinct Telegram channel identifier. The system SHALL poll and publish only active entries.

#### Scenario: An office is onboarded
- **WHEN** the versioned office-ID seed set is loaded or refreshed
- **THEN** the system retrieves `https://api.weather.gov/offices/{office_id}` for each entry to seed and verify the office ID, NWS display name, postal address, telephone, email, office-home URL, and region reference/details; geocodes the postal address, persists the validated latitude and longitude, derives the registry timezone from those coordinates using a timezone lookup tool; and requires the resulting coordinates/IANA timezone, absolute HTTPS Weather Stories URL, office-home URL, and Telegram channel before activating an office

#### Scenario: An office registry entry is invalid
- **WHEN** an entry has a duplicate or missing office ID, a non-HTTPS or missing Weather Stories URL, missing display name/geocoded coordinates/timezone, out-of-range coordinates, an invalid IANA timezone, or a failed NWS office lookup
- **THEN** the system rejects the entry and does not poll or publish for that office

#### Scenario: An active office lacks a channel
- **WHEN** an entry is marked active without a unique non-empty Telegram channel identifier
- **THEN** the system rejects activation and does not schedule, poll, or publish for that office

#### Scenario: Office endpoint does not match the common contract
- **WHEN** an active office's configured Weather Stories URL returns a response that does not satisfy the required common `stories[]` and image-download contract
- **THEN** the system rejects that retrieval as unsupported, records the office-specific failure, and raises an operational alert

### Requirement: Retrieve configured office Weather Stories
The system SHALL retrieve the current story collection for exactly one active National Weather Service office—the office ID supplied in that invocation's Scheduler payload—using that office's Weather Stories API. Requests SHALL include an identifying `User-Agent` and SHALL request JSON-compatible content negotiation. A valid story's source `altText` SHALL be retained as bounded plain-text accessibility content for the publisher; no synthetic office, timestamp, or source-link fields are required for the Telegram caption.

#### Scenario: An active office has Weather Stories
- **WHEN** an active office's Weather Stories API responds successfully with one or more stories
- **THEN** the system identifies each returned story by the canonical `(office_id, source_story_id)` pair, where `source_story_id` is the UUID in its absolute `download` URL; preserves the office ID, start time, end time, update time, title, description, alt text, priority, order, and download URL; and makes the record available for processing

#### Scenario: An active office has no Weather Stories
- **WHEN** an active office's Weather Stories API responds successfully with no stories
- **THEN** the run completes without publishing a Telegram message for that office

#### Scenario: MKX is the only active MVP office
- **WHEN** the service is deployed for the initial implementation
- **THEN** the seeded registry contains all NWS offices, `MKX` is the only active entry, and no other office is scheduled or implemented for publication

### Requirement: Persist an objective single-office run result
Every invocation SHALL persist one immutable run result containing `run_id`, exactly one `office_id`, start and completion timestamps, elapsed time, collection status, status, a `required_work_completed` boolean, bounded failure reasons, and counts for `discovered`, `published`, `edited`, `skipped`, `deferred`, `quarantined`, `rejected`, and `ambiguous` outcomes. It SHALL also persist an aggregate count object equal to the sum of the invocation's per-office results; because an invocation processes exactly one office, the aggregate currently contains that office's counts without implying cross-office batching.

The only run statuses SHALL be `success`, `success_with_deferred`, `success_with_quarantined_items`, and `failed`. `success` requires a valid collection and every selected eligible revision reaching a successful or explicitly skipped terminal outcome, with no unresolved required work. `success_with_deferred` has the same requirement but includes only controlled `story_cap` or `run_budget` deferrals for unstarted eligible work. `success_with_quarantined_items` has the same requirement while one or more malformed collection items are quarantined. `failed` applies to collection failure, required-outcome persistence failure, or any selected required revision ending rejected, ambiguous, or image-invalid without an approved terminal handling path. A valid empty collection is `success` with `discovered=0` and `required_work_completed=true`.

After durably persisting a failed run result, the handler SHALL return normally so the run status—not an opaque invocation exception—determines operational success. It MAY return an invocation failure only when it cannot persist the required run result.

#### Scenario: A selected publication remains unresolved
- **WHEN** a selected revision ends rejected, ambiguous, or image-invalid without an approved terminal handling path
- **THEN** the run persists `failed`, increments the corresponding outcome count, sets `required_work_completed=false`, and the handler returns normally after persistence

#### Scenario: An office has no stories
- **WHEN** a valid collection contains no stories
- **THEN** the run persists `success`, `discovered=0`, zero publication failures, and `required_work_completed=true`

### Requirement: Validate the NWS Weather Stories contract
The system SHALL first validate a successful NWS Weather Stories response as a collection envelope: a JSON-compatible object containing a `stories` array and no unsupported pagination metadata. It SHALL then validate each array item independently. A valid item SHALL contain `officeId`, `startTime`, `endTime`, `updateTime`, `title`, `description`, `altText`, `priority`, `order`, and an absolute HTTPS `download` URL whose final path segment is a UUID. Timestamps SHALL be parsed as ISO-8601 date-times, and `priority` and `order` SHALL retain their boolean and integer types. Unknown fields SHALL be tolerated and ignored for normalization.

#### Scenario: Valid current story collection
- **WHEN** the response has status `200`, content type `application/ld+json` or another JSON-compatible content type, and a valid collection envelope whose items are valid
- **THEN** the system normalizes every story using the required fields and uses the configured office ID plus the UUID from `download` as the canonical story identity

#### Scenario: Source UUID appears in more than one office
- **WHEN** the same `source_story_id` is returned for two different office IDs
- **THEN** the system retains and processes the stories independently using their distinct canonical identities and emits a WARNING log naming both office IDs and the shared source story ID

#### Scenario: Empty current story collection
- **WHEN** the response has status `200` and `stories` is an empty array
- **THEN** the system treats the collection as successfully retrieved and produces no story records for that office

#### Scenario: Collection envelope is malformed
- **WHEN** a successful response is not JSON-compatible, is not an object, has no `stories` array, or advertises unsupported pagination metadata
- **THEN** the system treats the retrieval as invalid, records a bounded collection-level validation failure, processes no item from that response, and marks the office run failed

#### Scenario: One story item is malformed
- **WHEN** a valid collection envelope contains an item missing a required field, with an invalid field type/date, or with an invalid/non-HTTPS download URL or UUID
- **THEN** the system creates an immutable quarantine record for that item containing only the run ID, array index, validation error code, affected field, and sanitizer-produced bounded summary; it does not create a story identity, snapshot, image download, or publication attempt for that item; and it continues processing the other valid items

#### Scenario: Collection contains valid and malformed items
- **WHEN** a valid collection envelope contains one or more valid items and one or more quarantined malformed items
- **THEN** the system processes every valid item, increments the run's `quarantined` count, emits the quarantine metric and deduplicated operational error alert, and completes the run as `success_with_quarantined_items` unless an independent run-failure condition occurs

#### Scenario: Upstream error response
- **WHEN** the NWS endpoint returns a non-success status with an `application/problem+json` payload
- **THEN** the system records the HTTP status, problem type, title, detail, instance, correlation ID when present, and parameter errors when present, without treating the response as a story collection

### Requirement: Handle Weather Stories collection pagination
The system SHALL process the complete `stories` array returned by the Weather Stories endpoint. Because the observed contract does not expose pagination links or cursors, the system SHALL treat the response as complete and SHALL fail validation rather than silently dropping data if a future response advertises unsupported pagination metadata.

#### Scenario: Current response has no pagination metadata
- **WHEN** a valid response contains only its `stories` collection and no pagination link or cursor
- **THEN** the system processes every story in that collection exactly once for the run

#### Scenario: Upstream introduces unsupported pagination
- **WHEN** a response contains a pagination link, cursor, or continuation indicator that the service does not support
- **THEN** the system records an unsupported-contract error and does not claim that the complete collection was retrieved

### Requirement: Detect Weather Story revisions and expiration
The system SHALL compute a deterministic revision hash from the normalized story content and image identity/bytes, SHALL retain each distinct revision without overwriting earlier observations, and SHALL use the source `endTime` as the story's expiration time. A story SHALL remain eligible for current-story processing until its expiration time, even if it is omitted from a later successful collection; a failed or invalid retrieval SHALL not change current or expiration state.

#### Scenario: Story is discovered with unchanged content
- **WHEN** a successful poll returns a story identity and revision hash already recorded for that story
- **THEN** the system records the observation without creating a new revision or publication event

#### Scenario: Story content or image changes under the same identity
- **WHEN** a successful poll returns the same source story identity with a different revision hash
- **THEN** the system creates an immutable revision snapshot, advances the current-story projection to that revision, and makes the revision eligible to update the existing Telegram publication

#### Scenario: Story reaches its expiration time
- **WHEN** the current time is at or after a story's source `endTime`
- **THEN** the system marks the current-story projection as expired, retains all snapshots and publication history, and does not create a new publication or revision solely because of expiration

#### Scenario: Story is omitted before expiration
- **WHEN** a story is absent from a successful collection but its source `endTime` has not passed
- **THEN** the system retains its current projection and does not mark it deleted or expired

#### Scenario: Source identity is reused with changed content
- **WHEN** a source story identity returns content that differs from every previously retained revision
- **THEN** the system retains the prior revisions unchanged and creates a new revision under the same source identity

### Requirement: Retrieve and retain story images
The system SHALL retrieve an image from the absolute HTTPS URL in a new story's `download` field and SHALL retain an accepted image in durable story history. The source and every redirect destination SHALL use HTTPS and match the configured NWS image-host allowlist, initialized to `weather.gov` and `*.weather.gov`; at most three redirects are permitted. The image URL SHALL be stored as protected source metadata, while the UUID extracted from that URL SHALL be stored as the stable story identity and image source identifier.

#### Scenario: New story includes a downloadable image
- **WHEN** a newly discovered Weather Story has a valid `download` URL
- **THEN** the system obtains the image from that URL, records the returned content type and integrity metadata, retains it durably, and makes it available for Telegram publication

#### Scenario: Image download fails or returns an invalid response
- **WHEN** an image URL cannot be retrieved successfully or returns an unsupported/non-image response
- **THEN** the system records the image failure, does not make the story publishable, and raises the existing operational alert

### Requirement: Validate image bytes and resource limits before retention
The system SHALL stream image downloads with a 20-second deadline and a 9 MiB compressed-byte limit, rejecting an absent, malformed, or exceeding response without buffering beyond that limit. It SHALL accept only non-animated JPEG (`image/jpeg`) or PNG (`image/png`) images whose declared content type and magic bytes agree. Before committing the image, it SHALL defensively decode it and require at most 25 megapixels, a width-plus-height no greater than 10,000 pixels, and a width-to-height ratio no greater than 20. It SHALL compute SHA-256 while streaming and retain the resulting checksum with the verified content type, byte size, and dimensions. A partial download, checksum/decoder failure, type mismatch, redirect-policy failure, or resource-limit failure SHALL be an image failure: no retained-image reference or publication attempt is created for that revision, and the existing alert workflow is invoked.

#### Scenario: Declared and actual image types disagree
- **WHEN** an image response declares an allowed type but its magic bytes identify another type, or it is not a JPEG or PNG
- **THEN** the system rejects it as an image validation failure without creating a retained object or Telegram publication attempt

#### Scenario: Image exceeds a resource or Telegram photo limit
- **WHEN** streaming bytes exceed 9 MiB, decoding exceeds 25 megapixels, width plus height exceeds 10,000 pixels, or the aspect ratio exceeds 20
- **THEN** the system stops or rejects the download, records the bounded validation failure, and does not make the revision publishable

#### Scenario: Image redirect leaves the allowed NWS hosts
- **WHEN** an image source or any of its more than three redirects is non-HTTPS or does not match the configured NWS image-host allowlist
- **THEN** the system rejects the download before retrieving bytes from that destination and raises the existing operational alert

### Requirement: Handle upstream API failures
The system SHALL classify and record an unsuccessful collection retrieval and raise an operational alert when it cannot successfully obtain the current Weather Story collection for an active office. A `404` or non-`429` `4xx` response is non-retryable and fails the collection immediately. A `429` response is retried once only when its `Retry-After` delay and a new request fit before the 60-second shutdown reserve. A `5xx` response, connection failure, or request timeout is retried once after one second only when it fits before that reserve. If the permitted retry cannot start or does not succeed, the collection fails and the next scheduled poll re-attempts it. The system SHALL retain only HTTP status, stable error class/code, Retry-After value when present, retry decision/ordinal, and a sanitizer-produced bounded error summary; it SHALL not retain the raw NWS problem body or unbounded upstream error text.

#### Scenario: NWS API request fails
- **WHEN** an active office's Weather Stories API request fails or returns an invalid response
- **THEN** the system does not mark any unprocessed story as published and raises an operational alert with office-specific failure context

#### Scenario: NWS rate-limits a collection request
- **WHEN** the NWS endpoint returns `429` with a `Retry-After` value that fits before the shutdown reserve
- **THEN** the system waits at least that duration, makes one retry, and records the retry decision and result

#### Scenario: NWS has a transient collection failure
- **WHEN** the NWS request returns `5xx`, times out, or has a connection failure and one-second retry plus a new request fit before the shutdown reserve
- **THEN** the system makes one retry and records the retry decision and result

### Requirement: Summarize each office invocation
The system SHALL produce one durable summary for the single active `office_id` processed by each invocation. The summary SHALL include collection result; counts of stories discovered, published or edited, skipped, deferred, quarantined, rejected, and ambiguous; elapsed time; and final status (`success`, `success_with_deferred`, `success_with_quarantined_items`, or `failed`). The invocation SHALL return failure when the office collection fails or the service cannot durably persist its required run outcome. It SHALL return success for a valid empty collection, normal skips, controlled deferrals, and successfully processed collections that quarantine one or more malformed items. Handled per-story Telegram delivery failures SHALL be counted and alerted but SHALL NOT alone make the invocation fail.

#### Scenario: A Telegram delivery fails after collection succeeds
- **WHEN** the office collection succeeds and a story's Telegram publication is rejected or ambiguous
- **THEN** the summary increments the relevant outcome count, the existing alert workflow is invoked, and the Lambda still returns success unless an independent run-failure condition occurs
