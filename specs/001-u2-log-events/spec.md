# Feature Specification: U2 Log Events

**Feature Branch**: `001-u2-log-events`

**Created**: 2026-11-09

**Status**: Draft (revised 2026-11-09 to simplify)

**Input**: User description: "Continue unit U2 "log events" of the observability work in this repo (weather-story-bot, a Python 3.13 Lambda; read CLAUDE.md first). [...] Then finish the plan: new code first and its tests in the same change, `event` names on every WARNING and ERROR and the message-sent line, the `run.slow` warning, the drift and token-leak tests, and `docs/logging-review.md` kept in step. Do not change log message text, levels or stack traces. [...] One pull request for the unit; do not commit without asking me. After U2 the remaining observability units are U4 (sturdy alarms) and U5 (warnings-and-errors digest), which filter on U2's event names."

**Revision input** (owner, 2026-11-09): "Let's rewrite this spec so that we simplify logging while still keeping it within best practices."

## Context

This is unit U2 of the observability effort (`docs/roadmap.md`, Phase 2.3). U1 (the logging review,
`docs/logging-review.md`) and U3 (the health dashboard) are merged. U4 (sturdy alarms) and U5 (the
warnings-and-errors digest) come after this unit and filter on the event names it introduces.

**Why this spec was rewritten.** The first version kept and hardened the bot's hand-written JSON formatter: a
three-tier fallback, an import-time install, a request-id record factory, full branch coverage, and a slow-run timer
in the handler. A review found that most of that rebuilds what the platform already provides:

- Lambda's own **JSON log format** writes every Python log record as one JSON line with `timestamp`, `level`,
  `message`, `logger` and `requestId`, and puts the call's `extra={...}` fields at the top level. It also writes the
  runtime's `START`, `END` and `REPORT` lines as JSON, and it is in place before the package is imported.
- Lambda already publishes a **`Duration` metric** for every invocation, so a slow run can be caught by an alarm
  with no code.

This version keeps what is worth building, the event names, and lets the platform do the rest. The design in
`docs/handoff/u2-log-events/` is now background reading only. Where it differs from this spec, this spec wins, and
the differences are listed under Assumptions.

**State of the branch (checked 2026-11-09)**: the two Spec Kit initialisation commits on this branch (`b96bb46`,
`09e89b5`) swept in a formatter module (`src/weather_story_bot/log_format.py`) and an import-time install in
`src/weather_story_bot/__init__.py`. Neither commit is on `main`. This version of U2 does not use either file, so
neither ships (FR-018).

## Clarifications

### Session 2026-11-09

- Q: Should the quality gates in SC-007 also require `mise run tftest` and `mise run scan`, as the constitution does, or only lint, the tests and coverage? → A: Add them. The gate is `mise run lint ::: test ::: tftest ::: scan`, plus the coverage floor.
- Q: Should the tooling work now on this branch go to `main` in its own pull request before U2, or travel in U2's pull request? That work is the AI-DLC removal, the Spec Kit set-up, the constitution and the extensions. → A: Tooling first, in its own pull request without the two source files. U2 is rebuilt on the updated `main`, and its pull request holds only the unit and its spec documents.
- Q: Should U2 keep and harden the bot's own JSON formatter, or switch to Lambda's built-in JSON log format, and should the slow-run warning be code in the handler or an alarm on Lambda's `Duration` metric? → A: Switch to Lambda's JSON log format and delete the custom formatter. The slow-run check becomes a `Duration` alarm in U4. U2 keeps the event names, the field-name fixes, the token-leak test and a simple drift check. The owner accepts, without a spike, that the runtime's formatter writes extra fields and stack traces as the AWS documentation describes.
- Q: Before production is approved, how should anyone confirm that staging's real log lines have the expected shape: JSON, `event` at the top level, `office` present? → A: A manual gate. Before approving production, the owner runs a short Logs Insights query against the first staging run. The U2 pull request includes the query and the steps.

