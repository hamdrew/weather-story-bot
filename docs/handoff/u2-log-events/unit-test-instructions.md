# Unit Test Instructions: u2-log-events

## Sources

- `code-generation-plan.md` (Steps 1, 7 to 13) and its Testing Contract (custom: new code first, then its tests; Standard strategy; classic scope)
- `nfr-design/logical-components.md` ("Tests", "Coverage target") and `rules.md` (BR1.1 to BR6.4)
- `mise.toml` (`test` is `uv run pytest`; `coverage` is `uv run pytest --cov --cov-report=term-missing --cov-report=html`) and `pyproject.toml` (`testpaths = ["tests"]`, `addopts = ["-ra", "--strict-markers"]`, branch coverage on, `source = ["weather_story_bot"]`)

## Framework and setup

pytest, with respx for HTTP, moto for AWS and `caplog` for log records. Nothing is added: no dependency, no config
change, no marker. Every test runs offline; the autouse `aws_env` fixture in `tests/conftest.py` replaces any real AWS
or Telegram credentials. The moto-backed `dynamodb` and `s3` fixtures come from `tests/conftest.py`. Coverage stays
out of `addopts` (it breaks debugger breakpoints) and runs only through the commands below.

## Run this unit's tests

The unit's own tests, by exact path (every command below is scoped to this unit; none is a bare `uv run pytest`):

```bash
uv run pytest tests/test_log_format.py tests/test_logging_review.py tests/test_log_secrets.py
```

The existing test modules whose log assertions this unit changes or extends, by exact path:

```bash
uv run pytest tests/test_handler.py tests/test_telegram.py tests/test_nws.py tests/test_history.py
```

One module or one test while working:

```bash
uv run pytest tests/test_log_format.py -k fallback
```

The whole suite (`mise run test`) is the last step of Code Generation and is run again by Build and Test; it is not
repeated per unit command above.

## Expected coverage targets

- **`log_format.py`: no missing line and no missing branch** (NFR4.4), including the fallback line, the last-resort
  line, a non-string `record.msg`, a failed `exc_info` format and both scope exits (return and exception). This is a
  target for this unit's own module, so it has its own check, in a command of its own with nothing after it:

```bash
uv run pytest tests/test_log_format.py --cov=weather_story_bot.log_format --cov-branch --cov-report=term-missing --cov-fail-under=100
```

  The 100 applies only to the one measured module (`--cov` names it), so it does not touch the project floor. If
  this exits non-zero, a line or branch of `log_format.py` is untested: add the test, never lower the number.
- **Project floor: 80% line coverage.** It covers all measured source, so a unit-scoped run does not judge it (other
  units' tests cover other files). Build and Test checks it on the full suite with `mise run coverage`. Under Code
  Generation the floor is checked once, by hand, with `mise run coverage`, and the `log_format.py` line from the
  report goes in the pull request body. Nothing here changes the floor or its configuration.

## Test inventory (Standard strategy)

| Module | What it proves | Rules | Approx. cases |
|--------|----------------|-------|---------------|
| `tests/test_log_format.py` (new) | Line shape, extras cannot replace core fields, fallback and last-resort tiers, one line per record, third-party records, context scopes restore, factory chains, install is idempotent (C2 only) | BR1.1 to BR1.5, BR1.7, BR6.4 | 20 |
| `tests/test_handler.py` | Each handler call's event and field, message text unchanged; the four slow-run cases; ambiguous-listing signal event | BR2.1, BR2.2, BR2.4, BR3.2, BR4.1, BR4.2, BR6.2 | 14 |
| `tests/test_telegram.py` | L13, L15, L16 events and fields; message-sent signal event | BR2.1, BR2.2, BR3.1, BR3.2, BR6.2 | 5 |
| `tests/test_nws.py` | L17, L18 events; `http_status` | BR2.1, BR3.1 | 3 |
| `tests/test_history.py` | L19 event; `error` as `repr` | BR2.1, BR3.2 | 2 |
| `tests/test_logging_review.py` | AST drift checks and the checker's own tests against bad snippets; code and table 1 list the same events | BR2.3, BR3.3, BR6.1, BR6.3 | 8 |
| `tests/test_log_secrets.py` (new) | The token, `api.telegram.org`, the caption and the image bytes never reach a formatted line on any handled failure; control assertion; the caps read back | BR5.1 to BR5.3 | 12 |

About 60 cases in about 40 test functions, many of them parametrised. Each module still tests one source module,
except `test_log_secrets.py`, which drives three and so has a module of its own (functional spec).

## Mocking and stubbing

- **HTTP**: respx. Telegram routes are built from a recognizable token (`123:secret-token`), so the control
  assertion (BR5.2) can show the route for the token-bearing URL was called. NWS routes use the fixtures already in
  `tests/`.
- **AWS**: moto through the shared `dynamodb` and `s3` fixtures. A throttled call is made by replacing the client's
  method, as the existing `test_failed_release_still_counts_the_run` does.
- **Log records**: `caplog` with `caplog.set_level(logging.INFO, logger="weather_story_bot")`. The leak test calls
  `handler.configure_logging()` first and passes every record through the shipped `JsonFormatter`.
- **The clock**: the slow-run tests replace `handler._monotonic` with a fake that returns scripted readings; they
  never patch `time.monotonic` (assumption A3 of the functional spec). The fake is given back by `monkeypatch`.
- **The drift test** reads `src/weather_story_bot/*.py` with `ast` and never imports the package.
- **No test sleeps or waits**: the clients take a `sleep` argument, which tests already replace.

## Test data

- Real captured NWS listings through `office_payload` / `office_stories` and the `mkx_payload` fixture, and the
  `make_story(**overrides)` builder, all in `tests/conftest.py`.
- For the formatter: hand-built records from `logging.makeLogRecord`, a circular dict, an object whose `__str__`
  raises, and a record with `exc_info` whose formatting is made to fail.
- For the leak test: the token, a caption and an image byte string that are recognizable and appear nowhere else.

## Pass condition

All commands above exit 0. A failure of the `log_format.py` coverage command with every test passing is an untested
line or branch, not a flaky test.
