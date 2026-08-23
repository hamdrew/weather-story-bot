# History operations

This runbook covers authorized review of the Weather Story Bot's retained current
state and its short-lived operational audit history. It deliberately describes
key shapes and procedures, not secret values, Telegram identifiers, invite links,
image URLs, raw payloads, or raw responses.

## Read-only review

Use the `HistoryStore` read helpers from an authorized operator tool or Lambda
session. They use `GetItem` or key-family `Query` operations only; they never use
`Scan` and do not change retained records.

| Question | Helper | Facts available |
| --- | --- | --- |
| Current office configuration and managed references | `get_current_office(office_id)` | Current NWS-enriched fields, active flag, and managed-reference placeholders. |
| Current story and retained image | `get_current_story(office_id, source_story_id)` | First/last-seen facts, current revision/lifecycle/publication state, and current image metadata. |
| Stories for one office by source expiration | `list_current_stories(office_id)` | Current-story facts through `office-current-index`; no table scan. |
| One invocation result | `get_run_result(run_id)` | Collection outcome, elapsed milliseconds, status, required-work result, bounded reasons, and per-office/aggregate outcome counts, including deferrals. |
| Malformed items from an invocation | `list_quarantined_items(run_id)` | Bounded validation code, field, and sanitized summary. |
| Reservation, lease, and reconciliation history | `get_publication_attempt(attempt_id)` | Reservation owner/lease, target-reference placeholder, and ordered sanitized transition events, including reconciliation action and reason. |

`RUN`, `QUARANTINE`, `ATTEMPT`, transition, and `ALERT` records have a 30-day
`expires_at` boundary. DynamoDB TTL removal is asynchronous, so the helpers
intentionally treat records at or past that timestamp as unavailable. `OFFICE`
and `STORY` current records, their lightweight first-seen/outcome facts, and a
committed current image remain available indefinitely.

## Current-image lifecycle

Only a `committed` image with a deterministic `current/` key is publishable. A
story record never references `staging/`. When a later current image is committed,
the publisher removes the replaced current object; S3 versioning retains the
noncurrent version for 30 days. Story expiration does not delete the story record,
committed image, or publication history. Uncommitted staging objects are reconciled
and also expire through the seven-day staging lifecycle safety net.

## Attempt and reconciliation review

An expired `reserved` lease that has not started a send may be reclaimed by a new
attempt. A `send_started` lease is never automatically resent after expiry: review
the attempt's ordered transitions, then invoke the protected reconciliation Lambda
with an authorized operator identity and bounded reason. `confirmed_received`
records the delivery; `confirmed_not_received` makes a later poll eligible to make
a new reservation. Reconciliation is idempotent and appends no duplicate action.

Do not place a Telegram message reference, invite link, raw response, token, or
unbounded exception text into tickets, public chat, or command output. Use the
durable, sanitizer-produced metadata and safe attempt/run IDs for correlation.

## Authorized purge and recovery

Runtime functions never delete retained office/story records or current images for
expiration. A permanent purge is an exceptional, authorized, audited operator
procedure:

1. Confirm the exact office/story scope and obtain the required approval.
2. Create and verify an on-demand DynamoDB backup before a destructive migration
   or table replacement.
3. Disable the affected schedules and preserve the review evidence using safe IDs.
4. Perform the approved data operation with the deployment/operator authority;
   no runtime role may perform it.
5. Record the authorization, scope, backup identifier, validation, and re-enable
   decision without exposing sensitive identifiers.

The production recovery posture is same-Region. DynamoDB PITR has a 35-day window,
with monthly backups retained for one year. Restore only to a new isolated table;
then reapply IAM, tags, TTL, PITR, alarms, and runtime configuration. Validate
sampled current-story, attempt, transition, and run records against retained S3
image version checksums before a controlled cutover. Keep schedules disabled,
retain the source table for rollback, and re-enable only after validation. Record
this exercise quarterly; cross-Region replication is not part of the MVP.
