# API Documentation

## External HTTP APIs

### National Weather Service Office Resource

- **Method**: `GET`
- **Path**: `https://api.weather.gov/offices/{office_id}`
- **Purpose**: Enrich each seeded office with public office and regional metadata.
- **Request**: Identifying User-Agent, JSON-LD-compatible Accept header, ten-second timeout.
- **Response**: Flat JSON-LD office fields validated by `NWSOfficeResponse`.

### National Weather Service Regional Office Resource

- **Method**: `GET`
- **Path**: The validated `parentOrganization` URL from the office response.
- **Purpose**: Enrich an office record with regional-office name and public URL.
- **Security**: Must be an HTTPS `api.weather.gov/offices/{ID}` URL without user info, custom port,
  query, or fragment.

### National Weather Service Weather Stories

- **Method**: `GET`
- **Path**: `https://api.weather.gov/offices/{office_id}/weatherstories`
- **Purpose**: Retrieve the complete collection for one active office.
- **Request**: Identifying User-Agent, JSON-compatible Accept header, ten-second request timeout.
- **Response**: A complete collection envelope with independently validated story items; advertised
  pagination is rejected.
- **Retry Contract**: At most one retry for `429` with valid `Retry-After`, `5xx`, connection error,
  or timeout, and only when the delay, request timeout, and shutdown reserve fit the run deadline.

### NWS Story Image

- **Method**: `GET`
- **Path**: Absolute HTTPS download URL contained in a validated story.
- **Purpose**: Download the current JPEG or PNG for retention and publication.
- **Security and Limits**: Host allowlist, at most three safe redirects, 20 seconds, 9 MiB,
  non-animated decode, 25 megapixels, dimension sum at most 10,000, and aspect ratio at most 20.

### Telegram Bot API

- **Operations**: Send one photo or edit one existing photo message.
- **Purpose**: Publish a new current story or replace its current photo/caption in place.
- **Request**: Explicit caption entities, no parse mode, retained and revalidated media bytes.
- **Response**: Positive acknowledgement with message reference, definitive rejection metadata, or
  an ambiguous outcome. Raw bodies are not retained.

## AWS Lambda Event APIs

### Publisher Handler

- **Function**: `publisher_handler(event, context) -> None`
- **Request**: A mapping containing exactly `{"office_id": "MKX"}` for the MVP.
- **Behavior**: Delegates to the configured `PublisherRuntime.process_office` implementation.
- **Validation**: Rejects extra, missing, blank, or non-string fields and an unconfigured runtime.
- **Deployment Status**: Handler exists; complete runtime composition and SAM wiring are planned.

### Reconciliation Handler

- **Function**: `reconciliation_handler(event, context) -> dict[str, object]`
- **Request Fields**: `attempt_id`, `operator_id`, `reason`, `outcome`, and optional `message_ref`.
- **Allowed Outcomes**: `confirmed_received` or `confirmed_not_received`.
- **Response Fields**: Safe attempt ID, resulting outcome, and whether a transition was applied.
- **Authorization Boundary**: Intended for IAM-protected console or CLI invocation.

## Internal APIs

### Configuration

- `load_seed_set(path) -> NWSOfficeSeedSet` - Load the versioned office seed input.
- `load_environment_config(path) -> EnvironmentConfig` - Validate one non-secret environment.
- `validate_environment_isolation(configs) -> None` - Require exactly dev/staging/prod and distinct
  live destinations.
- `weather_stories_url(office_id) -> str` - Construct the canonical NWS collection endpoint.
- `validate_telegram_secret(secret_json) -> str` - Validate and return a nonblank token without
  logging or retaining it in a model.
- `derive_timezone(coordinates) -> str` - Derive and validate an IANA timezone.

### Ingestion and NWS Client

- `OfficeRegistrySeeder.seed(seed_set, environment) -> OfficeRegistry` - Enrich every seed and
  activate only configured offices.
- `NWSCollectionClient.fetch(url, processing_deadline) -> httpx.Response` - Perform a bounded NWS
  request with classified retry behavior.
- `OfficeWeatherStoryRetriever.retrieve(registry, office_id, processing_deadline) -> NormalizedCollection`
  - Retrieve only one known active office.
