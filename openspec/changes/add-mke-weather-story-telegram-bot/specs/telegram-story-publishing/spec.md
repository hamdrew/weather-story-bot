## Purpose

Publish Weather Stories from each enabled National Weather Service office to that office's configured Telegram channel with at most one automatic Telegram API attempt per reservation and explicit reconciliation for ambiguous outcomes.

## ADDED Requirements

### Requirement: Maintain a pinned office-information message
The deployment SHALL provision a separate on-demand office-info Lambda that queries the current NWS office and region information, obtains or creates an invite link for the configured channel, and creates or edits exactly one durable pinned office-information message for that channel. This message is separate from Weather Story publication messages and SHALL not be managed by the story publication-attempt state machine. The Lambda SHALL locate the existing managed message by its durable office record/message reference or an explicit managed marker, update it in place when content changes, and pin it; it SHALL never create a duplicate when the managed message already exists. Dev SHALL simulate all Telegram operations; staging and prod SHALL perform the real operation only for their dedicated channel.

The pinned message SHALL use explicit Telegram entities rather than MarkdownV2/HTML and SHALL be neatly structured with a bold NWS office heading, office ID, office-home link, Weather Stories link, region name and region-home link, postal address, telephone, email, timezone, and channel invite link. Office-home and Weather Stories links SHALL appear before telephone/email. Optional telephone, email, region name/link, or address rows MAY be omitted when NWS does not supply them; the office name, office ID, office-home URL, Weather Stories URL, and invite link are required for a valid pin. The invite link SHALL not be emitted in CloudFormation outputs or logs.

#### Scenario: Office information is pinned on demand
- **WHEN** an authorized operator invokes the office-info Lambda for an active staging or prod office
- **THEN** it queries NWS, creates or reuses the channel invite link, creates or edits the one managed information message, pins it, and records the message/link references without creating a Weather Story publication attempt

#### Scenario: Office information changes
- **WHEN** a later invocation observes changed NWS office/region data or link configuration
- **THEN** it edits the existing managed pinned message in place and leaves Weather Story messages and publication history unchanged

#### Scenario: Pinning cannot be verified
- **WHEN** the Lambda cannot query required NWS data, manage the invite link, edit/create the message, or pin it
- **THEN** it emits the existing operational alert, leaves that office's scheduler disabled, and does not claim the office is ready

#### Scenario: An optional NWS field is absent
- **WHEN** NWS omits telephone, email, address, or region details
- **THEN** the pinner omits only that optional row and can still produce a valid message when required fields are present

### Requirement: Publish Weather Stories as one photo message
The system SHALL publish each newly discovered Weather Story as exactly one photo message to its office's configured Telegram channel. The retained image SHALL be the message media and the title and story text SHALL be in that photo's caption; the system SHALL NOT send a companion text message or source link. The title SHALL be bold, followed by one newline and plain-text story text. When the source provides non-empty `altText` and the complete caption including an `Image description: ` line fits within Telegram's limit, the caption SHALL append two newlines followed by `Image description: ` and that plain-text description. If the complete description section does not fit, it SHALL be omitted rather than displacing the title/body; the existing body truncation rule then applies if needed. Telegram captions SHALL NOT include the office ID or display name, and SHALL NOT add issued/updated timestamp fields. For a material revision of an already published story, the system SHALL edit that existing photo message in place and replace its photo when the retained image revision changes.

#### Scenario: New story is discovered
- **WHEN** a Weather Story not previously recorded as published is retrieved successfully
- **THEN** the system posts one photo message with the retained image and caption to that story's office-specific Telegram channel without an office identifier in the caption

#### Scenario: Revision of a published story is discovered
- **WHEN** a previously published story identity receives a new material revision before its expiration time
- **THEN** the system edits the existing Telegram message in place, swaps in the revised retained photo when the image changed, and updates the story text in the caption

#### Scenario: Revision is discovered before initial publication
- **WHEN** a story has retained revisions but no successful Telegram publication exists and the current revision is publishable
- **THEN** the system posts the current revision as a new Telegram message and records its message reference for future in-place edits

#### Scenario: Telegram message edit fails definitively
- **WHEN** Telegram definitively rejects an edit before accepting it
- **THEN** the system records the failed revision edit, preserves the prior publication state and message reference, and raises an operational alert without creating a second message

#### Scenario: Telegram edit outcome is ambiguous
- **WHEN** the result of an in-place edit is unknown because of timeout, interruption, or lost response
- **THEN** the system records an ambiguous edit outcome, alerts the operator, and does not automatically create a replacement message

### Requirement: Prevent duplicate channel publications
The system SHALL use the stable NWS story identity and revision hash to ensure each revision is applied at most once to the existing Telegram message, while preserving the message reference needed for future edits.

#### Scenario: Previously published story is returned again
- **WHEN** a scheduled run retrieves a Weather Story with an identity already recorded as successfully published
- **THEN** the system does not send another Telegram channel message for that story

