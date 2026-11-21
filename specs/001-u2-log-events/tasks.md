---

description: "Task list for U2 Log Events (revised design: Lambda's JSON log format)"
---

# Tasks: U2 Log Events

**Input**: Design documents from `specs/001-u2-log-events/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/log-line.md](contracts/log-line.md), [quickstart.md](quickstart.md)

**Tests**: Required. The spec makes the checks requirements (FR-010 to FR-014, SC-001 to SC-007). **Inside each story
the code comes first, then its tests, in the same change.** That is the owner's rule for this unit. There is no bug fix
here, so nothing is test-first.

**Organization**: by user story, so each story can be checked on its own.

**Standing rules for every task** (from the spec, the plan and `CLAUDE.md`):

- Never change a log call's message text, its level, or whether it records a stack trace (FR-006). This unit adds no
  log message.
- Event names, levels, messages and stack traces come from `docs/logging-review.md` table 1. Field changes are those in
  [data-model.md](data-model.md), "Field changes U2 makes". Both win over a paraphrase here.
- Every event is a `str` constant written as the `"event"` value in a dict literal passed as `extra=`, with constant
  string keys and no `**` spread (FR-004, FR-012).
- Never pass `office`, `timestamp`, `level`, `logger`, `message`, `requestId`, `asctime` or a `LogRecord` attribute in
  `extra` (FR-009).
- Every test is offline: respx for HTTP, moto for AWS, nothing else.
- Fix type errors; never add `# ty: ignore`. No TODO or FIXME markers. Comments say why, not what.
- Do not commit. Commits, pushes and the pull request happen only when the owner says so.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1 to US4, as in spec.md)

---

## Phase 0: Branch Split (FR-018)

**Purpose**: get the tooling to `main` in its own pull request, then rebuild U2 on top of it. The commit map is in
[plan.md](plan.md), "Delivery". **Every commit, branch rename, push and pull request here waits for the owner's
go-ahead.**

- [x] S0 Save the revised design before any branch switch. The revised files in `specs/001-u2-log-events/` (spec, plan, research, data model, contract, quickstart, both checklists and this `tasks.md`) are uncommitted, and `checklists/platform-logging.md` is untracked. A branch switch would refuse, or stash them, and S3's checkout would restore the first design from `37274c5`. Ask the owner for a go-ahead to make one local commit on the current branch with `git add specs/001-u2-log-events` (plus the uncommitted deletions of the Spec Kit extension files, if the owner wants them in it). That branch keeps the pre-split work, and the commit is never pushed. (Done as `0ad00a9` on `u2-log-events`, which kept its name.) Without a yes, stop: do not stash, and do not copy the files elsewhere in place of the commit. Then confirm with `git status --short specs/` that nothing under `specs/` is left uncommitted
- [x] S1 Fetch `origin`, then create branch `spec-kit-setup` from `origin/main`. Cherry-pick `856fb04`, `b96bb46` and `5882d78` in that order. Cherry-pick `b96bb46` with `--no-commit`, then run `git rm -f src/weather_story_bot/log_format.py` (the file is staged, so a plain `git rm` refuses), then `git commit -C b96bb46` to keep the original message. Skip `09e89b5` (the `__init__.py` install), `1349a3d` (the removed Spec Kit extensions) and `37274c5` (the U2 specs). Resolve any conflict with the newer `main` on this branch. Then remove the Spec Kit extensions' leftovers if any came across (`.specify/extensions/`, `.specify/extensions.yml`, `.claude/skills/speckit-git-*`, `.claude/skills/speckit-bug-*`). Confirm that `git diff origin/main --stat` lists nothing under `src/`, `tests/` or `specs/`
- [x] S2 On `spec-kit-setup`, run `mise run lint ::: test ::: tftest ::: scan`. Then ask the owner before committing any fix, pushing the branch and opening its pull request. Wait until that pull request's `checks` job passes and it has merged (merged as #55)
- [x] S3 Fetch `origin`. Keep the old `u2-log-events` branch as it is. Create a fresh `001-u2-log-events` from `origin/main`. Run `git checkout u2-log-events -- specs/001-u2-log-events`, then confirm that `git status` shows only that directory. Confirm it is the revised design saved in S0: `checklists/platform-logging.md` exists, `spec.md` has FR-020 with the five SC-006 checks, and `plan.md` does not say `tasks.md` is stale. If any of these fails, stop and tell the owner
- [ ] S3a With the owner's go-ahead, commit only `specs/001-u2-log-events/` (never the scratch `pr-body.md`), push `001-u2-log-events` and open its pull request against `main` (FR-017). Wait until its `checks` job passes and it has merged. Then continue on a branch from the updated `origin/main`; the uncommitted `pr-body.md` carries across
- [ ] S4 After U2 has merged, ask the owner whether to delete the old `u2-log-events` branch. Never delete it without a yes