- `normalize_collection(response, office_id) -> NormalizedCollection` - Validate the envelope and
  return valid stories plus bounded quarantines.
- `parse_retry_after(value, now) -> float | None` - Parse seconds or an HTTP date into a
  non-negative delay.

### History Store

- `put_office(...)` - Persist or conditionally update one current office record.
- `get_current_office(office_id)` - Read one current office record.
- `get_current_story(office_id, source_story_id)` - Read one current story projection.
- `list_current_stories(office_id)` - Query current stories through `office-current-index`.
- `observe_story(story, image_sha256)` - Compute a revision hash and conditionally advance current
  story state.
- `commit_image(...)` and `mark_image_invalid(...)` - Transition current-image state.
- `expire_due_stories(office_id, now)` - Mark due stories expired without deleting them.
- `put_quarantine(...)`, `put_deferral(...)`, and `put_run(...)` - Persist bounded operational facts.
- `reserve_publication(...)` - Acquire a leased create/edit reservation or report a race.
- `start_publication_send(reservation)` - Atomically permit the reservation's one external call.
- `transition_publication(...)` - Append a legal outcome transition and update current facts.
- `reconcile_ambiguous_attempt(...)` - Conditionally append an authorized reconciliation result.
- `get_run_result`, `list_quarantined_items`, and `get_publication_attempt` - TTL-aware review APIs.

### Image Retention

- `ImageRetainer.download(url) -> ValidatedImage` - Download and fully validate source media.
- `ImageRetainer.retain(...) -> ImageMetadata` - Stage, verify, promote, and commit a current image.
- `ImageRetainer.delete_current_image(image) -> None` - Delete only a current-namespace object.
- `StagingReconciler.cleanup(older_than) -> int` - Paginate and delete old staging objects.

### Telegram Publishing

- `render_caption(title, description, alt_text) -> Caption` - Produce a UTF-16-bounded caption with
  an explicit bold-title entity.
- `classify_telegram_response(response) -> tuple[bool, dict[str, str]]` - Return acceptance and
  bounded response metadata.
- `publish_photo(...) -> str` - Revalidate media and make one create or edit call.
- `execute_reserved_publication(...) -> PublicationResult` - Start a reservation, execute it once,
  and persist the terminal result.
- `publish_with_retries(...) -> PublicationResult` - Retry only definitive retryable failures using
  new reservations and the remaining run budget.

### Scheduled Processing

- `OfficeScheduledProcessor.process_office(office_id) -> ScheduledRun` - Run the complete pure
  orchestration for exactly one active office.
- **Limits**: 14-minute processing deadline, 60-second shutdown reserve, and 25 eligible revisions.
- **Ordering**: Priority first, then source order.

## Data Models

### Office Models

- `NWSOfficeSeedSet` - Schema version, public seed source, unique office IDs including MKX.
- `PostalAddress` and `OfficeCoordinates` - Validated address and latitude/longitude.
- `OfficeRegistryRecord` - Canonical endpoint, public NWS metadata, timezone, destination, and
  activation flag.
- `OfficeRegistry` - Unique office records and unique active destinations.
- `EnvironmentConfig` - Environment, Telegram mode, allowlist, active offices, destinations, and
  private-alert recipient reference.

### Story and Collection Models

- `WeatherStory` - Office, start/end/update instants, title, description, alt text, priority, order,
  and HTTPS download URL.
- `NormalizedCollection` - Office ID, valid immutable story tuple, and quarantined item tuple.
- `QuarantinedStoryItem` - Array index, stable validation code, affected field, and bounded summary.

### Publication and Run Models

- `PublicationReservation` - Attempt/run/story/revision identity, operation, owner, lease, and
  optional edit target reference.
- `ImageMetadata` - Deterministic current key, media type, byte size, SHA-256, width, and height.
- `OutcomeCounts` - Non-negative discovered/published/edited/skipped/deferred/quarantined/rejected/
  ambiguous counters.
- `ScheduledRun` - Run ID, terminal status, counts, and required-work result.
- `PublicationResult` - Telegram outcome, optional safe message reference, bounded metadata, and
  retry/defer facts.
