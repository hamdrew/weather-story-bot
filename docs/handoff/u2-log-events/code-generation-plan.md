# Code Generation Plan: u2-log-events

## Summary

- Builds: a `log_format.py` module (JSON formatter that never raises, request-context scopes), an `event` on every WARNING, ERROR and the message-sent line, the `run.slow` warning, the drift tests and the token-leak test.
- Touches: new `src/weather_story_bot/log_format.py`; edits to `handler.py`, `telegram.py`, `nws.py`, `history.py`, `docs/logging-review.md`; new `tests/test_log_format.py` and `tests/test_log_secrets.py`; edits to `tests/test_logging_review.py`, `test_handler.py`, `test_telegram.py`, `test_nws.py`, `test_history.py`. No Terraform.
- Tests: about 60 test cases in about 40 test functions (Standard strategy), all offline, plus a check that `log_format.py` has no uncovered line or branch.

## Sources

- `construction/u2-log-events/functional-design/functional-spec.md`, `rules.md` (BR1.1 to BR6.4) and `entities.md` [FR2.1, FR2.2, FR2.3, FR2.4, FR5.2, FR6.3]
- `construction/u2-log-events/nfr-requirements/` (`tech-stack-decisions.md`, `security-requirements.md`) and `nfr-design/` (`security-design.md`, `logical-components.md`) [NFR4, NFR5, NFR6]
- `construction/u2-log-events/infrastructure-design/cicd-pipeline.md` (the unit is code inside the existing Lambda; no new job)
- `inception/units-generation/unit-of-work.md` (U2) and `inception/requirements-analysis/requirements.md`
- `docs/logging-review.md` (table 1 is the source of the event names)
- A read, for this plan, of `handler.py`, `telegram.py`, `nws.py`, the log call in `history.py`, `OfficeLease.release` in `state.py`, `tests/test_logging_review.py`, and the tests that read log fields (`test_handler.py`, `test_telegram.py`, `test_history.py`); `mise.toml` and `pyproject.toml` for the test commands

No user stories exist for this intent, so the trace is by requirement (`unit-of-work-story-map.md`).

## Decision for the owner (OQ1): where the JSON formatter is installed

**Plainly: the design as written cannot meet FR2.4 as worded.** FR2.4 says any WARNING or above from any Python
logger in the function is a record the filters can read. The Lambda runtime installs its own plain-text handler
before it imports our code, and today the JSON formatter goes on only when the first invocation calls
`configure_logging()`. A record written while modules are imported, before that call, is plain text and no filter reads
it as a warning. Nothing in this repository logs at import; the gap would be a third-party library logging a WARNING
as it is imported, which is possible and rare.