**Checkpoint**: `main` has the tooling and the spec documents. The code branch starts from it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: record the starting line on the rebuilt branch.

- [x] T001 On the rebuilt branch (after S3), before any edit, run `mise run lint ::: test ::: tftest ::: scan` and record the passing-test count in `specs/001-u2-log-events/pr-body.md` (created here as a scratch draft, finished in T031). No check may fail. If one does, stop and report it to the owner rather than fixing `main`'s code in this unit. Also confirm that `src/weather_story_bot/log_format.py` does not exist and that `src/weather_story_bot/__init__.py` matches `origin/main`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: shrink the bot's own logging to the office stamp and the level settings (research R2 to R4, R8). Every
story builds on this.

**⚠️ CRITICAL**: no user-story work starts until this phase is complete and the suite is green.

- [ ] T002 In `src/weather_story_bot/handler.py`: delete `_STANDARD_LOG_ATTRS`, `_aws_request_id`, `_invocation_context` and `class JsonFormatter`. Rename `_record_with_request_context` to `_record_with_office` and cut it to stamp `record.office` only while `_office` is set; update its docstring so it no longer mentions the request id. Keep `_office`, `_office_context` and the `logging.setLogRecordFactory(...)` call. Rewrite `configure_logging()` to only `logging.getLogger().setLevel(logging.INFO)` and set `httpx` and `httpcore` to `logging.WARNING`. Keep the existing comment on the caps (Telegram URLs hold the token). Add a comment saying the root level must equal `application_log_level` in `infra/lambda.tf`, and that the function adds no handler or formatter because the Lambda runtime's JSON formatter writes the lines (FR-002). Add a keyword parameter `aws_request_id: str | None = None` to `run()` and pass it to `services.history.record_run(...)` in place of `_aws_request_id.get()`. In `lambda_handler`, drop the `with _invocation_context(...)` block (dedent its body) and call `run(settings.offices, _services, aws_request_id=context.aws_request_id)`. Remove an import only if `ruff` reports it unused (F401): `json` stays, because `ProcessingError(f"... {json.dumps(summary)}")` still uses it, and `contextvars`, `Generator`, `contextmanager`, `datetime`, `UTC` and `Any` are all still used
- [ ] T003 In `src/weather_story_bot/history.py`, change the comment above `_log_failure` so it names `handler`'s office record factory (`_record_with_office`). Behaviour is unchanged
- [ ] T004 Update the tests listed in research R8, all in `tests/test_handler.py`: delete `test_json_formatter_includes_extra_fields`. In `test_lambda_handler_end_to_end`, delete the assertions that log records carry `aws_request_id` (the "Run complete" and "Telegram message sent" checks) and keep the `RUN#` history assertion. Delete `test_aws_request_id_does_not_leak_into_a_later_bare_run`: without the context variable there is nothing left to leak, and `test_posts_are_recorded_as_events_and_the_run_as_a_run_record` already covers a bare `run()`'s `RUN#` item. If that test does not assert that the bare run's `RUN#` item has no `aws_request_id`, add that assertion there, picking the item by its `run_at` (`NOW`). Change the comment above `LAMBDA_CONTEXT` so it says `lambda_handler` passes the id to the run history record, not that it reads it "for every log line". Leave `test_log_lines_carry_their_own_office_and_never_a_stale_one` unchanged
- [ ] T005 Run `uv run pytest` and confirm every test passes after T002 to T004

**Checkpoint**: no formatter and no request-id context in `src/`; office stamping unchanged; the suite is green.

---

## Phase 3: User Story 1 - Every warning and error says what kind it is (Priority: P1) 🎯 MVP

**Goal**: every WARNING and ERROR call, and the message-sent call, carries its event from table 1, with the field
renames (FR-004 to FR-008).

