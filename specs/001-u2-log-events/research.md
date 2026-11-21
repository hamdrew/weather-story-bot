# Research: U2 Log Events (revised)

Phase 0 of [plan.md](plan.md). The spec has no open clarifications. Each entry records a design decision, why it was
chosen and what else was considered. This replaces the first version's research, whose R1 (the C2 import-time checks),
R3 (the slow-run clock) and R6 (the three-tier formatter) no longer apply.

## R1. Let Lambda format the lines

**Decision**: in `infra/lambda.tf`, set `logging_config` to `log_format = "JSON"`, `application_log_level = "INFO"`
and `system_log_level = "INFO"`, and keep `log_group`. Replace the block's comment ("The handler formats its own JSON
log lines.") with one saying the runtime writes the JSON lines and that `application_log_level` must equal the root
level `configure_logging()` sets (FR-002). Add a `terraform test` assertion for all three in
`infra/tests/lambda.tftest.hcl`.

**Rationale**: the AWS Lambda developer guide ("Using Lambda advanced logging controls with Python") documents that,
with the JSON format, every record from Python's `logging` is written as one JSON object with `timestamp`, `level`,
`message`, `logger` and `requestId`, and that `extra={...}` keys appear at the top level. It is set up by the runtime
before the handler module is imported, so it also covers records libraries write while they load (accepted
unverified, spec Assumptions). INFO is Lambda's default system level; it is set explicitly so the configuration states
what the `REPORT` lines depend on. Those lines are the per-run duration and memory a person reads beside the run's own
lines, which U4's `Duration` alarm complements but does not replace. The mock-provider
`terraform test` validates the attribute names against the provider schema offline.

**Alternatives considered**: keeping and hardening the hand-written formatter (rejected: rebuilds the platform, and
needs a fallback design, an import-time install and full branch coverage); Powertools for AWS Lambda `Logger` (rejected:
a new runtime dependency or layer for features this single-user bot does not need, against constitution Principle VI);
`python-json-logger` or `structlog` (rejected for the same reason).

**Accepted without a spike** (owner, spec Clarifications): how the runtime writes a field it cannot serialise, and the
exact keys it uses for stack traces. The staging check (FR-020) is the first look at real lines.

## R2. The bot's logging set-up shrinks to levels

**Decision**: `configure_logging()` keeps only `logging.getLogger().setLevel(logging.INFO)` and the `httpx` and
`httpcore` caps at WARNING. It no longer adds a handler or sets a formatter. Delete `JsonFormatter` and
`_STANDARD_LOG_ATTRS` from `handler.py`.

**Rationale**: in Lambda the root logger already has the runtime's handler and JSON formatter. Replacing that formatter,
as today's code does, would undo R1. The caps stay because `httpx` logs request URLs at INFO, and Telegram URLs hold the
token. Running `configure_logging()` twice is still harmless: it only sets levels.

**Who owns the root level**: `lambda_handler` calls `configure_logging()` after the runtime has set the root level from
`application_log_level`, so the code's INFO is the level in effect. The two must stay equal (FR-002). A comment beside
each says so.