#### Scenario: Previously applied revision is returned again
- **WHEN** a scheduled run retrieves a story revision already recorded as applied to its Telegram message
- **THEN** the system does not post or edit the Telegram message again for that revision

#### Scenario: Overlapping processing attempts see the same story
- **WHEN** multiple processing attempts encounter the same unposted Weather Story
- **THEN** no more than one successful channel publication is recorded for that story

### Requirement: Enforce the publication-attempt state machine
The system SHALL represent each initial publication or revision-edit attempt using an operation type of `create` or `edit`, a distinct `attempt_id`, its scheduled-processing `run_id`, and only these states: `reserved`, `send_started`, `published`, `rejected`, `ambiguous`, `confirmed_received`, and `confirmed_not_received`. An edit attempt SHALL retain the target Telegram chat/message reference and revision hash. Every state change SHALL append an audit transition event; no state transition may overwrite prior audit history.

#### Scenario: Reservation is acquired
- **WHEN** a new create or edit attempt wins the conditional reservation for a story revision
- **THEN** the attempt enters `reserved` and has a lease expiry

#### Scenario: Send begins
- **WHEN** the publisher is about to call Telegram for a reserved attempt with an unexpired lease
- **THEN** the attempt transitions atomically to `send_started` before the one automatic Telegram send attempt

#### Scenario: Telegram positively acknowledges delivery
- **WHEN** Telegram positively acknowledges the send
- **THEN** the attempt transitions to `published` and records the Telegram message reference

#### Scenario: Telegram positively acknowledges a revision edit
- **WHEN** Telegram positively acknowledges an edit of the existing message and media
- **THEN** the edit attempt transitions to `published` and records the applied revision hash and resulting message reference

#### Scenario: Telegram definitively rejects before acceptance
- **WHEN** Telegram definitively rejects the request before accepting it
- **THEN** the attempt transitions to `rejected`, and a later scheduled run may create a new reservation

#### Scenario: Telegram outcome is ambiguous
- **WHEN** the send response is unknown because of a timeout, interruption, or lost response
- **THEN** the attempt transitions to `ambiguous`, emits an error for monitoring, and is not automatically retried

#### Scenario: Operator reconciles an ambiguous attempt
- **WHEN** the operator invokes the reconciliation Lambda with a valid ambiguous attempt
- **THEN** the operator may transition it to `confirmed_received` if the message arrived or `confirmed_not_received` if it did not, recording operator identity, time, and reason

#### Scenario: Confirmed-not-received attempt is retried
- **WHEN** a scheduled run encounters a story whose latest attempt is `confirmed_not_received`
- **THEN** it may create a new `reserved` attempt for that story

### Requirement: Limit automatic sends per reservation
The system SHALL make no more than one automatic Telegram API call after entering `reserved` for a given publication attempt, and SHALL NOT claim exactly-once external delivery. Any permitted retry SHALL use a new conditional reservation, `attempt_id`, and append-only audit history.

#### Scenario: Reservation send attempt completes ambiguously
- **WHEN** a `send_started` attempt has an ambiguous Telegram outcome
- **THEN** no automatic retry is made for that attempt, even after its lease expires

### Requirement: Apply bounded Telegram retry policy
The system SHALL classify Telegram outcomes and apply retries only when Telegram has definitively rejected the request before accepting it. For a `429` flood-control response with `parameters.retry_after`, the system SHALL record the value and retry using a new attempt only after waiting at least that many seconds. For an explicit Telegram `5xx` response with `ok: false`, the system SHALL retry using a new attempt after exponential backoff of 1 second then 2 seconds. The system SHALL make at most two automatic retries per story revision per run, SHALL defer retry when the required delay would extend beyond the 14-minute processing deadline or leave fewer than 60 seconds before the 15-minute Lambda timeout, and SHALL record every classification, delay, retry ordinal, and retry/defer decision in the attempt audit history.

Explicit `4xx` responses other than `429` SHALL be classified as definitive rejections and SHALL NOT be automatically retried. Network timeouts, connection loss, malformed responses, and any outcome for which Telegram acceptance cannot be determined SHALL be classified as ambiguous and SHALL NOT be automatically retried.

#### Scenario: Telegram returns flood control
- **WHEN** Telegram returns `429` with `parameters.retry_after` and sufficient execution time remains
- **THEN** the system records the flood-control classification and retry-after value, waits at least the specified duration, and creates a new attempt for the retry

#### Scenario: Flood-control delay does not fit the run budget
- **WHEN** a `429` retry-after delay would extend beyond the 14-minute processing deadline or leave fewer than 60 seconds before the 15-minute Lambda timeout
- **THEN** the system records a deferred retry decision and leaves the story eligible for a later scheduled run without issuing another Telegram API call

#### Scenario: Telegram returns a definitive server error
- **WHEN** Telegram returns an explicit `5xx` response with `ok: false` and the retry budget remains
- **THEN** the system records the server-error classification and retries in a new attempt after the applicable exponential-backoff delay

