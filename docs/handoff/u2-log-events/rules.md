# Rules: u2-log-events

## Sources

- `requirements.md`: FR2.1 to FR2.4, FR5.2, FR6.3, NFR4, NFR5 [FR2.3]
- `decisions.md`: ADR-001 (event names at the call site), ADR-002 (alarms read event, level and logger only), ADR-003 (the Python drift test), ADR-005 (the formatter never raises) [FR5.2]
- `docs/logging-review.md`: rules BR1.1 to BR4.2 of the review (they are named "review BR" below so they are not confused with this unit's rules), decisions D1 to D6, and "What U2 must build" [FR6.3]
- A read of the current `handler.py`, `telegram.py`, `nws.py`, `history.py` and the tests that read log fields

This unit has no questions file: every choice below was settled upstream (ADR-001 to ADR-005, the owner's U1
answers Q1 A, Q2 B, Q3 A, and the review's decisions D1 to D9). The few design judgements left are listed in
the spec's "Assumptions & Open Questions".

```yaml
rules:
  - id: BR1.1
    statement: The formatter writes one JSON object per record with today's fields plus the call's extra fields.
    category: constraint
    applies_to: LogLine
    trigger: a record reaches a root handler
    logic: IF a record is formatted THEN the line holds time (UTC ISO 8601), level, logger and message, then every extra field of the call (event included, at the top level), then office and aws_request_id when the record carries them, then exception when the record has exc_info. A value that is not JSON-serializable is written with str(). The line holds no raw newline.
    violation: the formatter test fails; an alarm filter or Logs Insights query that reads event, level or logger finds nothing.
    source: FR2.3, FR5.2
  - id: BR1.2
    statement: An extra field can never replace time, level, logger, message or exception.
    category: constraint
    applies_to: LogLine
    trigger: a call passes an extra field with one of those names
    logic: IF an extra field is named time, level, logger, message or exception THEN the formatter's own value is the one written. (A record cannot carry an extra called message at all; logging raises KeyError. The other four are the formatter's guard.)
    violation: the formatter test fails; an alarm that filters on level would otherwise read a caller's value.
    source: FR2.3, FR5.2
  - id: BR1.3
    statement: The formatter never raises.
    category: constraint
    applies_to: LogFormatter
    trigger: building the full line fails for any reason (a circular structure, a message whose arguments do not format, a stack trace that cannot be formatted)
    logic: IF producing the full line raises any exception THEN the formatter returns the fallback line of BR1.4 instead. IF the fallback itself cannot be built THEN it returns a line holding only level and logger. No exception leaves format().
    violation: a record is lost and logging prints its own error to stderr, where no alarm reads it.
    source: FR2.4, FR6.3, ADR-005
  - id: BR1.4
    statement: A fallback line still carries what the alarms read, and says that it is a fallback.
    category: policy
    applies_to: LogLine
    trigger: BR1.3 applies
    logic: IF a fallback line is written THEN it holds time, level, logger, message (the raw message text when the formatted one is unavailable), formatter_error (the exception class name) and, when each is a plain string, event, office and aws_request_id. It holds no extra fields and no stack trace. This is wider than the review's "time, level, logger, message" wording on purpose; see assumption A2.
    violation: a failing extra field silently removes a record from the signal it counts, or hides that the formatter failed.
    source: FR2.4, FR6.3
  - id: BR1.5
    statement: A record from any logger is written the same way; one without an event is written without one.
    category: constraint
    applies_to: LogLine
    trigger: a record at WARNING or above from httpx, botocore, urllib3 or any other logger reaches a root handler
    logic: IF the record has no event THEN the line has no event key and still has level and logger. The formatter never invents or checks an event.
    violation: a third-party warning or error would be dropped or mislabeled, which breaks FR2.4's "any Python logger in the function".
    source: FR2.4, ADR-005
  - id: BR1.6
    statement: Logging setup puts the formatter on every root handler and keeps the token-safe caps.
    category: constraint
    applies_to: configure_logging
    trigger: each invocation starts (configure_logging runs first)
    logic: IF configure_logging runs THEN the root logger has a handler (one is added when none exists), every root handler uses the JSON formatter, the root level is INFO, and the httpx and httpcore loggers are at WARNING. Running it again changes nothing.
    violation: a handler Lambda installed keeps writing plain text; httpx logs Telegram URLs, which hold the bot token, at INFO.
    source: FR2.4, FR6.3
  - id: BR1.7
    statement: The office and the request id come from scoped context, not from callers.
    category: constraint
    applies_to: RequestContext
    trigger: an invocation starts, an office starts, either ends
    logic: IF a scope sets aws_request_id or office THEN every record created inside it carries it, and leaving the scope (normally or by exception) restores the previous value. The record factory is installed when the module is imported, chained to the factory already in place, so tests that call run() without configure_logging see it too.
    violation: a value leaks into a later invocation or office, or a line has no office.
    source: FR2.4
  - id: BR2.1
    statement: Every WARNING, ERROR and CRITICAL call of the bot passes its decided event as a literal.
    category: constraint
    applies_to: L01, L03 to L09, L11, L13, L16 to L20
    trigger: a logger call at WARNING, ERROR or CRITICAL is written or changed in src/weather_story_bot/
    logic: IF the call is at WARNING, ERROR or CRITICAL (logger.warning, .error, .exception, .critical) THEN its extra argument is a dict literal with the key "event" and a string constant as its value, and that value is the one docs/logging-review.md table 1 decides for the call. The names are office.lease_failed, nws.list_failed, office.process_failed, nws.image_download_failed, store.read_failed, office.lease_release_failed, nws.ambiguous_stories, story.process_failed, telegram.delete_failed, telegram.photo_rejected, telegram.rate_limited, nws.retry_transport_error, nws.retry_server_error, history.write_failed and run.slow.
    violation: the Python drift test (BR6.1) fails, naming the call; otherwise the call would be counted as a warning or error with no kind.
    source: FR2.1, FR2.2, FR2.3
  - id: BR2.2
    statement: The two signal events are the exact names the alarm filters will read.
    category: constraint
    applies_to: L08, L14
    trigger: either call is edited, or an alarm filter in U4 is written
    logic: IF the call is the message-sent INFO line (L14) THEN its event is telegram.message_sent; IF it is the ambiguous-stories ERROR (L08) THEN its event is nws.ambiguous_stories. Each is emitted on the real path (a send; an ambiguous listing), not only written in the source.
    violation: the quiet, repost-loop and nws-ambiguous alarms go blind when U4 moves them to the event.
    source: FR2.2, FR5.2
  - id: BR2.3
    statement: No INFO call other than the message-sent line gets an event.
    category: policy
    applies_to: L02, L10, L12, L15
    trigger: an INFO call is written or changed
    logic: IF the call is at INFO and is not L14 THEN it passes no event.
    violation: the review's rule BR1.4 and the drift test (BR6.1) flag it.
    source: FR2.3
  - id: BR2.4
    statement: Message text, levels and stack traces stay as they are.
    category: constraint
    applies_to: every existing LogCall
    trigger: an event or field is added to a call
    logic: IF a call gets an event or a field change THEN its message string, its level and whether it keeps its stack trace do not change. The only new message is Run was slow (L20). The three message-based alarm filters therefore keep matching until U4.
    violation: today's alarms stop matching before U4 moves them.
    source: FR2.3, FR5.2, FR6.3
  - id: BR3.1
    statement: One meaning per field name for the status and the message id.
    category: constraint
    applies_to: L18, L15
    trigger: the field names of those two calls
    logic: IF L18 (NWS server error, retrying) logs an HTTP code THEN the field is http_status, not status. IF L15 (Telegram message deleted) logs the Telegram message id THEN the field is telegram_message_id, not message_id.
    violation: a query on status mixes an HTTP code with the story's new or updated; a query on a message id misses L15.
    source: FR6.3
  - id: BR3.2
    statement: A caught exception is under error, as its repr.
    category: constraint
    applies_to: L07, L11, L13, L17, L19
    trigger: a call logs the exception that caused it
    logic: IF a WARNING call logs an exception THEN the field is error and its value is repr(exc). L13's reason field is replaced by error; L07, L11 and L19 change from str(exc) to repr(exc); L17 already conforms.
    violation: an empty str() of an httpx exception hides the cause; one name per meaning is lost.
    source: FR6.3
  - id: BR3.3
    statement: No call's extra field repeats a name the line already owns.
    category: validation
    applies_to: every LogCall
    trigger: a call passes an extra dict literal
    logic: IF a call's extra dict literal has a key that is a LogRecord attribute, or is time, level, logger, message, exception, office or aws_request_id, THEN the drift test fails. A key that is not lowercase snake_case also fails. Keys added by a ** spread or built outside the literal are not read.
    violation: logging raises KeyError at run time, or the formatter's own value is shadowed.
    source: FR6.3, FR5.2
  - id: BR4.1
    statement: A run that takes more than 150 seconds logs one warning.
    category: calculation
    applies_to: lambda_handler
    trigger: run() returns inside an invocation
    logic: IF the monotonic time from the first statement of lambda_handler to the return of run() is more than 150 seconds THEN log "Run was slow" at WARNING with event run.slow, duration_seconds (rounded to one decimal) and threshold_seconds 150. IF it is 150 seconds or less THEN log nothing.
    violation: a run that finishes but crawls goes unnoticed until it times out.
    source: FR2.1, FR6.3
  - id: BR4.2
    statement: The slow-run line comes before "Run complete" and keeps no state.
    category: constraint
    applies_to: lambda_handler
    trigger: the slow-run check fires
    logic: IF the check fires THEN its line is written before "Run complete", and a failed count still raises ProcessingError afterwards exactly as today. IF run() raises THEN no slow-run line is written (the errors alarm covers that run). Nothing is stored between invocations.
    violation: the order of the lines misleads a reader, or the failure behaviour changes (NFR5).
    source: FR2.1, FR6.3
  - id: BR5.1
    statement: A test proves the Telegram token never reaches a log line.
    category: validation
    applies_to: TelegramClient error paths and the handler's delete path
    trigger: the unit's tests run
    logic: IF each handled Telegram failure is driven with a recognizable token (transport error, 429 then success, photo rejected, unexpected result, delete failed, and an HTTP error status on every method), THEN no captured record, passed through the shipped formatter so fields and exception text are included, contains the token. The test calls configure_logging() first, so httpx and httpcore records are captured under the cap production uses.
    violation: a leak is found only in CloudWatch.
    source: FR6.3, review BR3.3
  - id: BR5.2
    statement: The leak test proves that it looked in the right place.
    category: validation
    applies_to: the BR5.1 test
    trigger: the BR5.1 test runs
    logic: IF the leak test passes THEN a control assertion has shown that the mocked route matched the token-bearing URL, so "no token in the log" cannot pass because the request never happened.
    violation: the test passes without testing anything.
    source: FR6.3
  - id: BR5.3
    statement: The httpx and httpcore caps are read back.
    category: validation
    applies_to: configure_logging
    trigger: the unit's tests run
    logic: IF configure_logging() has run THEN a test reads the httpx and httpcore logger levels and finds WARNING.
    violation: someone removes the cap and httpx writes Telegram URLs at INFO.
    source: FR6.3, review BR3.1
  - id: BR6.1
    statement: A test fails when a WARNING or ERROR call in src/ has no event.
    category: validation
    applies_to: SignalContractCheck (Python half)
    trigger: the unit's tests run
    logic: IF any logger.warning, .error, .exception or .critical call in src/weather_story_bot/ lacks an extra dict literal with a string-constant "event" key THEN the test fails and names the module, line and message. The message-sent call (L14) must have one too. An extra built outside a dict literal fails with a message saying to write the literal.
    violation: a new warning or error is counted with no kind (FR2.1, FR2.2) and the dashboard and alarms cannot name it.
    source: FR5.2, FR2.1, FR2.2
  - id: BR6.2
    statement: The two signal events are proven on their real paths.
    category: validation
    applies_to: SignalContractCheck (Python half)
    trigger: the unit's tests run
    logic: IF a story is sent through TelegramClient THEN a captured record has message Telegram message sent and event telegram.message_sent; IF the handler runs on an ambiguous listing THEN a captured ERROR record has event nws.ambiguous_stories. The names are written out in the tests, not imported from src.
    violation: renaming either name in src compiles and passes, then blinds an alarm after U4.
    source: FR5.2
  - id: BR6.3
    statement: The events in the code and in the logging review are the same set.
    category: validation
    applies_to: SignalContractCheck (Python half)
    trigger: the unit's tests run
    logic: IF the set of event strings in the log calls of src/ differs from the set in docs/logging-review.md table 1 THEN the test fails and names the difference. The review's "(new)" mark on L20 is removed when the call exists, which the existing review test already requires.
    violation: the review that U4 and U5 rely on names an event the code does not emit, or the reverse.
    source: FR5.2, FR2.3
  - id: BR6.4
    statement: The formatter test shows the event at the top level and its absence for third-party records.
    category: validation
    applies_to: SignalContractCheck (Python half), LogFormatter
    trigger: the unit's tests run
    logic: IF a record with extra event is formatted THEN the parsed line has event at its top level; IF a record from a logger named like a third-party one at WARNING has no event THEN the parsed line has level and logger and no event key; IF a field cannot be serialised (a circular structure) THEN the line is the fallback of BR1.4 and parses as JSON.
    violation: the line contract that ADR-002 and U4 depend on changes unnoticed.
    source: FR5.2, FR2.4
```

| Rule | Group | Plain statement |
|------|-------|-----------------|
| BR1.1 | Line shape | One JSON line: today's fields, the call's extras, the exception |
| BR1.2 | Line shape | An extra can't replace time, level, logger, message or exception |
| BR1.3 | Line shape | The formatter never raises |
| BR1.4 | Line shape | A fallback line keeps event, office and request id and says it is a fallback |
| BR1.5 | Line shape | A record from any logger is written; no event is invented |
| BR1.6 | Line shape | Setup formats every root handler and keeps the httpx caps |
| BR1.7 | Line shape | Office and request id come from scoped context |
| BR2.1 | Events | Every WARNING, ERROR and CRITICAL call passes its decided event |
| BR2.2 | Events | The two signal names are exact and emitted on the real path |
| BR2.3 | Events | No other INFO line gets an event |
| BR2.4 | Events | Message text, levels and stack traces don't change |
| BR3.1 | Fields | http_status and telegram_message_id |
| BR3.2 | Fields | A caught exception is error, as repr |
| BR3.3 | Fields | No extra repeats a name the line owns |
| BR4.1 | Slow run | More than 150 s logs run.slow |
| BR4.2 | Slow run | It comes before Run complete and keeps no state |
| BR5.1 | Token | A test proves the token stays out of the log |
| BR5.2 | Token | The test proves it looked in the right place |
| BR5.3 | Token | The httpx and httpcore caps are read back |
| BR6.1 | Drift test | A WARNING or ERROR call without an event fails the test |
| BR6.2 | Drift test | The two signal events are proven on their real paths |
| BR6.3 | Drift test | Code and review list the same events |
| BR6.4 | Drift test | The line contract is pinned, fallback included |