**Independent Test**: drive each failure path offline and read `caplog.records`. Every WARNING and ERROR record has
its decided `event`. The message-sent record has `telegram.message_sent`. No other INFO record has an `event`.

### Implementation for User Story 1

- [ ] T006 [P] [US1] In `src/weather_story_bot/handler.py`, add `"event"` to L01, L03 to L09 and L11 exactly as in `docs/logging-review.md` table 1: `office.lease_failed`, `nws.list_failed`, `office.process_failed`, `nws.image_download_failed`, `store.read_failed`, `office.lease_release_failed`, `nws.ambiguous_stories`, `story.process_failed`, `telegram.delete_failed`. Calls with no `extra` today get `extra={"event": "..."}`. In L07 and L11, change `"error": str(exc)` to `"error": repr(exc)`. Keep each message, level and `logger.exception`/`logger.error`/`logger.warning` choice. Change the comment above L08 ("matches this exact ERROR message") so it also names the event `nws.ambiguous_stories`. Leave L02, L10 and L12 without an event
- [ ] T007 [P] [US1] In `src/weather_story_bot/telegram.py`: L13 becomes `extra={"event": "telegram.photo_rejected", "error": repr(exc)}`, replacing `"reason": str(exc)`; L14 adds `"event": "telegram.message_sent"`; L15 renames `"message_id"` to `"telegram_message_id"` and gets no event; L16 adds `"event": "telegram.rate_limited"`. If a comment near L14 names the alarm's exact message, make it also name the event
- [ ] T008 [P] [US1] In `src/weather_story_bot/nws.py`: L17 adds `"event": "nws.retry_transport_error"` (its `error` is already `repr(exc)`); L18 adds `"event": "nws.retry_server_error"` and renames `"status"` to `"http_status"`
- [ ] T009 [P] [US1] In `src/weather_story_bot/history.py`, change `_log_failure(write: str, exc: Exception, **extra: str)` to `_log_failure(write: str, exc: Exception, image_id: str | None = None)`. Its call becomes `logger.warning("History write failed", extra={"event": "history.write_failed", "history_write": write, "error": repr(exc), "image_id": image_id})`. Update the three callers: `_log_failure("event", exc, image_id=image_id)`, `_log_failure("last_seen", exc, image_id=story.image_id)` and `_log_failure("run", exc)`
- [ ] T010 [US1] In `docs/logging-review.md` table 1, update only the fields column: L13 `reason` → `error`; L15 `message_id` → `telegram_message_id`; L18 `status` → `http_status`; L19 says `image_id` is always present (null on the `run` write). Delete the L20 row. Change the counts line to "7 WARNING, 7 ERROR, 5 INFO (19 calls)". Leave the message, level, stack and event columns as they are

### Tests for User Story 1

- [ ] T011 [P] [US1] In `tests/test_handler.py`, for each of L01, L03 to L09 and L11, drive the path (reuse the existing failure tests where one exists) and assert the record's `event` with the name written out, its level, and that `exc_info` is set exactly where table 1's Stack column says yes. Extend `test_ambiguous_stories_are_all_rejected_and_logged` to assert `event == "nws.ambiguous_stories"` on the real path (FR-014). Assert that L07 and L11 records have `error == repr(<the raised exception>)`. Assert that "Story posted", "Run complete" and "Office run already in progress" records have no `event` attribute
- [ ] T012 [P] [US1] In `tests/test_telegram.py`, first fix `test_delete_message_sends_ids_and_logs`, which reads `vars(deleted)["message_id"]` and breaks after T007: it should read `telegram_message_id`. Then assert on the real send path that "Telegram message sent" has `event == "telegram.message_sent"` (written out, FR-014) and no other INFO record has an `event`. Assert that L13 has `event == "telegram.photo_rejected"` and `error` equal to the repr of the photo error and no `reason` attribute; that L15 has `telegram_message_id` and no `message_id`; and that L16 has `event == "telegram.rate_limited"`. Assert `exc_info is None` on L13 to L16 (SC-003: none records a stack trace)
- [ ] T013 [P] [US1] In `tests/test_nws.py`, assert that L17 has `event == "nws.retry_transport_error"`, and that L18 has `event == "nws.retry_server_error"`, `http_status` set to the 5xx code and no `status` attribute. Assert `exc_info is None` on both
- [ ] T014 [P] [US1] In `tests/test_history.py`, for each of the three failing writes (`event`, `last_seen`, `run`), assert one WARNING "History write failed" with `event == "history.write_failed"`, the right `history_write`, `error == repr(<the exception>)`, `image_id` set on the first two and `None` on `run`, and `exc_info is None`

