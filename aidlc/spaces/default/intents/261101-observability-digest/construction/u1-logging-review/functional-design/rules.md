# Rules: u1-logging-review

## Sources

- `requirements.md`: FR2.1 to FR2.3, FR5.1, FR5.2, FR6.1 to FR6.3, NFR5 [FR6.1]
- `decisions.md`: ADR-001 (event names at the call site), ADR-002 (fields read), ADR-005 (formatter never raises)
- `functional-design-questions.md`: Q1 A, Q2 B, Q3 A (the owner's answers)
- Project rule: the Telegram token is never in Terraform variables or state, and `httpx` logs full request URLs at INFO

```yaml
rules:
  - id: BR1.1
    statement: Every WARNING and ERROR call passes an event name.
    category: constraint
    applies_to: every LogCall at WARNING, ERROR or CRITICAL in src/weather_story_bot/
    trigger: a logger call at WARNING or above is written or changed
    logic: IF the call is at WARNING, ERROR or CRITICAL THEN it passes extra={"event": "<name>"}.
    violation: the U2 Python test fails, naming the call.
    source: FR2.3, FR6.1
  - id: BR1.2
    statement: An event name is lowercase, in the form area.what, with one name per call.
    category: validation
    applies_to: EventName
    trigger: a name is chosen
    logic: IF a name is chosen THEN it matches ^[a-z]+(\.[a-z_]+)+$, its area is one of nws, telegram, office, story, store, history or run, and no other call uses it.
    violation: the review rejects the name; the U2 test fails on a duplicate.
    source: FR2.3
  - id: BR1.3
    statement: The two signal events are fixed names, and the message-sent line carries one although it is INFO.
    category: constraint
    applies_to: L08, L14
    trigger: a signal call is edited, or an alarm filter is written
    logic: IF the call is L14 THEN its event is telegram.message_sent; IF it is L08 THEN its event is nws.ambiguous_stories. Renaming either needs the same change in U4's filters and both drift tests.
    violation: the U2 and U4 drift tests fail.
    source: FR5.1, FR5.2
  - id: BR1.4
    statement: No INFO call other than the message-sent line gets an event.
    category: policy
    applies_to: L02, L10, L12, L15
    trigger: an INFO call is written or changed
    logic: IF an INFO call is not a signal THEN it passes no event; Logs Insights finds it by message.
    violation: the review flags the extra event as unneeded.
    source: ADR-001
  - id: BR1.5
    statement: Message text does not change in U2.
    category: constraint
    applies_to: every LogCall
    trigger: U2 edits a call
    logic: IF U2 adds an event or renames a field THEN the message string stays as it is today, so the three message-based filters keep matching until U4 moves them.
    violation: an alarm silently stops matching between U2 and U4.
    source: FR5.1, NFR5
  - id: BR2.1
    statement: Extra field names are lowercase snake_case, none is a reserved LogRecord attribute, and none repeats office or aws_request_id.
    category: validation
    applies_to: every LogCall's fields
    trigger: a field is added or renamed
    logic: IF a field is named like a LogRecord attribute (filename, message, name, ...) or office or aws_request_id THEN it is renamed, because logging raises KeyError on a clash.
    violation: the call raises at run time; the review caught image_filename already.
    source: FR6.1
  - id: BR2.2
    statement: One meaning per field name.
    category: policy
    applies_to: status, http_status, error, telegram_message_id
    trigger: a field is added or renamed
    logic: IF the field carries an HTTP status THEN it is http_status (status stays the story's new or updated); IF it carries an exception THEN it is error, set to repr(exc); IF it carries a Telegram message id THEN it is telegram_message_id.
    violation: the review reports the inconsistency.
    source: FR6.1, FR6.3
  - id: BR2.3
    statement: A caught failure is logged at ERROR with its stack trace; a recoverable condition is logged at WARNING with no stack trace, and with an error field when an exception caused it.
    category: policy
    applies_to: every LogCall at WARNING or ERROR
    trigger: a call is written or changed
    logic: IF the call is inside an except block that counts the unit of work as failed THEN it uses logger.exception; IF the call logs a retry, a fallback or a best-effort write that did not matter THEN it uses logger.warning, with error=repr(exc) when an exception caused it.
    violation: the review reports the call.
    source: FR2.1, FR2.2, FR6.1
  - id: BR2.4
    statement: Today's levels hold.
    category: constraint
    applies_to: the seven warnings and seven errors
    trigger: the review looks at levels
    logic: IF a call is one of today's seven WARNINGs or seven ERRORs THEN it keeps its level.
    violation: the dashboard's kinds change without a requirement.
    source: FR2.1, FR2.2
  - id: BR3.1
    statement: No log line carries a secret.
    category: policy
    applies_to: every LogCall, and the exception text it prints
    trigger: a call is written or changed, or a library logger is turned on
    logic: IF a value could hold the Telegram token (a Telegram URL, a request object, os.environ) THEN it is never passed as a message argument or field, and exception text is built from the exception type or Telegram's description only; httpx and httpcore stay capped at WARNING.
    violation: the token appears in CloudWatch Logs, which keeps it 30 days.
    source: FR6.2
  - id: BR3.2
    statement: No log line carries a full request or response body, a caption or image bytes.
    category: policy
    applies_to: every LogCall
    trigger: a call is written or changed
    logic: IF a field would hold a body, caption or image THEN it holds identifiers and short metadata instead (image_id, title, reasons, status codes, counts).
    violation: log volume and Logs Insights cost grow, and story content leaves the bot.
    source: FR6.2
  - id: BR3.3
    statement: A test proves the token never reaches a log line.
    category: validation
    applies_to: telegram.py error paths
    trigger: U2 adds its tests
    logic: IF the Telegram client fails in any of its handled ways with a recognizable token THEN no captured log record's message, extra fields or exception text contains that token.
    violation: the U2 test fails.
    source: FR6.2
  - id: BR4.1
    statement: A run that takes longer than 150 seconds logs run.slow at WARNING.
    category: policy
    applies_to: lambda_handler
    trigger: run() returns
    logic: IF the time from the start of the invocation to the return of run() is more than 150 seconds THEN log "Run was slow" at WARNING with event run.slow and fields duration_seconds and threshold_seconds. A run that hits the 300-second timeout never logs it, and stays with the errors alarm.
    violation: a slow run goes unnoticed until it times out.
    source: FR6.1, Q2 B, Q3 A
  - id: BR4.2
    statement: An NWS listing with no active stories gets no new warning.
    category: policy
    applies_to: _process_office
    trigger: list_stories returns an empty list
    logic: IF the listing is empty THEN nothing new is logged; the quiet alarm covers a long silence.
    violation: not applicable; this rule records a decision not to add a call.
    source: FR6.1, Q1 A
```

| Rule | Group | Plain statement |
|------|-------|-----------------|
| BR1.1 | Events | Every WARNING and ERROR passes an event |
| BR1.2 | Events | Names look like area.what and are unique |
| BR1.3 | Events | The two signal names are fixed |
| BR1.4 | Events | No other INFO line gets an event |
| BR1.5 | Events | Message text stays as it is in U2 |
| BR2.1 | Fields | Safe, snake_case field names |
| BR2.2 | Fields | One meaning per field name |
| BR2.3 | Fields | Caught failure: ERROR with stack; recoverable: WARNING with error |
| BR2.4 | Fields | Today's levels hold |
| BR3.1 | Secrets | No secret in any line |
| BR3.2 | Secrets | No full body, caption or image |
| BR3.3 | Secrets | A test proves the token stays out |
| BR4.1 | New warnings | run.slow past 150 s |
| BR4.2 | New warnings | No warning for an empty listing |