### Session 2026-11-20

- Q: Should the spec documents ship with the code in one pull request, or first on their own? → A: First on their own. The documents in `specs/001-u2-log-events/` go to `main` in a pull request of their own, so the design is reviewed on its own and no longer lives only on a local branch. The code then ships as one pull request with its tests and the documents it keeps in step. This replaces the part of the 2026-11-09 answer that put the spec documents in U2's pull request.

## User Scenarios & Testing *(mandatory)*

The "user" is the owner, who runs this single-user bot, together with the two later units (U4 alarms, U5 digest)
that read its logs. The owner never reads raw log text day to day. They read alarm emails, the dashboard and the
weekly digest. Today two metric filters match message text ("Telegram message sent", "Ambiguous stories from NWS")
and feed three alarms, which the U3 dashboard charts. After U4 the alarms, and from the start the U5 digest, read a
line's **event**, **level** and **logger**, and never its message.

### User Story 1 - Every warning and error says what kind it is (Priority: P1)

When the bot logs a warning or an error, the line carries a stable, named kind (an *event*, such as
`nws.list_failed` or `telegram.rate_limited`) that does not depend on the wording of the message. The one
informational line that counts deliveries ("Telegram message sent") carries one too. U4 and U5 can then count and
alarm on kinds instead of on exact sentences.

**Why this priority**: it is the contract U4 and U5 are built on, and it is the one part of structured logging the
platform cannot provide.

**Independent Test**: drive each failure path of the bot offline and read the captured log records. Every warning
and error record has its decided event, and the message-sent record has `telegram.message_sent`.

**Acceptance Scenarios**:

1. **Given** the NWS listing fails, **When** the run logs the failure, **Then** the record is at ERROR, says "Failed to list stories" as it does today, and carries event `nws.list_failed`.
2. **Given** NWS returns stories that cannot be told apart, **When** the run rejects them, **Then** an ERROR record with the unchanged message "Ambiguous stories from NWS" carries event `nws.ambiguous_stories`.
3. **Given** a story is accepted by Telegram, **When** the send is logged, **Then** the INFO record "Telegram message sent" carries event `telegram.message_sent`, and it is the only INFO record with an event.
4. **Given** any of the bot's log calls (L01 to L19 in the review's table 1), **When** it logs, **Then** its message text, its level and whether it includes a stack trace are exactly as before this unit.

---

### User Story 2 - Every log line is structured, by the platform (Priority: P1)

In the deployed function, every record from any logger, the bot's own or a library's, arrives in the log group as
one JSON line written by the Lambda runtime. The line has the time, level, logger, message and request id, plus the
call's extra fields (the event among them) at the top level. Lines written while an office is being processed also
carry `office`. The bot no longer formats its own lines.

**Why this priority**: an alarm cannot count a record it cannot read. Using the platform's format removes a
hand-written formatter and its failure modes from the bot.

**Independent Test**: offline, check the infrastructure configuration and the bot's logging set-up. After deploying
to staging, read one run's lines in the log group.

**Acceptance Scenarios**:

1. **Given** the function's infrastructure, **When** the offline `terraform test` runs, **Then** it asserts that the log format is JSON and that the application and system log levels are both INFO.
2. **Given** an office is being processed, **When** any record is logged, **Then** it carries `office` without the caller passing it, and a record logged after that office's scope ends, normally or by an error, does not.
3. **Given** the bot's logging set-up runs, **Then** it adds no handler and installs no formatter of its own, sets the root level to INFO, and caps the HTTP client libraries' loggers at WARNING. Running it twice changes nothing.
4. **Given** the change is deployed to staging, **When** a run completes, **Then** its lines in the log group are JSON with `timestamp`, `level`, `logger`, `message` and `requestId`. If the run posted, the message-sent line carries `event` and the posts metric filter counts it. The ambiguous-stories filter is accepted by inference: it reads the same `message` key with the same match form, so the posts filter counting proves it too (SC-006).