**Checkpoint**: every warning and error is named; U4 and U5 could filter on events from here.

---

## Phase 4: User Story 2 - Every log line is structured, by the platform (Priority: P1)

**Goal**: the function uses Lambda's JSON log format, pinned offline, and the bot's set-up only sets levels (FR-001 to
FR-003).

**Independent Test**: `mise run tftest` asserts the three logging settings; a unit test shows `configure_logging()`
adds no handler or formatter and is idempotent. The real lines are checked on staging (T028).

### Implementation for User Story 2

- [ ] T015 [P] [US2] In `infra/lambda.tf`, set the `logging_config` block to `log_format = "JSON"`, `application_log_level = "INFO"`, `system_log_level = "INFO"`, and keep `log_group = aws_cloudwatch_log_group.lambda.name`. Replace the comment "The handler formats its own JSON log lines." with one saying the runtime writes each record as a JSON line, that `application_log_level` must equal the root level set in `configure_logging()` (FR-002), and that the system level keeps the `REPORT` lines. Change nothing else in `infra/` (FR-019)

### Tests for User Story 2

- [ ] T016 [US2] In `infra/tests/lambda.tftest.hcl`, add a `run` block, for example `run "lambda_writes_json_logs_at_info"`, with one `assert` each for `aws_lambda_function.bot.logging_config[0].log_format == "JSON"`, `.application_log_level == "INFO"` and `.system_log_level == "INFO"`, each with an error message naming the setting. Run `mise run tftest` and confirm it passes
- [ ] T017 [US2] (after T011, which edits the same file) In `tests/test_handler.py`, add a test that saves the root logger's handlers (as a list copy) and the formatter of each, plus the root, `httpx` and `httpcore` levels, and restores them in a `finally`. It should call `configure_logging()` twice and assert the following: the root handler list and each handler's formatter are unchanged (no handler added, no formatter set); the root level is `logging.INFO`; and the `httpx` and `httpcore` levels are `logging.WARNING`

**Checkpoint**: the infrastructure is pinned to JSON at INFO; the bot no longer touches handlers or formatters.

---

## Phase 5: User Story 3 - The Telegram token never reaches the logs (Priority: P1)

**Goal**: prove that no handled Telegram failure puts the token, the API host, the caption or the image bytes into a
log record, and that the token-bearing request ran (FR-010, FR-011, research R7).

**Independent Test**: `uv run pytest tests/test_log_secrets.py -v` passes, and each test asserts its respx route was
called.

### Tests for User Story 3

- [ ] T018 [US3] Create `tests/test_log_secrets.py`. The failures must be driven through `handler.run(...)`, not through `TelegramClient` alone. On most failure paths `telegram.py` raises without logging, and the records that carry a Telegram exception are the handler's L09 ("Failed to process story", logged with a stack trace) and L11 ("Telegram delete failed", whose `error` is `repr(exc)`). The file contains:
  - a canary token constant `TOKEN = "123456:LEAK-CANARY"`;
  - `services` and `api` fixtures modelled on those in `tests/test_handler.py` (lines 43 to 71), with the canary token in the `TelegramClient` and in the respx URLs, and `sleep=lambda _: None` on both clients so the 429 path does not really sleep;
  - a `production_logging` fixture that saves the root, `httpx` and `httpcore` levels, calls `handler.configure_logging()`, yields, and restores the three levels. Tests take it *after* `caplog` in their parameters and do not call `caplog.set_level`, so the levels under test are the ones production sets, and `caplog`'s own teardown cannot leave a changed level behind;
  - a helper `assert_no_secret(records, *, captions, images)`. It first asserts that `records` is not empty. Then, for each record, it checks `record.getMessage()`, `repr()` of every value in `vars(record)`, and the formatted stack trace (`logging.Formatter().formatException(record.exc_info)` when set). None of them may contain the token, `api.telegram.org`, any of the story captions that were sent, or any image's bytes (or their `repr`). Take the captions and images from the fixture stories (`mkx_payload`), whose values are long and distinctive, never short stand-ins such as `"cap"` or `b"x"`
