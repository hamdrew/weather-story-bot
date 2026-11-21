# Contract: the log line and its events

This is the interface U2 publishes. U4 (alarms) and U5 (the warnings-and-errors digest) build on it, and so do any
CloudWatch Logs Insights queries. Consumers may rely on every key marked "yes" in the Stable column. Anything else may
change without notice.

## Line

The function uses Lambda's JSON log format. The runtime writes each record as one JSON object in the log group,
`/aws/lambda/<function name>`.

| Key | Stable | Meaning |
|-----|--------|---------|
| `level` | yes | Python's level name: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`; the `WARNING` spelling (not `WARN`) is unverified until a real warning line is seen |
| `logger` | yes | logger name; the bot's own lines start with `weather_story_bot` |
| `event` | yes | the kind of line (catalogue below); present only where the catalogue says |
| `timestamp` | yes | when the record was made, written by the runtime; whole seconds only, so it cannot order lines within one second: sort on CloudWatch's `@timestamp` (millisecond precision) for that |
| `requestId` | yes | the invocation's request id, written by the runtime |
| `office` | yes | present on lines written while an office is being processed; absent otherwise |
| `message` | until U4 | human text; today's two message-based metric filters (`Telegram message sent`, `Ambiguous stories from NWS`), which feed three alarms, still match it, and U4 moves them to `event` |
| stack-trace keys | no | written by the runtime for errors logged with a stack trace; their names and content are not a contract. The runtime writes the raised exception's own frames and text only, not the chained cause (`raise ... from exc`), so the inner frames the old formatter printed are gone |
| any other key | no | per-call detail (for example `title`, `error`, `http_status`); for people, not filters |

Key order is not part of the contract.

**The runtime's own lines.** `START`, `END` and `REPORT` for each invocation, and the runtime's report of an unhandled
error, are JSON as well. They have no `event`. A failed run is counted through the Lambda `Errors` metric, and a slow
run through the `Duration` metric (U4), not through log lines.

**Filter guidance for U4/U5**:

- Match on `$.event` together with `$.level`.
- A line from a library (`httpx`, `botocore`, `urllib3`) at WARNING or above has no `event`. Count it by `$.logger`.
- Count nothing else. A line with no `event` whose `logger` is not a library's is the runtime's own; this includes its
  report of an unhandled error, which may carry `level` ERROR. Failed runs are counted from `Errors`, never from it.
- Before a filter relies on `$.level = "WARNING"`, confirm the spelling on a real warning line.

## Event catalogue

| Event | Level | Line (message, unchanged) | Signal | One line per |
|-------|-------|---------------------------|--------|--------------|
| `office.lease_failed` | ERROR | Failed to take office lease | | office per run whose lease could not be taken |
| `nws.list_failed` | ERROR | Failed to list stories | | office per run whose listing failed |
| `office.process_failed` | ERROR | Failed to process office | | office per run that failed outside a narrower catch |
| `nws.image_download_failed` | ERROR | Failed to download story image | | story whose image failed to download |
| `store.read_failed` | ERROR | Failed to read posted stories | | office per run whose posted-story read failed |
| `office.lease_release_failed` | WARNING | Office lease release failed | | office per run whose lease release failed |
| `nws.ambiguous_stories` | ERROR | Ambiguous stories from NWS | **yes** (nws-ambiguous alarm) | office per run with any rejected stories (the `stories` field lists them) |
| `story.process_failed` | ERROR | Failed to process story | | story whose post or update failed |
| `telegram.delete_failed` | WARNING | Telegram delete failed, old message kept | | superseded message Telegram refused to delete |
| `telegram.photo_rejected` | WARNING | Photo rejected, sending as document | | photo Telegram rejected (then sent as a document) |
| `telegram.message_sent` | INFO | Telegram message sent | **yes** (quiet and repost-loop alarms) | message Telegram accepted |
| `telegram.rate_limited` | WARNING | Telegram rate limited, retrying | | Telegram call retried after a 429 (at most one per call) |
| `nws.retry_transport_error` | WARNING | NWS request failed, retrying | | NWS request attempt retried after a transport error |
| `nws.retry_server_error` | WARNING | NWS server error, retrying | | NWS request attempt retried after a 5xx |
| `history.write_failed` | WARNING | History write failed | | failed history write (`history_write` names which) |

`history.write_failed` covers three write paths. Its `history_write` field (`event`, `last_seen`, `run`) tells them
apart, and is not the `event` key.

The source of truth is `docs/logging-review.md` table 1. A test fails when the code and that table disagree. To add or
rename an event, change the call, table 1 and this catalogue in one pull request. Renaming a **signal** event also
changes the metric filter that reads it in that pull request.

## Guarantees

- Every WARNING, ERROR and CRITICAL line from the bot's own loggers has an `event` from this catalogue.
- No INFO line other than `telegram.message_sent` has an `event`.
- No log record holds the Telegram bot token, `api.telegram.org`, a story caption or image bytes, so no line can.