| Option | What it does | FR2.4 | Cost |
|--------|--------------|-------|------|
| **A** | Nothing extra. The formatter goes on at the first `configure_logging()` of each invocation. | Not met for import-time records; the pull request says so. | None. |
| **C2 (this plan's default)** | A small idempotent `install_json_format()` in `log_format.py`; `configure_logging` calls it; `__init__.py` imports only `log_format` and calls it first, before `httpx` and `boto3` are imported. | Met, including records written while those libraries are imported. | Importing the package now changes the root logger: it affects pytest's log capture and the output of `uv run weather-story-bot --dry-run` (its warnings would print as JSON). **Not yet checked**, so Step 2 is a spike. |

Step 2 is the spike. If pytest and the dry run are unaffected, Step 3 builds C2. If not, the plan falls back to A and
the pull request says FR2.4 is met from the first invocation only. **Approving this plan approves C2-after-the-spike
with A as the fallback.** To choose A now, ask for changes and say so; Step 2 and the `__init__.py` part of Step 3 drop
out. Nothing else in the plan depends on the choice.

## Working notes

- **Branch**: one short-lived branch for this unit, made off `main` before the first source edit (a local branch; nothing is committed in this stage without asking you first).
- **Order of work** follows the Testing Contract: new code is written first, then its tests, in the same change. This unit has no bug fix, so nothing here is test-first.
- **Message text, levels and stack traces never change** (BR2.4), so today's three message-based alarm filters keep matching until U4. The only new message is "Run was slow".
- **Quality targets are inputs**: 80% line coverage for the project, and no uncovered line or branch in `log_format.py` (NFR4.4). Neither is lowered to make a step pass.
- **No TODO or FIXME markers**; comments say why, not what.

## Steps

### Part A: Ground and design check

- [ ] **Step 1: Verify the test runner and record the unit-scoped commands.** `uv run pytest` is the existing runner (`mise run test`; `pyproject.toml` has `testpaths = ["tests"]`, `-ra --strict-markers`; coverage stays out of `addopts`). Run the unit's test modules once on the unchanged tree to see them green, run the coverage command of `unit-test-instructions.md` on a module that exists to prove its shape, and create the working branch. No runner or dependency is added (NFR1.1, NFR4.1). *Requirements: NFR4.1, NFR4.4.*
- [ ] **Step 2: Spike the C2 install point (OQ1), throw-away.** In a scratch change, add `install_json_format()` to a draft `log_format.py`, make `__init__.py` import it, and check: (a) the full `uv run pytest` is unchanged and green, (b) `caplog` still captures records and `caplog.text` assertions still hold, (c) `uv run weather-story-bot --dry-run` still prints the same decisions and captions, with only warnings changing form, (d) importing the package twice adds one root handler, not two. Record the result in the stage diary and say it in one line to you. Pass: Step 3 builds C2. Fail on any of a to d: Step 3 builds A and the spike is reverted. *Requirements: FR2.4; NFR6.4.*

### Part B: The library (new code first)

- [ ] **Step 3: Write `src/weather_story_bot/log_format.py` (LogFormatter, LC1).** Contains:
  - `JsonFormatter` with the three tiers: full line (BR1.1, BR1.2: base fields, then every non-standard record attribute, then `time`, `level`, `logger`, `message` written again so an extra cannot replace them, then `exception`); fallback line (BR1.3, BR1.4: `time`, `level`, `logger`, `message` or the raw message text, `formatter_error` as the exception class name, and `event`, `office`, `aws_request_id` only when plain strings); last-resort line holding only `level` and `logger`. No exception leaves `format()`. A value that is not JSON-serialisable is written with `str()` (`default=str`); the line holds no raw newline.
  - The request context: the two `ContextVar`s, the record factory chained to the one already installed and installed at import (BR1.7), and the two scopes `invocation_context(aws_request_id)` and `office_context(office_id)` that restore the previous value on exit, also on an exception. Public names: `JsonFormatter`, `invocation_context`, `office_context`, `current_aws_request_id()`.
  - **C2 only** (Step 2 passed): `install_json_format()`, idempotent, adds a root handler when none exists and sets the JSON formatter on every root handler; it touches no level and no cap. `__init__.py` imports only `log_format` and calls it as its first statement.
  - Types are plain and `ty check` clean (`Generator[None]`, `ContextVar[str | None]`); no `# ty: ignore`. *Rules: BR1.1 to BR1.5, BR1.7. Requirements: FR2.3, FR2.4, FR5.2; NFR5.4 to NFR5.6; ADR-005.*
- [ ] **Step 4: Rewire `handler.py` (LambdaHandler, LC2).** Remove `_STANDARD_LOG_ATTRS`, the context variables, the record factory, `_invocation_context`, `_office_context` and `JsonFormatter`; import them from `log_format`; `run()` uses `office_context` and `current_aws_request_id()`. Keep `configure_logging()` in `handler.py` (it calls `install_json_format()` under C2, or sets the formatter itself under A) with the root level INFO and the `httpx` and `httpcore` caps at WARNING (BR1.6). Add the slow-run check: a module-level `_monotonic = time.monotonic` read as the first statement of `lambda_handler`, the constant `SLOW_RUN_SECONDS = 150`, and, after `run()` returns, a WARNING "Run was slow" with `event` `run.slow`, `duration_seconds` rounded to one decimal and `threshold_seconds`, written before "Run complete" and only when the unrounded duration is more than 150 (BR4.1, BR4.2). If `run()` raises, no slow-run line is written. *Rules: BR1.6, BR4.1, BR4.2. Requirements: FR2.1, FR6.3; NFR4.3.*
- [ ] **Step 5: Call-site events and field changes (L01 to L19, LC3).** Add the event as a string literal in the `extra` dict of every WARNING, ERROR and exception call, and of the message-sent line, with the names and field changes of the functional spec's call-site table:
  - `handler.py`: L01 `office.lease_failed`, L03 `nws.list_failed`, L04 `office.process_failed`, L05 `nws.image_download_failed` (keeps `title`), L06 `store.read_failed`, L07 `office.lease_release_failed` with `error` = `repr(exc)`, L08 `nws.ambiguous_stories` (keeps `stories`), L09 `story.process_failed` (keeps `title`), L11 `telegram.delete_failed` with `error` = `repr(exc)`. The comment above L08 now says the event is the contract and the message text is kept until U4 moves the filter.
  - `telegram.py`: L13 `telegram.photo_rejected` with `reason` replaced by `error` = `repr(exc)`; L14 `telegram.message_sent` (the one INFO line with an event); L15 gets no event and `message_id` becomes `telegram_message_id`; L16 `telegram.rate_limited`. The comment above L14 is updated the same way.
  - `nws.py`: L17 `nws.retry_transport_error` (already `repr`); L18 `nws.retry_server_error` with `status` renamed `http_status`.
  - `history.py`: L19 `history.write_failed` in the one `_log_failure` call, `error` = `repr(exc)`; `history_write` stays.
  - L02, L10 and L12 are untouched. L07's exception is read from the code: `OfficeLease.release` re-raises a botocore `ClientError` that is not a condition failure, and the caller catches `BotoCoreError` and `ClientError`, so its `repr` holds the operation name and the AWS error text (closes OQ2 of the security design; recorded in `code-summary.md`).
  - Message text, levels and stack traces do not change. *Rules: BR2.1 to BR2.4, BR3.1, BR3.2. Requirements: FR2.1, FR2.2, FR2.3, FR6.3; NFR5.7.*
- [ ] **Step 6: Update `docs/logging-review.md`.** Take the " (new)" mark off L20's message now that the call exists, and bring the "Fields" cells of L13, L15, L18 in step with the code (the column heading "Fields today" becomes "Fields"). Event names in table 1 are unchanged. *Rules: BR6.3. Requirements: FR6.3; NFR6.1.*

### Part C: Tests (written after the code they test)

- [ ] **Step 7: `tests/test_log_format.py` (LC4, about 14 test functions).** Moves the `JsonFormatter` test out of `test_handler.py`. Cases: base fields and an ISO UTC `time`; extras at the top level with `event` (BR6.4); a third-party-named logger at WARNING has `level` and `logger` and no `event` (BR1.5, BR6.4); an extra named `time`, `level`, `logger` or `exception` cannot replace the formatter's value (BR1.2, parametrised); `exception` appears when the record has `exc_info`; a non-serialisable value is written with `str()`; a message with a newline stays on one line; a circular structure gives the fallback line that parses, with `formatter_error` `ValueError` and `event`, `office`, `aws_request_id` kept as plain strings and a non-string `event` dropped (BR1.3, BR1.4); a message whose arguments do not format gives the raw text; a stack trace that cannot be formatted gives the fallback; a record whose `msg` raises from `str()` even in the fallback gives the last-resort line with only `level` and `logger`; each scope sets, restores on return and restores on an exception (BR1.7); the record factory chains to the previous factory and a bare record has neither `office` nor `aws_request_id`; **C2 only**: `install_json_format()` is idempotent and importing the package installs the formatter. *Rules: BR1.1 to BR1.5, BR1.7, BR6.4. Requirements: FR2.4; NFR5.4 to NFR5.6.*
- [ ] **Step 8: Event and field tests beside the code (LC5, in the existing modules).** `test_handler.py`: one parametrised test that each of L01, L03 to L09 and L11 is written with its event and that the message text is unchanged; L07 and L11 `error` is the `repr`; the slow-run tests (Step 9). `test_telegram.py`: L13 `error` replaces `reason`; L16 event; L15 reads `telegram_message_id` (the existing assertion on `message_id` at line 219 changes); the message-sent test also asserts `telegram.message_sent`, written out in the test (BR6.2). `test_nws.py`: L17 and L18 events and `http_status`. `test_history.py`: L19 event, `error` as `repr` (the existing `"ResourceNotFoundException" in record["error"]` check stays true). `test_handler.py`'s ambiguous-listing test also asserts an ERROR record with `nws.ambiguous_stories`, written out in the test (BR6.2). *Rules: BR2.1 to BR2.4, BR3.1, BR3.2, BR6.2.*
- [ ] **Step 9: Slow-run tests in `test_handler.py`.** The test replaces `handler._monotonic` (not `time.monotonic`): a run over 150 logs one `run.slow` with `duration_seconds` and `threshold_seconds`; exactly 150 and below log nothing; a duration of 150.04 is logged and reads `150.0`; with a failed count the order is `run.slow`, "Run complete", then `ProcessingError`; if `run()` raises there is no `run.slow` line. *Rules: BR4.1, BR4.2. Requirements: FR2.1.*
- [ ] **Step 10: The Python drift test in `tests/test_logging_review.py`.** The `ast` walk (no import of the package) is factored into a function that returns problems for a piece of source, so it is itself tested against bad snippets. Checks: every `warning`, `error`, `exception` and `critical` call, and the message-sent call, has an `extra` dict literal with a string-constant `event` key, else the failure names module, line and message and says to write the literal (BR6.1); no INFO call other than the message-sent line passes an `event` (BR2.3); no `extra` key is a `LogRecord` attribute, `time`, `level`, `logger`, `message`, `exception`, `office` or `aws_request_id`, and every key is lowercase snake_case (BR3.3); the set of events in `src/` equals the set in table 1, and the failure names the difference (BR6.3); no row stays marked "(new)" once its call exists. *Rules: BR2.1, BR2.3, BR3.3, BR6.1, BR6.3. Requirements: FR5.2.*
- [ ] **Step 11: The token-leak test `tests/test_log_secrets.py` (LC5).** It calls `configure_logging()` first so `httpx` and `httpcore` records are captured under the cap production uses, then drives every handled Telegram failure with a recognizable token, caption and image bytes: a transport error; a 429 then success; a photo rejected then sent as a document; an unexpected result; a delete that fails (through the handler); an HTTP error status on `sendPhoto`, `sendDocument` and `deleteMessage`. Every captured record goes through the shipped `JsonFormatter`, and no line holds the token, `api.telegram.org`, the caption or the image bytes. A control assertion shows the mocked route for the token-bearing URL was called (BR5.2). A separate test reads the `httpx` and `httpcore` levels back as WARNING (BR5.3). For L17 and L19 the recognizable string sits on the request side (the NWS `User-Agent`, a DynamoDB item value) and the test checks it never reaches the `error` field. A small local fixture builds the moto-backed services, because the existing ones live in `test_handler.py`. *Rules: BR5.1 to BR5.3. Requirements: FR6.3; NFR5.1, NFR5.2, NFR5.3.*

### Part D: Verify and document

- [ ] **Step 12: Lint, types, and the unit's tests.** `mise run format` then `mise run lint` (ruff, `ty check`, `terraform fmt`, workflow lint); fix a type error rather than silencing it. Run the unit-scoped commands of `unit-test-instructions.md`, then `mise run test` for the whole suite. *Requirements: NFR4.1, NFR5.7.*
- [ ] **Step 13: Coverage.** Run the `log_format.py` coverage command of `unit-test-instructions.md`: no missing line and no missing branch. Then `mise run coverage` for the project: 80% line coverage or better, with the `log_format.py` line quoted for the pull request body. A target that is not met is surfaced, never lowered. *Requirements: NFR4.4.*
- [ ] **Step 14: Stage files.** Write `code-summary.md` (files changed, decisions including the OQ1 result and L07's exception, deviations, tests not run here and why), `source-manifest.json` (every source path this unit created or changed) and `traceability.json` through the sensor command. *Requirements: all.*

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "Bug fixes start with a failing test that reproduces the bug, then the fix; new code is written first, then its tests, in the same change.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "- **Methodology**: custom\n- **Methodology evidence**: Affirmed at the interview (Q2): test-first for bug fixes, test-after\n  for new code. The history cannot show the order (tests land in the same squashed commit as the\n  code in every behaviour change); its one explicit signal is a review finding \"fixed test-first\"\n  in #27, which fits the bug-fix half of the rule.\n- **Ordering**: Bug fixes start with a failing test that reproduces the bug, then the fix; new code\n  is written first, then its tests, in the same change.\n- **Coverage floor**: 80% line coverage, checked in CI by a separate coverage step. That CI step is\n  later work and not part of the current change; until it exists, the floor is checked with\n  `mise run coverage`. At affirmation the suite measured 99% branch coverage of\n  `src/weather_story_bot/` (296 tests).\n- **Coverage stays opt-in locally**: `--cov` is never in pytest `addopts`, because it breaks\n  debugger breakpoints; coverage runs through its own task or CI step.\n- **Offline suites**: every suite runs without network or credentials. respx mocks HTTP, moto mocks\n  AWS, an autouse fixture replaces any real AWS or Telegram credentials, and Terraform tests use\n  `mock_provider \"aws\"` with `-backend=false`.\n- **Test types**: Python unit and component tests in `tests/` (pytest), one test module per source\n  module (`tests/test_<module>.py`), plus tests that run the bash tasks for real with fake\n  `terraform` and `aws` on `PATH`; Terraform tests in `infra/tests/` and `infra/bootstrap/tests/`.\n  There is no live integration suite: live behaviour is checked on staging (see Deployment).\n- **Test data**: real captured NWS listings in `tests/fixtures/`, loaded through `office_payload` /\n  `office_stories`, plus the `make_story(**overrides)` builder.\n- **Tooling**: `mise run test` (pytest, `-ra --strict-markers`), `mise run tftest`,\n  `mise run coverage` (pytest-cov, branch coverage, terminal and HTML report).\n- **CI**: the `checks` job runs `lint`, `test`, `tftest` and `scan` on every pull request and every\n  push to `main`, and must pass before merge."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - Bug fixes start with a failing test that reproduces the bug, then the fix; new code is written first, then its tests, in the same change.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:f9e88e854eeb6103790c56799563833a0b9d3ef436070b8ad352f04757086cd7",
  "contract_sha256": "sha256:94ddaaa54604ce1f0e6fde36d5d40f5fc90cb099cd0232c1dd12e9b12ec0e67d"
}
```

## Traceability: requirements to plan steps

| Requirement | Plan steps |
|-------------|-----------|
| FR2.1 every WARNING is a kind | 4, 5, 8, 9, 10 |
| FR2.2 every ERROR is a kind | 5, 8, 10 |
| FR2.3 a kind does not depend on wording | 3, 5, 8, 10 |
| FR2.4 any logger in the function | 2, 3, 4, 7 (limit and choice: OQ1) |
| FR5.2 Python half of the drift test | 3, 7, 8, 10 |
| FR6.3 the review's code changes | 3 to 6, 8, 9, 11 |
| NFR4 (offline tests, 80% line coverage) | 1, 12, 13 |
| NFR5 (token never logged; line integrity; what is posted does not change) | 3, 5, 7, 11 |
| NFR6 (one revertible slice, no Terraform) | 6, 14 |

| Rule | Step | Rule | Step |
|------|------|------|------|
| BR1.1 to BR1.5 | 3, 7 | BR4.1, BR4.2 | 4, 9 |
| BR1.6 | 4 | BR5.1 to BR5.3 | 11 |
| BR1.7 | 3, 7 | BR6.1, BR3.3, BR2.3 | 10 |
| BR2.1 to BR2.4 | 5, 8, 10 | BR6.2 | 8 |
| BR3.1, BR3.2 | 5, 8 | BR6.3 | 6, 10 |
| | | BR6.4 | 7 |

## Assumptions & Open Questions

- **A1**: `uv run pytest <paths>` is the unit-scoped form of `mise run test` (`uv run pytest`), and `--cov=weather_story_bot.log_format` limits coverage to the one module. *Reason: read in `mise.toml` and `pyproject.toml`; the commands are run in Step 1 before they are relied on.*
- **A2**: NFR5 review point 6 ("cover L17 and L19 so text from outside the bot cannot reach `error`") is read as: a recognizable string on the request side (the NWS `User-Agent`, a DynamoDB item value) never appears in the `error` field. It is not read as a search for the exception's own text, which `repr(exc)` holds by design. *Reason: `security-design.md` words it as a recognizable string "in the exception text"; searching for that text would contradict BR3.2.*
- **A3**: The unit stays one pull request even under C2. *Reason: the change is a new module, call-site edits and tests; if the spike makes it larger than one revertible slice, the split is raised at this stage's review, not decided here.*
- **OQ1**: the install point (C2 after the spike, fallback A) is the owner's choice at this plan's approval; see "Decision for the owner".
- **OQ2 (closed here)**: L07's exception is a botocore `ClientError` or `BotoCoreError` (read in `state.py` and `handler.py`); the security design's table gets its row in `code-summary.md`.