**Alternatives considered**: removing `configure_logging()` entirely and relying on `application_log_level` (rejected:
the `httpx` caps must be set in code anyway); dropping only the root `setLevel` (rejected: if the runtime ever left the
root at Python's default WARNING, the INFO message-sent line, and with it the posts metric, would vanish silently).

**Local behaviour**: the CLI never calls `configure_logging()`, and on `main` the package installs no formatter at
import. Local dry runs therefore keep Python's default output (WARNING and above, plain text, to stderr), unchanged.

## R3. The request id moves from logs to an argument

**Decision**: delete `_aws_request_id`, `_invocation_context` and the request-id half of the record factory. Give
`run()` a keyword `aws_request_id: str | None = None`, which it passes to `history.record_run`. `lambda_handler` calls
`run(settings.offices, _services, aws_request_id=context.aws_request_id)`.

**Rationale**: the runtime writes `requestId` on every line, so stamping it again would duplicate it under another name.
The history record still needs it (`RUN#` items keep `aws_request_id`), and an explicit argument is simpler than a
context variable. A bare `run()` (tests, local use) passes nothing, so its run record omits the id, as today
(`test_record_run_without_request_id_omits_it`).

**Alternatives considered**: keeping the context variable only for the history record (rejected: a scope and a reset to
carry one value one call deep).

## R4. Office stays as a small record factory

**Decision**: keep the `_office` context variable, `_office_context()` and a record factory that sets `record.office`
while an office is being processed. Rename the factory to say it stamps the office only.

**Rationale**: `office` is the one per-line field the runtime cannot know. A record factory, unlike a logger filter, also
reaches the child loggers (`weather_story_bot.telegram`, `.nws`, `.history`), and `test_log_lines_carry_their_own_office_and_never_a_stale_one`
already pins this behaviour. The runtime's JSON formatter writes record attributes added this way just as it writes
`extra` keys, because `extra` works by setting record attributes.

**Alternatives considered**: passing `office` in `extra` at every call (rejected: about twenty call sites, and easy to
forget); a `LoggerAdapter` (rejected: the child modules would need one too).

## R5. Field names the drift check forbids

**Decision**: forbid every standard `LogRecord` attribute (`vars(logging.makeLogRecord({}))`), plus `message`,
`asctime`, `timestamp`, `level`, `logger`, `requestId` and `office`, and require lowercase snake_case
(`^[a-z][a-z0-9_]*$`).

**Rationale**: these are the names the runtime's line or Python's logging owns (FR-009). The snake_case rule also
excludes every camelCase key the runtime adds, such as `requestId` or its stack-trace fields, without the check needing
to know them. It cannot exclude a lowercase key the runtime adds that the documentation does not name (for example a
possible `location`). That is an accepted gap (spec Assumptions): if the staging lines show one, it joins the list.

## R6. A simple drift check, built on the existing test

**Decision**: extend `tests/test_logging_review.py`, which already parses `src/` with `ast`, reads table 1 and checks
levels and event-name shape:

1. Change `_log_calls()` to return each call's level, line, message and `extra` dict literal, and to report any logging
   call it cannot read: a `logger.<level>(...)` whose message is not a `str` constant, a `logger.log(...)`, or a call on
   the `logging` module (FR-012).
2. Every WARNING, ERROR and CRITICAL call, and the "Telegram message sent" call, has `"event"` with a `str` constant in
   a dict literal `extra=` whose keys are all `str` constants, with no `**` spread. A non-literal `extra=` is allowed
   only on an INFO call without an event (today L10, "Story posted", whose keys its handler test pins). No other call
   has an `"event"` key. No readable `extra` key is forbidden (R5).
   L19 changes to match: `_log_failure(write, exc, image_id=None)` writes
   `extra={"event": "history.write_failed", "history_write": write, "error": repr(exc), "image_id": image_id}`. The
   `run` write therefore logs `image_id` as null. That is per-call detail, not contract.
3. The set of event constants in `src/` equals the events in table 1 (FR-013).
4. Tighten `_EVENT` to `^(nws|telegram|office|story|store|history|run)\.[a-z_]+$` and drop `_AREAS`.
5. Each new rule has one small bad-source test, run through a helper that takes source text instead of reading `src/`.

**Rationale**: the existing tests already cover half of this, and one file stays the single place the contract is
checked. One bad sample per rule proves each rule can fail.

**Alternatives considered**: a runtime check in the bot (rejected: tests are enough and add no production code); the
earlier plan's separate `problems()` framework with many bad snippets (rejected as heavier than twenty calls need).

## R7. The token-leak test reads records, not formatted lines

**Decision**: a new `tests/test_log_secrets.py`. A fake token (`"123456:LEAK-CANARY"`) and respx routes for each
handled Telegram failure. Each failure is driven through `handler.run(...)`, not through `TelegramClient` alone. On
most paths the client raises without logging, and the records that hold a Telegram exception are the handler's: L09
(with its stack trace) and L11 (with `error` as `repr(exc)`). Each test calls `configure_logging()` first, as
production does, and captures at the levels it sets, so `httpx` and `httpcore` records are seen under the production
caps. A fixture saves the root, `httpx` and `httpcore` levels and restores them afterwards. Each test asserts that
records were captured, and that an L09 record with a stack trace exists wherever that path applies, so no check runs
over nothing. For each path, assert that the token-bearing route was called and
that neither the token, `api.telegram.org`, the caption nor the image bytes appears in any record's `getMessage()`, any
attribute value's `repr()`, or its formatted stack trace. Separately, after `configure_logging()`, assert that `httpx`
and `httpcore` have level WARNING (FR-011).

**Rationale**: the runtime's formatter is not available offline, and it only serialises what the record holds. So a
record that holds no secret cannot produce a line with one. Searching every attribute's `repr()` also catches values
the line would show. The existing `test_delete_transport_error_hides_token` and
`test_transport_error_is_not_retried_and_hides_token` check exception text, not logs, and stay.

**Paths driven**: transport error on send; 429 then success; photo rejected then sent as a document; unexpected result
(no `message_id`); an HTTP error status on `sendPhoto`, on `sendDocument` (after a photo rejection) and on
`deleteMessage` during an update. The delete path is covered here too, because the existing check in `test_handler.py`
only searches `caplog.text`: it does not look at field values, the API host or a stack trace. That existing check
stays.

## R8. Tests that change with the formatter's removal

| Test | Change |
|------|--------|
| `test_handler.py::test_json_formatter_includes_extra_fields` | delete, with `JsonFormatter` |
| `test_handler.py::test_lambda_handler_end_to_end` | drop the assertions that log records carry `aws_request_id`; keep the `RUN#` history assertion |
| `test_handler.py::test_aws_request_id_does_not_leak_into_a_later_bare_run` | delete: with no context variable there is nothing to leak; `test_posts_are_recorded_as_events_and_the_run_as_a_run_record` covers a bare run's `RUN#` item |
| `test_handler.py::test_log_lines_carry_their_own_office_and_never_a_stale_one` | unchanged; it pins R4 |

## R9. The logging review is kept in step

**Decision**: in `docs/logging-review.md`:

- table 1: update the fields column (L13 `reason` → `error`, L15 `message_id` → `telegram_message_id`, L18 `status` →
  `http_status`; L19 lists `image_id` as always present), and remove the L20 row; leave the message, level, stack and
  event columns as they are;
- the counts line under table 1: 7 WARNING, 7 ERROR, 5 INFO (19 calls);
- rule BR2.1: drop `aws_request_id` and name the runtime-owned keys instead (`timestamp`, `level`, `logger`,
  `message`, `requestId`, `office`, `asctime`);
- rules BR4.1 and decision D5: mark them moved to U4 (a `Duration` alarm above 150 s);
- "The run.slow check" section: replace it with two sentences pointing at U4;
- "Edge cases": drop the formatter's `default=str` bullet and the two `run.slow` bullets; say the runtime, not the
  formatter, keeps a library's logger name;
- "What U2 must build": rewrite to this plan (no formatter fallback, no `run.slow`; the leak test reads records);
- "What U4 and U5 take from this": drop `run.slow`, add the `Duration` alarm, the counting rule for event-less lines
  (spec Key Entities) and the unverified `level` spelling;
- "Assumptions": the 150 s threshold now belongs to U4's alarm.

**Also**: `CLAUDE.md` points to `docs/handoff-u2-log-events.md` as U2's description. Point it at
`specs/001-u2-log-events/spec.md` instead.

## R10. The staging check

**Decision**: the pull request carries the Logs Insights query and steps in [quickstart.md](quickstart.md) section 4.
The owner runs it on the first staging run after deploy, before approving production (FR-020, SC-006). A failed check
means declining the approval and opening a revert pull request of the U2 merge, which puts staging back on the old
format through the pipeline.

**Rationale**: it is the only place the real lines exist, and production approval is already a manual step. The
ambiguous-stories filter is not exercised on staging (it needs an NWS rejection) and is accepted by inference from the
posts filter, which reads the same key in the same way.

## R11. Delivery

**Decision**: unchanged from the spec's FR-018. The tooling pull request (`856fb04`, `b96bb46` without `log_format.py`,
`5882d78`) goes first, and U2 starts fresh from the updated `main`. U2 does not bring `log_format.py` or the
`__init__.py` change, so the pre-split branch only supplies `specs/001-u2-log-events/`.