---

### User Story 3 - The Telegram token never reaches the logs (Priority: P1)

On every handled Telegram failure, no log record contains the bot token, the Telegram API host, the story caption
or the image bytes. The check proves that it actually exercised the token-bearing request, so it cannot pass
vacuously.

**Why this priority**: the repository is public, and a leaked token gives anyone control of the channel. More
structured fields on more lines means more places a secret could slip in.

**Independent Test**: use a recognizable fake token and drive every handled failure: a transport error, a 429
followed by success, a photo rejected and then sent as a document, an unexpected result, a failed delete, and an
HTTP error status on each Telegram method. Search every captured record's message and every field value.

**Acceptance Scenarios**:

1. **Given** each handled Telegram failure, **When** its records are captured, **Then** no message, field value or stack trace contains the token, `api.telegram.org`, the caption or the image bytes.
2. **Given** the leak check passes, **Then** the check has also shown that the mocked token-bearing request was made.
3. **Given** logging is set up as in production, **Then** the HTTP client libraries' loggers are capped at WARNING, so request URLs are never logged at INFO.

---

### User Story 4 - Code and review cannot drift apart unnoticed (Priority: P2)

A simple automated check fails when a warning or error call has no event, when an informational call other than
message-sent has one, when a call passes a field name the line already owns, or when the events in the code differ
from the list in `docs/logging-review.md` table 1. The two signal events are proven on their real paths, with the
names written out in the checks.

**Why this priority**: it keeps the U2 contract true after this unit ships, which U4 and U5 rely on.

**Independent Test**: run the check against the finished code (it passes), then against a few small bad samples
(each fails, naming the problem and where it is).

**Acceptance Scenarios**:

1. **Given** a new warning call without an event, **When** the checks run, **Then** they fail and name the module, the line and the message.
2. **Given** the review's table 1 lists an event the code does not emit (or the reverse), **When** the checks run, **Then** they fail and name the difference.
3. **Given** someone renames `telegram.message_sent` in the code, **When** the checks run, **Then** the real-path check fails.

---

### Edge Cases

- **A library logs a warning while the package is being imported.** The runtime's JSON handler is assumed to be in place already, so the line is JSON and no import-time set-up is needed (see Assumptions).
- **A record logged outside any office** (start-up, reading the token, the run summary) carries no `office`.
- **Local runs** (`uv run weather-story-bot --dry-run`, the test suite) do not have the runtime's formatter and keep Python's plain-text output, exactly as on `main` today. Only the deployed function writes JSON.
- **Two events in one invocation** are two separate lines (for example a transport retry and then a listing failure).
- **`office` passed as an extra field** would collide with the stamped value. The drift check forbids it.
- **The runtime's own lines** (`START`, `END`, `REPORT`, and its report of an unhandled error) become JSON too. They carry no `event`. A failed run is counted through the Lambda `Errors` metric, as today, never from these lines (the rule for U4 and U5 is under Key Entities).
- **A slow run** is no longer logged by the bot. U4 adds an alarm on the `Duration` metric instead.

## Requirements *(mandatory)*

### Functional Requirements

**Lines: the platform formats them**

- **FR-001**: The deployed function's logging configuration MUST set, explicitly, the JSON log format, the application log level INFO and the system log level INFO, and keep its existing log group. INFO is Lambda's default system level; it is written out so the configuration says what it relies on. The system level must stay at INFO so the `REPORT` lines stay in the log group: they are the only per-run record of duration and memory a person can read beside the run's own lines, which the `Duration` metric alone does not give. An offline `terraform test` MUST assert all three settings.
- **FR-002**: The bot MUST NOT install its own formatter or handler in the deployed function. Its logging set-up only sets the root level to INFO and caps the `httpx` and `httpcore` loggers at WARNING, and running it again changes nothing. The set-up runs after the runtime's, so its root level is the one in effect; it MUST equal the application log level in FR-001, and changing either one means changing both in the same pull request.
- **FR-003**: Every record logged while an office is being processed MUST carry `office`, added from scoped context and never passed by callers. Leaving the scope, normally or by an error, MUST restore the previous value. The bot MUST NOT stamp the request id itself, because the runtime writes `requestId`. The per-run history record keeps its request id as today.

