# Entities: u1-logging-review

## Sources

- `inception/units-generation/unit-of-work.md` (U1) and `inception/requirements-analysis/requirements.md` (FR6.1, FR6.2) [FR6.1]
- A read of every log call in `src/weather_story_bot/` (19 calls in four modules) [FR6.1]
- `functional-design-questions.md` (Q1 to Q3)

The review is a document, so its entities are the things the document lists: the calls it inventories, the
findings it reports and the decisions it records. They are rows in `docs/logging-review.md`, not stored data.

```yaml
entities:
  - name: LogCall
    description: One logger call in src/weather_story_bot/, as it is today (L01 to L19) or as the review adds it (L20).
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "L01 to L20, numbered by module (handler, telegram, nws, history) then line; L20 is the one new call" }
      - { name: module, type: enum, required: true, allowed: [handler, telegram, nws, history] }
      - { name: level, type: enum, required: true, allowed: [INFO, WARNING, ERROR] }
      - { name: message, type: string, required: true, constraints: "the exact text today; unchanged in U2 (BR1.5)" }
      - { name: fields, type: "list of string", required: true, default: "[]", constraints: "names of the extra fields the call passes" }
      - { name: has_stack_trace, type: boolean, required: true, constraints: "true for logger.exception calls" }
      - { name: event, type: string, required: false, constraints: "required when level is WARNING or ERROR, and for the message-sent line (BR1.1, BR1.3); follows BR1.2" }
      - { name: signal, type: boolean, required: true, default: false, constraints: "true only for the two calls an alarm filters on (BR1.3)" }
    constraints:
      - "Exactly 19 existing calls: 7 WARNING, 7 ERROR, 5 INFO; the review adds one WARNING (L20), so 8, 7 and 5"
      - "event is unique across LogCalls"
    relationships:
      - { to: Finding, cardinality: "one LogCall to zero or many Findings", direction: "LogCall <- Finding.call_ids" }

  - name: Finding
    description: A problem the review found in one or more calls.
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "F1, F2, ..." }
      - { name: call_ids, type: "list of LogCall.id", required: true }
      - { name: category, type: enum, required: true, allowed: [level, message, field, consistency, secret, coverage] }
      - { name: description, type: string, required: true }
    relationships:
      - { to: Decision, cardinality: "one Finding to exactly one Decision", direction: "Finding -> Decision" }

  - name: Decision
    description: What the review decides to do about a finding, and which unit carries it out.
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "D1, D2, ..." }
      - { name: finding_id, type: "Finding.id", required: true }
      - { name: outcome, type: enum, required: true, allowed: [change, keep, new-call] }
      - { name: carried_out_in, type: string, required: false, constraints: "u2-log-events for change and new-call; empty for keep" }
      - { name: rationale, type: string, required: true }

  - name: EventName
    description: The stable kind of a log call, written at the call site as extra={"event": "<name>"}.
    attributes:
      - { name: value, type: string, required: true, unique: true, constraints: "matches BR1.2" }
      - { name: call_id, type: "LogCall.id", required: true }
    relationships:
      - { to: LogCall, cardinality: "one EventName to one LogCall", direction: "EventName -> LogCall" }
```

Four entities: LogCall (the inventory row), Finding (a problem), Decision (the answer to it) and EventName (the
stable kind of a call). Each Finding has exactly one Decision, and each EventName belongs to one LogCall.
