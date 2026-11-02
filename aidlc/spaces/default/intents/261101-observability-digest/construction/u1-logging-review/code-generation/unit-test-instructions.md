# Unit Test Instructions: u1-logging-review

## Test framework

pytest, already configured in `pyproject.toml` (`-ra --strict-markers`). No new dependency, plugin or
configuration. Test ordering follows the Testing Contract in the plan: new content first (the document), then its
tests in the same change.

## Run this unit's tests

```bash
uv run pytest tests/test_logging_review.py
```

The command is runnable now: pytest and `uv` are installed, and the test file is created in Step 5 of the plan.
The whole project's suite (`mise run test`) is run by Build and Test, not here.

## Tests (3, Standard strategy for a single document-checking module)

| Test | Checks |
|------|--------|
| `test_every_log_message_in_src_is_in_the_review` | Every string passed as the message of a `logger.<level>` call in `src/weather_story_bot/` appears in the inventory table of `docs/logging-review.md`. A new log call added later without a review row fails here. |
| `test_event_names_are_well_formed_and_unique` | Every event name in the inventory matches `^[a-z]+(\.[a-z_]+)+$`, uses one of the areas nws, telegram, office, story, store, history, run, and appears once (BR1.2). |
| `test_review_levels_match_the_code` | The level written beside each message in the inventory equals the level of that call in `src/`; the one new call (`Run was slow`) is skipped until U2 adds it. |

## Mocking and test data

None needed. The tests read `src/weather_story_bot/*.py` with `ast` and the Markdown file with `pathlib`; there is
no network, AWS or Telegram access and no credentials. They run under the existing autouse credential fixture.

## Expected coverage

The unit adds no production code, so line coverage of `src/weather_story_bot/` is unchanged. The project's 80%
line-coverage floor is measured by Build and Test on the full suite with `mise run coverage`; a unit-scoped run does
not judge it, and nothing here lowers it.