#### Scenario: Retry budget is exhausted
- **WHEN** a story revision has already used two automatic retries in the current run
- **THEN** the system records that the retry budget is exhausted, raises an operational alert, and defers further processing to a later scheduled run

#### Scenario: Telegram rejection is not retryable
- **WHEN** Telegram returns an explicit `4xx` response other than `429`
- **THEN** the system records a definitive rejection and does not automatically retry

#### Scenario: Telegram outcome is unknown
- **WHEN** a network timeout, connection failure, malformed response, or lost response prevents determining whether Telegram accepted the request
- **THEN** the system records an ambiguous outcome, raises an operational alert, and does not automatically retry

### Requirement: Revalidate retained images before Telegram upload
Before every initial photo send or revision photo replacement, the system SHALL revalidate the retained image's SHA-256 checksum, JPEG/PNG magic bytes and content type, byte size at most 9 MiB, non-animated decode, decoded pixels at most 25 megapixels, width-plus-height at most 10,000, and aspect ratio at most 20. The system SHALL enforce these stricter retained-image limits before send so every upload also satisfies Telegram's documented 10 MB, 10,000 dimension-sum, and 20:1 photo constraints. A failed pre-send validation SHALL create no Telegram API call; it SHALL record an image failure and invoke the existing operational alert workflow.

#### Scenario: Retained image is invalid before initial publishing
- **WHEN** an otherwise eligible story's retained image fails pre-send validation
- **THEN** the system does not send a photo message, records the image failure, and raises an operational alert

#### Scenario: Revised image is invalid before editing
- **WHEN** a material revision's retained image fails pre-send validation
- **THEN** the system leaves the existing Telegram message unchanged, records the image failure, and does not issue an edit request

### Requirement: Render captions with safe explicit formatting
The system SHALL construct the base caption as the raw title, one newline, and raw story text. If the complete optional `Image description: {altText}` section fits, it SHALL append it after two newlines; no source link, office identifier/display name, or issued/updated timestamp fields SHALL be added. The system SHALL use one explicit Telegram `bold` caption entity spanning the retained title and SHALL NOT use MarkdownV2, HTML, or a `parse_mode`; all other source characters, including formatting-like characters and the image description, SHALL be literal plain text. The entity's offset and length SHALL be derived from the final caption in UTF-16 code units.

#### Scenario: Title and body are formatted
- **WHEN** the system sends or edits a photo caption
- **THEN** the title is bold, exactly one newline separates it from the plain-text body, and no source characters are interpreted as Markdown or HTML formatting

#### Scenario: Image description fits
- **WHEN** a story has non-empty source `altText` and the complete caption including its image-description section fits within Telegram's limit
- **THEN** the caption appends `Image description: ` and the plain-text description after two newlines, without adding a link or companion message

#### Scenario: Image description does not fit
- **WHEN** the complete image-description section would exceed Telegram's caption limit
- **THEN** the section is omitted and the base title/body caption is rendered and truncated under the existing grapheme-safe rules

#### Scenario: Source contains formatting-like characters
- **WHEN** a title or story body includes characters such as `*`, `_`, `[`, `]`, `<`, or `>`
- **THEN** the caption renders those characters literally outside the explicit bold-title entity

### Requirement: Respect Telegram photo-caption limits
The system SHALL determine caption length from the final explicit-entity caption according to Telegram's post-entity-parsing 1024-character photo-caption limit. If the final caption exceeds that limit, the system SHALL truncate only at Unicode extended grapheme-cluster boundaries, retain the maximum prefix that leaves room for the Unicode ellipsis character `…`, append `…`, and then derive the bold-title entity from the retained caption. The system SHALL NOT send a separate text message for caption overflow.

#### Scenario: Caption fits the photo-caption limit
- **WHEN** the complete rendered caption is at most 1024 characters after entity parsing
- **THEN** the system sends the complete caption with the photo

#### Scenario: Caption exceeds the photo-caption limit
- **WHEN** the complete rendered caption exceeds 1024 characters after entity parsing
- **THEN** the system sends one photo message with a grapheme-safe truncated caption whose final character is `…`, whose total length is at most 1024 characters after entity parsing, and whose bold-title entity is valid for the retained caption

#### Scenario: Caption contains complex Unicode
- **WHEN** a caption that requires truncation contains emoji, zero-width-joiner emoji sequences, combining marks, CJK text, or right-to-left text
- **THEN** the truncated caption does not split a grapheme cluster and retains valid explicit entity offsets

#### Scenario: Revised caption exceeds the photo-caption limit
- **WHEN** a revised title and story text exceed 1024 characters after entity parsing
- **THEN** the system edits the existing photo message with the revised image when applicable and a truncated caption ending in `…`, without creating a companion text message

### Requirement: Preserve retry eligibility after a known delivery failure
The system SHALL leave a story eligible for a later publication attempt when Telegram definitively rejects its channel delivery before accepting it.

#### Scenario: Telegram definitively rejects delivery
- **WHEN** Telegram rejects a new Weather Story publication before accepting it
- **THEN** the system does not record the story as successfully published and raises an operational alert
