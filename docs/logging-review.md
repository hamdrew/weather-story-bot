# Logging review

A review of every log call in `src/weather_story_bot/`, with a finding and a decision for each problem found,
and a check that no line carries a secret. The decisions are carried out in the `u2-log-events` unit of the
observability work; `u4-sturdy-alarms` and `u5-warnings-and-errors` filter on the event names decided here.

`tests/test_logging_review.py` fails when a log call in `src/` is missing from table 1 below, when an event name is
malformed or repeated, or when a level written here differs from the code. Keep the table in step with the code.

## Method

1. List every `logger.*` call in `src/weather_story_bot/` with its module, level, message, fields and whether it keeps a stack trace.
2. Give each WARNING and ERROR call, and the message-sent line, a stable event name (BR1.1 to BR1.4).
3. Compare the calls with the field and level rules (BR2.1 to BR2.4) and record each mismatch as a finding with a decision.
4. Check the calls against the secrets rules (BR3.1 to BR3.3).
5. Decide whether any pattern nothing logs today should become a warning (BR4.1, BR4.2).

`__main__.py` prints to the terminal and logs nothing. `planner.py`, `state.py`, `archive.py`, `config.py` and
`models.py` log nothing.

## Rules

| Rule | Statement |
|------|-----------|
| BR1.1 | Every WARNING and ERROR call passes an event name. |
| BR1.2 | An event name is lowercase, in the form `area.what` (area: nws, telegram, office, story, store, history or run), with one name per call. |
| BR1.3 | The two signal events are fixed: the message-sent line is `telegram.message_sent` and the ambiguous-stories error is `nws.ambiguous_stories`. Renaming either needs the same change in the alarm filters and both drift tests. |
| BR1.4 | No INFO call other than the message-sent line gets an event. |
| BR1.5 | Message text does not change while the events are added, so the message-based alarm filters keep matching until they move to the event. |
| BR2.1 | Extra field names are lowercase snake_case, none is a reserved `LogRecord` attribute, and none repeats `office` or `aws_request_id`. |
| BR2.2 | One meaning per field name: an HTTP status is `http_status` (`status` stays the story's `new` or `updated`); an exception is `error`, set to `repr(exc)`; a Telegram message id is `telegram_message_id`. |
| BR2.3 | A caught failure is logged at ERROR with its stack trace; a recoverable condition is logged at WARNING with no stack trace, and with an `error` field when an exception caused it. |
| BR2.4 | Today's seven warnings and seven errors keep their levels. |
| BR3.1 | No log line carries a secret: never a Telegram URL, request object or environment mapping; exception text is built from the exception type or Telegram's description only; `httpx` and `httpcore` stay capped at WARNING. |
| BR3.2 | No log line carries a full request or response body, a caption or image bytes; fields hold identifiers and short metadata. |
| BR3.3 | A test proves the token never reaches a log line (see "What U2 must build"). |
| BR4.1 | A run that takes longer than 150 seconds logs `run.slow` at WARNING. |
| BR4.2 | An NWS listing with no active stories gets no new warning. |

## Table 1. Inventory, with decided event names

| ID | Module | Level | Message | Fields today | Stack | Event decided |
|----|--------|-------|---------|--------------|-------|---------------|
| L01 | handler | ERROR | Failed to take office lease | none | yes | `office.lease_failed` |
| L02 | handler | INFO | Office run already in progress | none | no | none (BR1.4) |
| L03 | handler | ERROR | Failed to list stories | none | yes | `nws.list_failed` |
| L04 | handler | ERROR | Failed to process office | none | yes | `office.process_failed` |
| L05 | handler | ERROR | Failed to download story image | title | yes | `nws.image_download_failed` |
| L06 | handler | ERROR | Failed to read posted stories | none | yes | `store.read_failed` |
| L07 | handler | WARNING | Office lease release failed | error | no | `office.lease_release_failed` |
| L08 | handler | ERROR | Ambiguous stories from NWS | stories | no | `nws.ambiguous_stories` (signal) |
| L09 | handler | ERROR | Failed to process story | title | yes | `story.process_failed` |
| L10 | handler | INFO | Story posted | image_id, status, telegram_message_id, archive_prefix, fingerprint, and on an update changes, previous_image_id, previous_fingerprint, previous_archive_prefix | no | none (BR1.4) |
| L11 | handler | WARNING | Telegram delete failed, old message kept | image_id, telegram_message_id, error | no | `telegram.delete_failed` |
| L12 | handler | INFO | Run complete | summary | no | none (BR1.4) |
| L13 | telegram | WARNING | Photo rejected, sending as document | reason | no | `telegram.photo_rejected` |
| L14 | telegram | INFO | Telegram message sent | chat_id, image_filename | no | `telegram.message_sent` (signal) |
| L15 | telegram | INFO | Telegram message deleted | chat_id, message_id | no | none (BR1.4) |
| L16 | telegram | WARNING | Telegram rate limited, retrying | method, retry_after | no | `telegram.rate_limited` |
| L17 | nws | WARNING | NWS request failed, retrying | url, error | no | `nws.retry_transport_error` |
| L18 | nws | WARNING | NWS server error, retrying | url, status | no | `nws.retry_server_error` |
| L19 | history | WARNING | History write failed | history_write, error; three call sites share the one line: `history_write="event"` (plus image_id), `"last_seen"` (plus image_id) and `"run"`. `history_write` tells them apart and is not the `event` field | no | `history.write_failed` (one event for all three) |
| L20 | handler | WARNING | Run was slow (new) | duration_seconds, threshold_seconds | no | `run.slow` |

Counts: 8 WARNING (7 today plus L20), 7 ERROR, 5 INFO. The handler's logger is the fixed name
`weather_story_bot`; the other modules use `weather_story_bot.<module>`.

## Table 2. Findings

| ID | Calls | Category | Finding |
|----|-------|----------|---------|
| F1 | L18, L10 | field | `status` means an HTTP code in L18 and the story's `new` or `updated` in L10. A Logs Insights filter on `status` would mix them. |
| F2 | L07, L11, L13, L17, L19 | field | The exception is under `error` as `str(exc)` in L07, L11 and L19, as `repr(exc)` in L17 and under `reason` in L13. `str()` of many httpx exceptions is empty, so L17's choice is the useful one. |
| F3 | L15, L10, L11 | field | The Telegram message id is `message_id` in L15 and `telegram_message_id` in L10 and L11. |
| F4 | L01 to L19 | coverage | 14 WARNING and ERROR calls and the message-sent line carry no stable kind; three alarms read message text. |
| F5 | L15 | message | "Telegram message deleted" is logged also when Telegram said the message was already gone, which `delete_message` deliberately counts as deleted. The text is accurate enough for its purpose; no change. |
| F6 | all | secret | No call logs the token, a Telegram URL, a caption, an image or a request body. The mechanisms that keep it so are listed below; only the delete-failed path (L11) has a test that proves it today. |
| F7 | handler | consistency | The handler's logger is the fixed name `weather_story_bot`, the others use `__name__`. It matters only for records without an event (third-party loggers), which are kinded by logger name, so no change. |
| F8 | all | coverage | Nothing logs a run that finishes but takes a long time. |
| F9 | L03 | coverage | An empty NWS listing logs nothing. The owner decided that is right. |

## Table 3. Decisions

| ID | Finding | Outcome | Carried out in | Decision |
|----|---------|---------|----------------|----------|
| D1 | F1 | change | u2-log-events | Rename L18's `status` to `http_status` (BR2.2). |
| D2 | F2 | change | u2-log-events | Use `error` = `repr(exc)` in L07, L11, L13 and L19; L13's `reason` becomes `error`; L17 already conforms (BR2.2). The `repr` value includes the exception's class name, so L13's field reads `_PhotoRejectedError('...')`, a private class name; this is accepted, since it is only a label beside Telegram's description. U2 re-checks the tests that read `error`, `reason`, `status` and `message_id` before renaming. |
| D3 | F3 | change | u2-log-events | Rename L15's `message_id` to `telegram_message_id` (BR2.2). |
| D4 | F4 | change | u2-log-events | Add the events of table 1 to every WARNING and ERROR call and to L14 (BR1.1, BR1.3). |
| D5 | F8 | new-call | u2-log-events | Add L20, `run.slow` past 150 s (BR4.1; see "The run.slow check"). |
| D6 | F6 | change | u2-log-events | Add the test that the Telegram error paths never log the token (BR3.3). |
| D7 | F5 | keep | none | Leave L15's text as it is. |
| D8 | F7 | keep | none | Leave the logger names as they are; kinds come from events (BR1.1). |
| D9 | F9 | keep | none | No warning for an empty listing (BR4.2). |

## The secrets check

| Question | Answer from the code | Rule |
|----------|----------------------|------|
| Is the Telegram token in any message or field? | No. `_call` builds the URL with it but never logs the URL; a transport error is re-raised as `TelegramError` with the exception type only and `from None`, so no chained text prints it. | BR3.1 |
| Do `httpx` and `httpcore` log requests? | They log URLs at INFO, which would include the token. `configure_logging` caps both at WARNING. | BR3.1 |
| Does an exception text hold the token? | `TelegramError` messages hold the method, the HTTP code and Telegram's description. NWS and AWS error text holds no secret (the NWS URLs are public). Telegram's description is accepted as non-secret: it is Telegram's own error wording and never echoes the request URL. | BR3.1 |
| Is a body, caption or image logged? | No. L08 logs ids, titles and reasons; L10 logs ids and hashes; nothing passes the image or the caption. | BR3.2 |
| Is there a test? | One path: `tests/test_handler.py` asserts the token is not in the log for the delete-failed warning (L11). The transport-error, 429, photo-rejected and unexpected-result paths have none. D6 extends that coverage to them. | BR3.3 |

## The run.slow check (L20)

1. `lambda_handler` notes a monotonic start time as its first statement, before the services are built, because a cold start spends part of the 300 s. The Lambda init phase (module import) happens before the handler and is not counted.
2. After `run()` returns, it computes the elapsed seconds.
3. If it is more than 150, it logs "Run was slow" at WARNING with `event` `run.slow`, `duration_seconds` (one decimal) and `threshold_seconds` 150.
4. It then logs "Run complete" and raises `ProcessingError` for failed counts exactly as today.

The check has no stored state. If `run()` raises, no `run.slow` line is written; the `errors` alarm covers that run. A run
that hits the 300 s timeout never logs it either, and stays with the `errors` alarm. The owner asked about CloudWatch
anomaly detection on the Lambda `Duration` metric instead; it is possible, but run time depends mostly on how many
stories a run posts, so the learned band would be wide, and it would be a metric alarm that needs its own place on the
dashboard, in `alarm_names` and in the verdict. It is left as a possible later change.

## Edge cases

- A call that passes a reserved `LogRecord` name raises `KeyError`; BR2.1 forbids it, and none is left (`image_filename` was renamed earlier for this).
- A non-JSON-serializable field value is written by `str()` through the formatter's `default=str`; a long value such as L08's `stories` list stays one line.
- A record from a third-party logger (`httpx`, `botocore`, `urllib3`) at WARNING or above has no event; the formatter keeps the logger name. Not a finding.
- Two events in one invocation (for example `nws.retry_transport_error` then `nws.list_failed`) are separate lines; the warning alarm counts the first, the error-log alarm the second.
- `run.slow` and a failed run in the same invocation both log; the failed run raises after `run.slow` and "Run complete".
- A clock step cannot affect `run.slow`: it uses `time.monotonic`.

## What U2 must build

- The event names of table 1 and the field changes D1 to D3, with message text unchanged (BR1.5).
- The `run.slow` check and a test that patches `time.monotonic`: the line appears past 150 s, does not appear at or below 150 s, and comes before "Run complete" when a failed count follows.
- The token leak test (NFR4.1): it calls `configure_logging()` first, so `httpx` and `httpcore` records are captured under the cap production uses; it drives each handled Telegram failure (transport error, 429 then success, photo rejected, unexpected result, delete failed, and an HTTP error status on every method) with a recognizable token; it passes every captured record through the shipped formatter, so fields and exception text are included; and a control assertion checks that the respx route matched the token-bearing URL. A separate test reads the `httpx` and `httpcore` levels back.
- A `try/except` fallback in the formatter that emits a minimal record (time, level, logger, message) if serialising an extra field or the exception ever fails, with a test that passes a circular structure.
- The Python drift test: every WARNING and ERROR call in `src/` passes an event, and the message-sent and ambiguous-stories paths emit their exact names.

## What U4 and U5 take from this

- U4 filters on the two signal names: `telegram.message_sent` (for the `quiet` and `repost-loop` alarms) and `nws.ambiguous_stories`.
- U5 counts by `level` and shows kinds from `event`; `run.slow` joins the warning kinds without a change to the dashboard.

## Assumptions

- The Lambda timeout stays 300 s (`infra/lambda.tf`); if it changes, the 150 s threshold in BR4.1 is revisited.
- Normal runs finish well under 150 s, so `run.slow` rarely fires; the first week on staging shows whether the threshold is right.