**Events**

- **FR-004**: Every WARNING, ERROR and CRITICAL log call of the bot MUST pass its decided event as a fixed literal: a plain string constant written as the value of the `"event"` key in the dict literal passed as `extra=` at the call. The names are those in `docs/logging-review.md` table 1: `office.lease_failed`, `nws.list_failed`, `office.process_failed`, `nws.image_download_failed`, `store.read_failed`, `office.lease_release_failed`, `nws.ambiguous_stories`, `story.process_failed`, `telegram.delete_failed`, `telegram.photo_rejected`, `telegram.rate_limited`, `nws.retry_transport_error`, `nws.retry_server_error`, `history.write_failed`. No CRITICAL call exists today; adding one means adding its own event to table 1 in the same change.
- **FR-005**: The message-sent INFO call MUST carry `telegram.message_sent`, and the ambiguous-stories ERROR MUST carry `nws.ambiguous_stories`. Both MUST be emitted on their real paths. No other INFO call may carry an event.
- **FR-006**: No log call's message text, level or stack-trace behaviour may change. *Stack-trace behaviour* means whether the call records a stack trace (table 1's Stack column). The key and shape the trace appears under in the line belong to the runtime and are not part of this rule. This unit adds no new log message.

**Field names**

- **FR-007**: The NWS server-error retry call MUST name its HTTP code `http_status`, and the Telegram message-deleted call MUST name its id `telegram_message_id`.
- **FR-008**: A warning that logs a caught exception MUST put it under `error` as the exception's full representation (class and arguments), not its bare text. The photo-rejected call's `reason` field becomes `error`.
- **FR-009**: No call may pass an extra field whose name is a standard log-record attribute or a name the line already owns: `timestamp`, `level`, `logger`, `message`, `requestId`, `location` (the runtime reserves it and drops an extra of that name), `office`, plus Python's reserved `asctime`. Every extra field name MUST be lowercase snake_case.

**Secrets**

- **FR-010**: An automated check MUST show that no handled Telegram failure puts the token, the Telegram API host, the caption or the image bytes into any log record's message, field values or stack trace. It MUST also show that the token-bearing request was exercised.
- **FR-011**: An automated check MUST read back the `httpx` and `httpcore` log caps as WARNING after the logging set-up.

**Drift check**

- **FR-012**: An automated check MUST fail, naming the module, line and message, when a WARNING, ERROR or CRITICAL call (or the message-sent call) in `src/weather_story_bot/` has no fixed event literal, when another INFO call has one, or when a call passes a forbidden extra field name (FR-009). The check is a guardrail, not a proof: it reads `logger.<level>("constant message", extra={...})` calls only, and it does not try to catch a call written in another form (a non-constant message, `logger.log(...)`, a call on the `logging` module); a reviewer reads those. A WARNING, ERROR or CRITICAL call, and the message-sent call, MUST pass `extra=` as a dict literal whose `"event"` value is a string constant; with any other `extra=`, the call counts as having no event. An INFO call without an event may pass a dict built elsewhere (today only "Story posted", L10); the check cannot read its keys, so its own unit test pins them. The history-write call (L19) lists its fields in the literal instead of spreading them.
- **FR-013**: An automated check MUST fail, naming the difference, when the set of events in the code differs from `docs/logging-review.md` table 1, or when an event name does not match `^(nws|telegram|office|story|store|history|run)\.[a-z_]+$`.
- **FR-014**: The two signal events MUST be proven on their real paths, with the names written out in the checks rather than borrowed from the code.

**Review and contract kept in step**