- [ ] T019 [US3] In `tests/test_log_secrets.py`, write one test per handled path. Each drives `handler.run((MKX,), services, now=NOW)` with respx routes on the token-bearing URLs for that path, then asserts in this order: the route was called (`route.called`); the expected handler or telegram record exists; and `assert_no_secret(caplog.records, ...)` passes. The paths are:
  - a transport error on `sendPhoto` (L09 exists, with `exc_info` set);
  - a 429 then success on `sendPhoto` (L16 exists);
  - a photo rejected, then sent as a document (L13 exists; the `sendDocument` route is called);
  - an unexpected result with no `message_id` (L09 with `exc_info`);
  - an HTTP error status on `sendPhoto` (L09 with `exc_info`);
  - an HTTP error status on `sendDocument`, reached by first rejecting the photo (L13 then L09 with `exc_info`);
  - an HTTP error status on `deleteMessage` during an update (L11, whose `error` field is checked). Reach it as `test_failed_delete_keeps_the_new_post` in `tests/test_handler.py` does: revise a stored story so the run posts and then deletes. That existing test's `TOKEN not in caplog.text` check stays as it is

  Every test asserts at least one record with `exc_info` wherever L09 applies, so the stack-trace check is never vacuous
- [ ] T020 [US3] In `tests/test_log_secrets.py`, add `test_http_client_loggers_are_capped_at_warning`: through the `production_logging` fixture, assert `logging.getLogger("httpx").level == logging.WARNING` and the same for `httpcore` (FR-011)

**Checkpoint**: the token-leak proof covers every handled Telegram failure and cannot pass vacuously.

---

## Phase 6: User Story 4 - Code and review cannot drift apart unnoticed (Priority: P2)

**Goal**: one test file fails when a call and the contract disagree (FR-012, FR-013, research R5 and R6).

**Independent Test**: `uv run pytest tests/test_logging_review.py -v` passes on `src/`, and each bad-sample test shows
its rule failing with the module, line and message named.

### Tests for User Story 4 (all in `tests/test_logging_review.py`, so run in order)

- [ ] T021 [US4] Rewrite `_log_calls()` in `tests/test_logging_review.py` as `_log_calls_in(source: str, module: str)`, plus a wrapper that walks `src/weather_story_bot/*.py`. For each `logger.<debug|info|warning|error|exception|critical>(...)` call, it returns the module, line, level (`exception` counts as ERROR), message, and either the `extra` dict literal's keys and its `"event"` value, or a marker that `extra` is not a dict literal. It returns a separate list of unreadable calls:
  - a non-`str`-constant message;
  - `logger.log(...)` or `logger.warn(...)`;
  - a module-level logging call, `logging.<debug|info|warning|warn|error|exception|critical|log>(...)`. This does not cover `logging.getLogger`, `logging.getLogRecordFactory`, `logging.setLogRecordFactory` or other non-logging functions, which `handler.py` uses legitimately;
  - a `.<debug|info|warning|warn|error|exception|critical|log>(...)` call whose receiver is not the plain name `logger` (for example `logging.getLogger(x).warning(...)`);
  - an `extra` dict with a non-constant key or a `**` spread;
  - a non-literal `extra` on a WARNING, ERROR or CRITICAL call, or on "Telegram message sent".

  Update the existing four tests to use it. Remove `_NEW` and the `"(new)"` handling from `_inventory()` and `test_every_log_message_in_src_is_in_the_review`, since T010 removed the only `(new)` row: every table row must now match a call
- [ ] T022 [US4] Write the rules as one reusable helper, `_problems(calls, unreadable) -> list[str]`, which returns one message per broken rule, each naming the module, line and message. The rules are:
  - every WARNING, ERROR and CRITICAL call (`exception` counts as ERROR) and the "Telegram message sent" call has `"event"` with a `str` constant value (not a name, an f-string or another expression);
  - no other call has an `"event"` key;
  - every unreadable call is reported;
  - no readable `extra` key is forbidden. Forbidden means the keys of `vars(logging.makeLogRecord({}))` plus `message`, `asctime`, `timestamp`, `level`, `logger`, `requestId` and `office`. Every key must also match `^[a-z][a-z0-9_]*$`.

  Add a test that `_problems(...)` over `src/` returns an empty list
