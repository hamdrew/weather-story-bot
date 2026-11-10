# Entities: u2-log-events

## Sources

- `inception/units-generation/unit-of-work.md` (U2) and `unit-of-work-story-map.md` [FR2.1, FR2.2, FR2.3, FR2.4, FR5.2, FR6.3]
- `inception/domain-design/components.md` (LogFormatter, SignalContractCheck) and `decisions.md` (ADR-001, ADR-002, ADR-003, ADR-005) [FR2.3, FR5.2]
- `docs/logging-review.md` (tables 1 and 3, "What U2 must build"): the event names and field changes this unit carries out [FR6.3]
- A read of `src/weather_story_bot/handler.py` (today's `JsonFormatter`, record factory and context variables), `telegram.py`, `nws.py`, `history.py` and `tests/test_logging_review.py`

The entities are the shapes this unit's code writes or reads: the log line, the event name on it, the request
context stamped on it, the log call that produces it and the timing behind the slow-run line. None of them is
stored data; a LogLine exists only as a line in the Lambda's CloudWatch log group.

```yaml
entities:
  - name: LogLine
    description: One JSON object on one line, written for every log record at or above the root logger's level. Alarms and the dashboard read only event, level and logger.
    attributes:
      - { name: time, type: timestamp, required: true, constraints: "UTC, ISO 8601, from the record's creation time; today's field name, not timestamp (ADR-005)" }
      - { name: level, type: enum, required: true, allowed: [DEBUG, INFO, WARNING, ERROR, CRITICAL] }
      - { name: logger, type: string, required: true, constraints: "the logger's name: weather_story_bot, weather_story_bot.<module>, or a third-party name such as httpx or botocore" }
      - { name: message, type: string, required: true, constraints: "the formatted message text; unchanged by this unit except for the new Run was slow line" }
      - { name: event, type: string, required: false, constraints: "present when the call passed extra={event: ...}; required on every WARNING, ERROR and CRITICAL call of the bot's own loggers and on the message-sent line; absent from third-party records" }
      - { name: office, type: string, required: false, constraints: "present while an office is being processed (from RequestContext)" }
      - { name: aws_request_id, type: string, required: false, constraints: "present during an invocation (from RequestContext)" }
      - { name: exception, type: string, required: false, constraints: "the formatted stack trace when the record has exc_info" }
      - { name: extra_fields, type: "map of string to JSON value", required: false, default: "{}", constraints: "every other extra field of the call; a value that is not JSON-serializable is written with str(); none repeats time, level, logger, message, exception, office or aws_request_id" }
      - { name: formatter_error, type: string, required: false, constraints: "present only on a fallback line; the class name of the exception that stopped the full line" }
    constraints:
      - "One line per record: the JSON text holds no raw newline (a stack trace is one escaped string)"
      - "time, level, logger and message are never overwritten by an extra field"
      - "A fallback line (formatter_error present) holds only time, level, logger, message, formatter_error and, when they are safe strings, event, office and aws_request_id"
    relationships:
      - { to: EventName, cardinality: "one LogLine to zero or one EventName", direction: "LogLine.event -> EventName.value" }
      - { to: RequestContext, cardinality: "one LogLine to zero or one RequestContext", direction: "LogLine.office and LogLine.aws_request_id <- RequestContext" }

  - name: EventName
    description: The stable kind of a log call, written at the call site as the literal extra={"event": "<name>"}.
    attributes:
      - { name: value, type: string, required: true, unique: true, constraints: "lowercase, area.what, area one of nws, telegram, office, story, store, history or run (the form docs/logging-review.md BR1.2 sets)" }
      - { name: level, type: enum, required: true, allowed: [INFO, WARNING, ERROR], constraints: "INFO only for telegram.message_sent" }
      - { name: signal, type: boolean, required: true, default: false, constraints: "true only for telegram.message_sent and nws.ambiguous_stories, the two names an alarm filter reads" }
    relationships:
      - { to: LogCall, cardinality: "one EventName to exactly one LogCall", direction: "EventName -> LogCall" }

  - name: LogCall
    description: One logger call in src/weather_story_bot/ (L01 to L20 in docs/logging-review.md table 1).
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "L01 to L20" }
      - { name: level, type: enum, required: true, allowed: [INFO, WARNING, ERROR, CRITICAL] }
      - { name: message, type: string, required: true, constraints: "a constant string; the review's table 1 and the code agree on it" }
      - { name: extra_keys, type: "list of string", required: true, default: "[]", constraints: "lowercase snake_case; none is a LogRecord attribute and none repeats a LogLine field the formatter owns" }
      - { name: event, type: "EventName.value", required: false, constraints: "required when level is WARNING, ERROR or CRITICAL, and on L14" }
    constraints:
      - "A call that needs an event passes it in a dict literal given as extra, so a test can read it without running the call"

  - name: RequestContext
    description: The identifiers stamped on every record created while they are set, without any caller passing them.
    attributes:
      - { name: aws_request_id, type: string, required: false, constraints: "set once per invocation from the Lambda context; unset outside an invocation" }
      - { name: office, type: string, required: false, constraints: "set once per office inside an invocation; unset outside the office loop" }
    constraints:
      - "Each is set by a scope that restores the previous value on exit, even on an exception, so a value never outlives its scope"
      - "A caller never passes either name in extra (logging raises KeyError for a name the record already holds)"

  - name: RunTiming
    description: The measurement behind the Run was slow warning (L20). It is a value held for the length of one invocation, not stored.
    attributes:
      - { name: started, type: number, required: true, constraints: "a monotonic clock reading taken as the first statement of the handler" }
      - { name: duration_seconds, type: number, required: true, constraints: "monotonic now minus started, at the moment run() returns; written to the line rounded to one decimal" }
      - { name: threshold_seconds, type: number, required: true, default: 150, constraints: "half the 300-second Lambda timeout (docs/logging-review.md BR4.1)" }
```

Five entities: LogLine (what is written), EventName (its stable kind), LogCall (where it comes from), RequestContext
(the office and request id stamped on it) and RunTiming (the one measurement this unit adds). The ownership
follows `components.md`: LogLine and RequestContext belong to LogFormatter; EventName and LogCall are
conventions the drift test enforces.