- **FR-015**: `docs/logging-review.md` MUST be kept in step in the same change. Its fields column shows the renamed fields. The slow-run row (L20) and its rule are removed, and decision D5 moves to U4 as a `Duration` alarm. "What U2 must build" describes this version.
- **FR-016**: After this unit, adding or renaming an event changes the call, table 1 and the line contract in one pull request. Renaming a signal event also changes the metric filter that reads it in that pull request.

**Delivery**

- **FR-017**: The spec documents (`specs/001-u2-log-events/`) MUST ship first, in a pull request of their own that changes nothing else. The unit's code MUST then ship as one pull request, together with its tests, `docs/logging-review.md` (FR-015) and any updates to these documents. New code and its tests MUST be in the same change. No commit is made without the owner's go-ahead.
- **FR-018**: The tooling work now on this branch (the AI-DLC removal, the Spec Kit set-up and the constitution; the Spec Kit extensions were removed on 2026-11-09 and do not ship) MUST reach `main` first, in its own pull request. That pull request leaves out `log_format.py` and the `__init__.py` change, which this version of U2 does not use either. U2's pull request is then built on the updated `main`.
- **FR-019**: The only infrastructure change is the function's logging configuration (FR-001). The unit MUST NOT change alarms, metric filters or what is posted to Telegram.
- **FR-020**: The U2 pull request MUST include a Logs Insights query and the steps to run it against the first staging run after deploy. The query MUST show, for each of the run's application lines (those with a `level`), the `timestamp`, `requestId`, `level`, `logger`, `office`, `event`, `message`, `time` and `aws_request_id`; the last two are the old formatter's keys, selected so their absence shows. The steps MUST state the pass condition for each key (SC-006). The owner runs it and checks the result before approving the production deploy. If the check fails, the owner declines the production approval and staging is put back through a revert pull request of the U2 merge, which the pipeline deploys like any other change; the fix then comes in a new pull request. The query lives in the pull request and the feature's documents, not in Terraform.

### Key Entities