- [ ] T023 [US4] Replace `_AREAS` and `_EVENT` with `_EVENT = re.compile(r"^(nws|telegram|office|story|store|history|run)\.[a-z_]+$")`. Write a helper `_event_set_diff(code: set[str], table: set[str]) -> str`, which returns an empty string when the sets are equal and otherwise names the events missing from each side. Add a test that it returns an empty string for the event constants in `src/` against the events in table 1. Keep `test_event_names_are_well_formed_and_unique` on the new pattern
- [ ] T024 [US4] Add one bad-sample test per rule. Each passes a short source string to `_log_calls_in`, then to `_problems`, and asserts that the expected message is reported. The samples are:
  - a warning without an event;
  - "Telegram message sent" without its event;
  - an INFO call (not message-sent) with an event;
  - an `"event"` value that is a name, and one that is an f-string;
  - a `logger.exception(...)` without an event, reported as ERROR;
  - a forbidden key (`office`);
  - a camelCase key;
  - a non-constant dict key;
  - a `**` spread in a WARNING `extra`;
  - a non-literal `extra=some_dict` on a WARNING;
  - an f-string message;
  - `logging.warning(...)`;
  - `logger.log(...)`;
  - `logging.getLogger("x").warning(...)`.

  Add one sample that must report nothing, `logging.getLogger(__name__)` with a well-formed warning, to show the rule is not too broad. Add one more test that passes two event sets differing by one name to `_event_set_diff`, and asserts that the name appears in the result

**Checkpoint**: the contract is locked; any drift between code and table 1 fails the suite.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: the review and pointers in step, the gates, the pull request material, and the staging check.

- [ ] T025 [P] Update the rest of `docs/logging-review.md` as research R9 lists. The intro paragraph that says what `tests/test_logging_review.py` fails on should list the new rules: a missing or misplaced event, a forbidden or non-snake_case field, an unreadable call, and an event set that differs from table 1. Rule BR2.1 names the runtime-owned keys (`timestamp`, `level`, `logger`, `message`, `requestId`, `office`, `asctime`) instead of `aws_request_id`. BR4.1 and D5 are marked as moved to U4 (a `Duration` alarm above 150 s). "The run.slow check (L20)" is replaced by two sentences pointing at U4. In "Edge cases", drop the `default=str` bullet and both `run.slow` bullets, and say the runtime keeps a library's logger name. "The secrets check" row "Is there a test?" points at `tests/test_log_secrets.py`. Rewrite "What U2 must build" to match this unit: events and field changes, the leak test reading records, the drift check, and the JSON format. In "What U4 and U5 take from this", drop `run.slow` and add the `Duration` alarm, the rule that only lines with an `event` or a library logger are counted, and that the `WARNING` spelling must be confirmed first. In "Assumptions", the 150 s threshold belongs to U4's alarm. Table 1 was already done in T010
- [ ] T026 [P] Check `specs/001-u2-log-events/contracts/log-line.md` against `docs/logging-review.md` table 1 (15 events, levels, messages) and correct the catalogue if they differ
- [ ] T027 [P] In `CLAUDE.md`, change the sentence that points U2 at `docs/handoff-u2-log-events.md` so it points at `specs/001-u2-log-events/spec.md` (research R9)
- [ ] T028 Run `mise run format`, then `mise run lint ::: test ::: tftest ::: scan`. Fix every finding at its source
- [ ] T029 Run `mise run coverage` and confirm project line coverage is at least 80% (SC-007). Run `grep -rn "JsonFormatter\|_aws_request_id\|_invocation_context\|log_format" src/` and confirm it prints nothing (SC-005). Then run `git diff origin/main -- src | grep -E '^[-+].*logger\.'` and read every pair. Each removed `logger.<level>("<message>"` line must come back with the same level and message, and no `logger.exception` may become `logger.error` or the reverse (SC-003)
- [ ] T030 Run [quickstart.md](quickstart.md) section 3 (SC-008). The baseline must not use a branch switch: the U2 edits are uncommitted and would carry across, and the local `main` may be behind. Instead:
  1. Run `git fetch origin`, then `git worktree add /private/tmp/u2-baseline origin/main`.
  2. Run `uv run weather-story-bot --dry-run` inside that worktree, and straight away in this checkout.
  3. Compare the two stdouts. Repeat the pair once if they differ.
  4. Remove the worktree with `git worktree remove /private/tmp/u2-baseline`.
