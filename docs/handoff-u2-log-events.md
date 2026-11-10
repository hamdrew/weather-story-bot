# Handoff: observability unit U2 (log events)

Written 2026-11-09, when the AI-DLC workflow was removed from this repository. It records where the
work stopped and holds a prompt you can give to another coding framework to carry on.

## The work

The observability effort adds a CloudWatch dashboard and a weekly digest of warnings (`docs/roadmap.md`,
Phase 2.3). It was split into units:

| Unit | What | State |
|------|------|-------|
| U1 | Logging review (`docs/logging-review.md`) | Done and merged |
| U3 | Per-environment health dashboard with a verdict | Merged (#42, #43), plus the readability tweak `fea732a` |
| **U2** | **Log events: JSON log lines, an `event` name on every WARNING/ERROR and the message-sent line, `run.slow`** | **In progress, branch `u2-log-events`** |
| U4 | Sturdy alarms (filter on U2's event names) | Not started |
| U5 | Warnings-and-errors digest (filter on U2's event names) | Not started |

## Where U2 stopped

- The design is finished and was reviewed: functional design, NFR requirements, NFR design and
  infrastructure design (U2 adds no Terraform and no new CI job).
- The code-generation plan is written but was **not approved**, and no plan step is ticked.
  The plan and specs are in `docs/handoff/u2-log-events/`:
  - `functional-spec.md`, `rules.md` (business rules BR1.1 to BR6.4), `entities.md`
  - `code-generation-plan.md` (steps, open decision OQ1) and `unit-test-instructions.md`
- Uncommitted work on the branch:
  - `src/weather_story_bot/log_format.py` (new, 142 lines): the JSON formatter and request-context scopes.
  - `src/weather_story_bot/__init__.py`: imports `log_format` first and calls `install_json_format()`.
  - Neither is verified. Plan Step 2 (a throw-away spike) was meant to check that the full pytest run is
    still green, `caplog` still captures records, `uv run weather-story-bot --dry-run` is unchanged, and a
    double import adds one root handler.
- Not started: tests (`tests/test_log_format.py`, `tests/test_log_secrets.py`, drift-test edits in
  `tests/test_logging_review.py`), the `event` field on each WARNING/ERROR call and the message-sent line in
  `handler.py`, `telegram.py`, `nws.py` and `history.py`, the `run.slow` warning, and the matching updates to
  `docs/logging-review.md` (its table 1 is the source of event names, and a test fails when code and table differ).

## Open decision (OQ1)

Where the JSON formatter goes on. Option **C2** (the in-progress code): at package import, so records
logged while `httpx` and `boto3` import are also JSON; this changes the root logger when the package is
imported, so check pytest and the dry run. Option **A**: at the first `configure_logging()` of each
invocation; simpler, but FR2.4 (any WARNING from any logger is a readable record) is then met only from the
first invocation. The plan's default is C2 after the spike, with A as the fallback.

## Fixed constraints

- Message text, levels and stack traces do not change (BR2.4), so today's message-based alarm filters keep matching until U4.
- Coverage: 80% line coverage for the project, and no uncovered line or branch in `log_format.py`.
- `ty check` clean with no `# ty: ignore`; every test offline; no TODO or FIXME markers.
- Gate: `mise run lint ::: test`. Do not commit without asking the owner.

## Earlier records

The requirements (FR/NFR), unit definitions and domain design were committed in PR #35 (commit `ce9fcb9`)
under `aidlc/spaces/default/intents/261101-observability-digest/`, a directory this change deletes. Read them from history:

```bash
git show ce9fcb9:aidlc/spaces/default/intents/261101-observability-digest/inception/requirements-analysis/requirements.md
git show ce9fcb9:aidlc/spaces/default/intents/261101-observability-digest/inception/units-generation/unit-of-work.md
git show ce9fcb9:aidlc/spaces/default/intents/261101-observability-digest/inception/domain-design/decisions.md
```

U1 and U3's design records are in the history of the same directory (commits around #35 and #42/#43).

## Prompt for another framework

> Continue unit U2 "log events" of the observability work in this repo (weather-story-bot, a Python 3.13 Lambda; read CLAUDE.md first). Branch `u2-log-events` holds uncommitted work in progress: `src/weather_story_bot/log_format.py` and the `__init__.py` change. Read `docs/handoff-u2-log-events.md` and `docs/handoff/u2-log-events/` (spec, business rules BR1.1 to BR6.4, code-generation plan), plus `docs/logging-review.md` and `docs/roadmap.md` (Phase 2.3). First verify the in-progress code against Step 2 of the plan (pytest green, caplog works, `uv run weather-story-bot --dry-run` unchanged, a double import adds one handler); if any check fails, fall back to option A. Then finish the plan: new code first and its tests in the same change, `event` names on every WARNING and ERROR and the message-sent line, the `run.slow` warning, the drift and token-leak tests, and `docs/logging-review.md` kept in step. Do not change log message text, levels or stack traces. Gates: `mise run lint ::: test` must pass, the 80% coverage floor (`mise run coverage`), and no uncovered line or branch in `log_format.py`. One pull request for the unit; do not commit without asking me. After U2 the remaining observability units are U4 (sturdy alarms) and U5 (warnings-and-errors digest), which filter on U2's event names.
