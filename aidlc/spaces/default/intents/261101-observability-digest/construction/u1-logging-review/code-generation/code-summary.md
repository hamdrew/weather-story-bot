# Code Summary: u1-logging-review

## Sources

- `code-generation-plan.md` (approved) and `unit-test-instructions.md`
- `functional-design/` and `nfr-design/security-design.md` of this unit

## Files created

| File | What it is |
|------|-----------|
| `docs/logging-review.md` | The logging review (FR6.1, FR6.2): method, the rules BR1.1 to BR4.2, table 1 (inventory of the 19 log calls plus the one new `run.slow` call, each with its decided event name), table 2 (findings F1 to F9), table 3 (decisions D1 to D9), the secrets check, the `run.slow` design, edge cases, and what U2, U4 and U5 take from it. |
| `tests/test_logging_review.py` | Three offline tests that keep table 1 honest: every log message in `src/` is in the inventory, event names are well-formed and unique, and the levels in the inventory match the code. |

No file under `src/`, `infra/` or any other existing path changed.

## Key decisions

- The review lives in a new `docs/` folder; the existing README and AI-DLC record are untouched.
- The three tests read the code with `ast` and the document with `pathlib`, so they need no network, credentials or fixtures. They cost nothing to keep: a new log call without a review row fails the first test.
- The requirements that only U2's code can meet (the token leak test, the `run.slow` check and its test, the httpx cap test) are written into the document under "What U2 must build" and marked Deferred in `traceability.json`, not claimed as built.
- The review adds one item to U2 beyond the unit definition: a fallback in the formatter so a failure to serialise a field cannot drop a record (an architecture-review finding, made concrete in the NFR design).

## Test coverage summary

4 new tests; the full suite passes (300 tests). No production code changed, so line coverage of `src/weather_story_bot/` is unchanged. Each test was checked by changing the document in memory (a missing row, a duplicate event, an unknown area, a wrong level) and watching it fail.

## Tests written but not executed in this stage

None. `mise run lint` and `mise run test` both passed. `mise run coverage`, `tftest` and `scan` were not run: nothing they check changed.

## Deviations from the plan

One. After the architecture review the test module grew from the planned 3 tests to 4, and the first test got a second check: a new test asserts that every WARNING and ERROR row has an event and that no INFO row other than the message-sent line does, and the first test now also fails on a table row (not marked "(new)") whose message no longer exists in `src/`. Both close gaps the review named. U2 must remove the "(new)" mark from L20 when it adds that call.