- [ ] T031 Draft the pull request body in `specs/001-u2-log-events/pr-body.md` (not committed unless the owner wants it). Cover: the switch to Lambda's JSON format and what was deleted; that message text, levels and stack-trace behaviour are unchanged, so no alarm changes; that `run.slow` moved to U4 as a `Duration` alarm; the field renames; the accepted, unverified assumptions from the spec (level spelling, record-factory attribute, import-time handler); links to the tooling and spec pull requests; and the whole of [quickstart.md](quickstart.md) section 4, with the query, the five pass conditions and the revert path. Then stop and ask the owner before any commit, push or `gh pr create`
- [ ] T032 After the pull request merges and the pipeline has deployed staging, the owner runs the staging check in [quickstart.md](quickstart.md) section 4 before approving production (FR-020, SC-006). The agent may run the query with the `readonly` profile if asked, but never approves production, never runs `mise run start staging`, and reads the pipeline's job states with `gh run view <id> --json jobs`, never `gh run watch`. A failed check means declining the approval and opening a revert pull request, with the owner's go-ahead

---

## Dependencies & Execution Order

### Phase Dependencies

- **Branch split (Phase 0)**: none. S0 to S3a run in order. The tooling pull request must merge before S3, the spec pull
  request (S3a) must merge before Phase 2, and S4 waits until U2 has merged.
- **Setup (Phase 1)**: after S3.
- **Foundational (Phase 2)**: after Setup. Blocks every story, because T002 changes `handler.py`'s logging and `run()`.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after Foundational; independent of US1. T015 and T016 touch only `infra/`.
- **US3 (Phase 5)**: after Foundational. Run it again after US1, because T007 changes what L13 logs.
- **US4 (Phase 6)**: after US1, because its set-equality and event rules need every event in the code and T010's
  table.
- **Polish (Phase 7)**: after all stories. T032 waits for the merge and the staging deploy.

### Within Each User Story

- Code task, then its tests, in the same change.
- Tasks that touch the same file run in ID order: `handler.py` T002 → T006; `history.py` T003 → T009;
  `tests/test_handler.py` T004 → T011 → T017; `docs/logging-review.md` T010 → T025.

### Parallel Opportunities

- In US1, T006 to T009 touch four source files and run in parallel, and so do T011 to T014, in four test files.
- After Foundational, US1, US2 and US3 can proceed in parallel. US2 touches `infra/`, and US3 touches a new test file.
  T017 waits for T011, since both edit `tests/test_handler.py`.
- T025, T026 and T027 run in parallel.

---

## Parallel Example: User Story 1

```bash
# The four call-site edits together:
Task: "T006 handler.py events L01, L03-L09, L11"
Task: "T007 telegram.py L13, L14, L15, L16"
Task: "T008 nws.py L17, L18"
Task: "T009 history.py L19 as a plain literal"

# Then the four test files together:
Task: "T011 tests/test_handler.py per-call events and the ambiguous signal"
Task: "T012 tests/test_telegram.py L13/L15/L16 and the sent signal"
Task: "T013 tests/test_nws.py L17/L18"
Task: "T014 tests/test_history.py L19"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 0: the tooling merged on its own, then the spec documents, and U2 rebuilt on top of them.
2. Phase 1 and Phase 2: the formatter and request-id context gone, the suite green.
3. Phase 3 (US1): every warning and error named.
4. **Stop and validate**: run the four US1 test modules.

### Incremental Delivery

1. Foundation, then US1 (events), the MVP.
2. US2 (JSON format pinned) and US3 (token proof): the P1 safety net.
3. US4 (drift check) last, because it locks in everything above.
4. Polish: docs, gates, the pull request draft, then the staging check before production. **The unit's code ships as one pull
   request**, after the tooling and spec pull requests have merged; these steps are checkpoints, not separate merges.

---

## Notes

- [P] tasks touch different files and depend on no unfinished task.
- Every task ends with its tests green before the next same-file task starts.
- Nothing is committed during these tasks; the owner decides when.
- If a check passes without exercising anything (a route never called, a set compared with itself), treat it as a
  failure and fix the test.