- **Log line**: one JSON record in the function's log group, written by the Lambda runtime. U4 and U5 may rely on `level`, `logger`, `event`, `timestamp`, `requestId` and `office`, and on `message` until U4 moves the filters off it. Every other key is per-call detail and may change. U4 and U5 MUST count only lines that have an `event`, or a library's `logger` at WARNING or above. A line with neither (the runtime's own lines, including its report of an unhandled error) is never counted; failed runs come from the `Errors` metric and slow runs from `Duration`.
- **Event name**: the stable kind of a log call, written as `area.what`: lowercase, exactly one dot, an area from nws, telegram, office, story, store, history or run, and a `what` made of lowercase letters and underscores. Each log call has exactly one event, and each event belongs to exactly one log line (one message). One log call may serve several paths: the single history-write call (L19) is reached from three write paths, so all three emit `history.write_failed`. Two events are *signals* that alarms count: `telegram.message_sent` and `nws.ambiguous_stories`.
- **Log call**: one logging statement in the bot (L01 to L19 in the review's table 1), with a fixed message, a level, its extra field names and, where required, its event.
- **Office context**: the office stamped on every record written while it is processed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the bot's WARNING, ERROR and CRITICAL log calls (every logging call in `src/weather_story_bot/`), plus the message-sent call, carry an event from the review's list. An automated check counts them and finds no exceptions.
- **SC-002**: The set of event names in the code and the set in the logging review are identical: zero differences.
- **SC-003**: 0 changes to existing log message text, levels or stack-trace behaviour (as FR-006 defines it). The baseline is the code and table 1 on `main` at the commit U2's branch starts from. The three alarms that match on message text keep firing on the same lines as before.
- **SC-004**: Across every handled Telegram failure path, 0 captured log records contain the token, the API host, the caption or the image bytes, and the check proves that the token-bearing request ran.
- **SC-005**: The bot's own logging code shrinks: no custom formatter, no request-id stamping, and no handler or formatter installed at import remain in `src/`. The office record factory, which is set at import, stays (FR-003).
- **SC-006**: Before production is approved, the owner's query (FR-020) on the first staging run after deploy passes only if all of these hold, and fails otherwise:
  1. it returns at least one row (zero rows fails: the run did not happen or the lines are not JSON);
  2. every row has `timestamp`, `requestId`, `level` and `logger`;
  3. for each office in staging's configuration, the lines written while it was processed have `office` set to it, and "Run complete" has no `office` (this also tests the record-factory assumption);
  4. no row has `time` or `aws_request_id`;
  5. if the run posted, the "Telegram message sent" line has `event` = `telegram.message_sent` and the posts metric counts it.

  A run that posted nothing passes on checks 1 to 4, which prove the shape; check 5 then waits for the first staging run that posts. The ambiguous-stories filter is accepted by inference from check 5 (US2 scenario 4).
- **SC-007**: The project's quality gates pass: `mise run lint ::: test ::: tftest ::: scan` is green, and project line coverage is at least 80%.
- **SC-008**: The owner's local dry run shows the same decisions, captions and output as on `main`.

## Assumptions

- **The platform formats the lines.** Lambda's JSON log format writes `extra` fields at the top level and records stack traces in its own fields, as the AWS documentation describes. The owner accepts this without a spike.
- **Attributes set by the record factory are written like `extra` fields.** `extra` works by setting record attributes, so the runtime is assumed to write the factory's `office` the same way. Accepted unverified; SC-006 check 3 tests it on staging.
- **A value the runtime cannot serialise is an accepted risk.** How the runtime writes such a value is not known, and a broken or missing line would also be missing from the counts. Today every extra the bot passes is a string, number, boolean, null, or a list or dict of those, so none is at risk.
- **The runtime's handler is in place before the package is imported.** This covers a library warning at import time. Accepted unverified, from the AWS documentation.
- **The `level` spelling is unverified.** The contract expects Python's level names (`WARNING`, not Lambda's `WARN`). A normal run logs only INFO, so the staging check cannot settle it. U4 and U5 confirm the spelling from the first real WARNING line before a filter relies on it.
- **The runtime may add keys of its own beyond those listed.** The drift check forbids the keys the documentation names. If the staging lines show another lowercase key the runtime owns, it is added to FR-009's list in a later change.
- **The window between the staging and production deploys is harmless.** For that time the two environments write different line shapes, but only the `$.message` metric filters read the lines and the dashboard charts alarm metrics, so nothing breaks.
- **Field names follow the platform.** Lines use the runtime's `timestamp` and `requestId` rather than the custom formatter's `time` and `aws_request_id`. No filter or alarm reads either today. The two metric filters read `message`, whose key and text are unchanged.
- **The slow run moves to U4.** An alarm on the `Duration` metric's maximum above 150 seconds (half the unchanged 300-second limit) replaces the handler's `run.slow` warning. U2 writes no slow-run code, and `run.slow` is not an event.
- **The event names come from U1.** `docs/logging-review.md` table 1 is the source of truth for event names, levels, messages and stack traces, because the drift check reads it. The field changes come from the review's decisions D1 to D3.
- **Differences from the handoff** (`docs/handoff/u2-log-events/`): no custom formatter, fallback tiers, record factory for the request id or import-time install (its ADR on the formatter, rules BR1.1 to BR1.7 and OQ1 no longer apply); no `run.slow` (its BR4.1 and BR4.2 move to U4); line keys follow the runtime; an event belongs to one log line rather than one call site; and there are two message-based metric filters feeding three alarms, not three filters.
- **Out of scope:** moving the alarm filters from message text to events (U4), the `Duration` alarm (U4), the digest (U5), any CI change, and any change to what is posted.
- **Constitution, Principle V:** the alarm-contract message strings and the `message` key do not change, so `infra/monitoring.tf` is untouched. Principle IV is met by pinning the events with tests. Principle VI is served: the change removes code and adds no dependency.
