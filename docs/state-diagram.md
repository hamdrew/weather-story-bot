# Weather Story Bot state diagrams

This living reference diagrams the approved persistent lifecycles. **Implemented**
means the durable state primitive exists in the repository; **Planned** means the
transition or operational component remains in the active OpenSpec task set. It is a
contract reference, not a source of secrets or production identifiers.

## Story and revision lifecycle

**Implemented:** canonical current-story persistence, conditional revision replacement,
and expiration marking. **Planned:** scheduler-driven selection and Telegram work.

```mermaid
stateDiagram-v2
  [*] --> Unseen
  Unseen --> Current: valid canonical identity / create STORY CURRENT
  Current --> Current: unchanged observation / update last_seen_at
  Current --> RevisionPendingImage: changed revision / replace current source state
  RevisionPendingImage --> Current: image committed
  RevisionPendingImage --> ImageInvalid: image validation fails
  ImageInvalid --> RevisionPendingImage: later changed or retried current revision
  Current --> Expired: now >= source endTime
  Expired --> Expired: retain record, image, and history
  Expired --> RevisionPendingImage: source identity reused with a newer revision
```

Expiration is a state change, not deletion or unpublication. An omitted story remains
current until its source `endTime`; failed retrieval also does not alter current state.
Superseded source content and images are not archived.

## Office operational-state lifecycle

**Implemented:** conditionally mutable current-office persistence. **Planned:** the
on-demand office-info manager (3.6).

```mermaid
stateDiagram-v2
  [*] --> Current: seed validated OFFICE CURRENT
  Current --> Current: conditionally refresh NWS metadata or active configuration
  Current --> Current: conditionally update managed pinned-message/invite references
```

`OFFICE#{office_id}/CURRENT` is the sole retained office-metadata record. It has no
TTL and no immutable audit or snapshot family. Conditional updates prevent stale
enrichment or management operations from replacing newer current operational state.

## Image lifecycle

**Implemented:** bounded validation, staging upload, verification, promotion, commit,
replacement cleanup, and staging reconciliation. **Planned:** production bucket
policy/lifecycle provisioning (5.2).

```mermaid
stateDiagram-v2
  [*] --> Pending: accepted current revision
  Pending --> Downloading: HTTPS allowlist and redirect policy
  Downloading --> Invalid: download/type/decode/limit failure
  Downloading --> Staged: validated bytes uploaded to staging/
  Staged --> Verified: checksum, content type, size, dimensions verified
  Verified --> Promoted: copied to deterministic current/ key
  Promoted --> Committed: conditional STORY image commit
  Promoted --> Orphaned: current-record commit fails
  Staged --> Orphaned: upload interruption or failed verification
  Orphaned --> Cleaned: reconciler or 7-day lifecycle expiry
  Committed --> Replaced: newer image committed
  Replaced --> Cleaned: prior current object deleted, noncurrent version retained 30 days
  Committed --> RetainedAfterExpiration: story expires
  RetainedAfterExpiration --> RetainedAfterExpiration: indefinite retention
```

Only `Committed` images may be published. No committed record points into `staging/`.

## Publication reservation lifecycle

**Implemented:** reservation, lease, attempt/transition persistence, and the legal
state-order guard. **Planned:** Telegram caller, stale-send detection, protected
reconciliation Lambda, and retry orchestration.

```mermaid
stateDiagram-v2
  [*] --> Reserved: conditional reservation wins
  Reserved --> SendStarted: owner starts one Telegram call before unexpired lease
  Reserved --> Reserved: expired unstarted lease reclaimed by a new attempt
  SendStarted --> Published: positive acknowledgement
  SendStarted --> Rejected: definitive pre-acceptance rejection
  SendStarted --> Ambiguous: timeout, interruption, lost/malformed response
  Ambiguous --> ConfirmedReceived: operator reconciliation
  Ambiguous --> ConfirmedNotReceived: operator reconciliation
  ConfirmedNotReceived --> Reserved: later poll creates a new attempt
  Rejected --> Reserved: later poll creates a new attempt
  Published --> [*]
  ConfirmedReceived --> [*]
```

Legal transitions are exactly `reserved → send_started → published|rejected|ambiguous`
and `ambiguous → confirmed_received|confirmed_not_received`. Only an expired
**unstarted** `reserved` lease may be reclaimed. An expired `send_started` attempt
stays protected: it must become ambiguous and be reconciled, never automatically sent
again. Each reservation permits at most one Telegram API call; any retry is a new
attempt. `429` and explicit `5xx` retries are planned to use new reservations when
their bounded delay/run budget permits; unknown acceptance is never auto-retried.

## Run result lifecycle

**Implemented:** immutable `RUN` record structure and allowed status enum. **Planned:**
scheduled handler classification and metrics/alerts.

```mermaid
stateDiagram-v2
  [*] --> Collecting
  Collecting --> Failed: collection or result persistence failure
  Collecting --> Processing: valid collection
  Processing --> Success: all selected work successful or skipped
  Processing --> SuccessWithDeferred: only unstarted story_cap/run_budget deferrals
  Processing --> SuccessWithQuarantined: malformed siblings, valid selected work completes
  Processing --> Failed: unresolved rejected, ambiguous, or image-invalid work
  Success --> Persisted
  SuccessWithDeferred --> Persisted
  SuccessWithQuarantined --> Persisted
  Failed --> Persisted
  Persisted --> [*]
```

A valid empty collection is `success`, with `discovered=0` and
`required_work_completed=true`. A persisted failed result should still permit the
handler to return normally when persistence succeeded; the durable status drives
monitoring.

## Alert-fingerprint lifecycle

**Implemented:** conditional fingerprint state updates and 30-day rolling TTL.
**Planned:** versioned fingerprint construction, dispatcher, four-hour cooldown
policy, aggregation, and fallback delivery.

```mermaid
stateDiagram-v2
  [*] --> NewFingerprint
  NewFingerprint --> Notify: first matching occurrence
  Notify --> CoolingDown: persist first/last seen, count, cooldown, outcome
  CoolingDown --> Suppressed: matching event before cooldown expiry
  Suppressed --> CoolingDown: increment count and refresh last seen
  CoolingDown --> OngoingNotify: matching event after cooldown expiry
  OngoingNotify --> CoolingDown: emit aggregated count, begin next cooldown
  CoolingDown --> Expired: no later updates, operational TTL elapses
  Expired --> [*]
```

Only `critical` and `error` conditions notify; planned `warning` controlled-deferral
events remain metric-only. The fingerprint consists of schema version, severity,
workflow, office ID, normalized error class, and story identity only for
story-specific failures. Run and correlation IDs are context, not fingerprint inputs.

For field contracts and retention, see [data-model.md](data-model.md).
