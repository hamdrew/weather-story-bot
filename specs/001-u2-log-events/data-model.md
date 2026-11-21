# Data Model: U2 Log Events (revised)

None of these entities is stored by the bot. A log line exists only in the Lambda's CloudWatch log group; the others are
shapes in the code and conventions the tests enforce. The line's wire format is in
[contracts/log-line.md](contracts/log-line.md).

## LogLine

One JSON object per record, written by the Lambda runtime (research R1).

| Field | Source | Rule |
|-------|--------|------|
| `timestamp` | runtime | when the record was made |
| `level` | runtime | Python's level name: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` (the `WARNING` spelling is unverified; spec Assumptions) |
| `logger` | runtime | `weather_story_bot`, `weather_story_bot.<module>`, or a library's name |
| `message` | runtime | the formatted message; unchanged by U2 |
| `requestId` | runtime | the invocation's request id |
| `event` | the call's `extra` | see EventName; only where the catalogue says |
| `office` | OfficeContext | present while an office is being processed |
| *other extras* | the call's `extra` | per-call detail, lowercase snake_case |
| stack-trace keys | runtime | written by the runtime for `logger.exception`; not a contract |

## EventName

| Attribute | Rule |
|-----------|------|
| value | matches `^(nws\|telegram\|office\|story\|store\|history\|run)\.[a-z_]+$` |
| scope | one per log line (message); the one L19 call is reached from three history-write paths, so all three emit `history.write_failed` |
| level | WARNING or ERROR (CRITICAL allowed, none exists), except `telegram.message_sent` (INFO) |
| signal | true only for `telegram.message_sent` and `nws.ambiguous_stories` |

**Validation** (tests only, research R6): written as a `str` constant for the `"event"` key of a dict literal passed as
`extra=`; the set in `src/` equals the set in `docs/logging-review.md` table 1.

## LogCall

One logger call in `src/weather_story_bot/`, L01 to L19 in table 1.

| Attribute | Rule |
|-----------|------|
| form | `logger.<level>("<constant message>", ...)`; any other form fails the drift check |
| level | as in table 1; never changed by U2 |
| message | constant string; never changed by U2 |
| extra | a dict literal with constant string keys and no `**` spread, required at WARNING and above and on L14; an INFO call without an event may pass a built dict (L10) |
| extra keys | lowercase snake_case; not a `LogRecord` attribute; not `message`, `asctime`, `timestamp`, `level`, `logger`, `requestId`, `office` |
| event | required at WARNING, ERROR and CRITICAL, and on L14; forbidden on every other call |

**Field changes U2 makes**: L18 `status` → `http_status`; L15 `message_id` → `telegram_message_id`; L13 `reason` →
`error`; L07, L11, L19 `error` from `str(exc)` to `repr(exc)`; L19 lists `image_id` in its literal instead of spreading it
(absent from the line on the `run` write: the runtime drops null fields).

## OfficeContext

| Attribute | Rule |
|-----------|------|
| set by | `_office_context(office_id)`, entered by `run()` for each office |
| cleared | on leaving the scope, also on an exception |
| applied | by a record factory, so child loggers' records get it too |

```text
Outside ──run() enters office──▶ Office ──office scope ends──▶ Outside
```

The request id is no longer a logging context (research R3). `lambda_handler` passes it to `run()`, which passes it to
the `RUN#` history record.
