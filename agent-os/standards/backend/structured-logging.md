# Structured Logging

Log a fixed message and put the data in `extra`. `JsonFormatter` turns each `extra` key into a JSON field, so metric filters and Logs Insights can match `$.message` exactly and filter on fields.

```python
logger.warning(
    "Telegram delete failed, old message kept",
    extra={"telegram_message_id": replaced.telegram_message_id},
)
```

- Never use f-strings or `%` args in the message. Every line becomes unique and the data is buried in text
- `extra` keys can't be reserved `LogRecord` attributes (`filename`, `name`, `message`, `module` and so on). They raise `KeyError`, so use a prefixed name like `image_filename`
- Use `image_id` as a join field whenever you know it; `office` is supplied for you (below)
- Put errors in as `str(exc)` or `repr(exc)`, never a URL containing the token (`backend/secrets-in-errors`)
- Loggers: `logging.getLogger(__name__)` in modules. `handler` uses `"weather_story_bot"`, the parent, and tests capture that logger
- `configure_logging` keeps `httpx` and `httpcore` at WARNING because they log request URLs

## `office` and `aws_request_id`

Every log record created during a run gets `office` and `aws_request_id` from `handler._record_with_request_context`, a `logging` record factory installed once, at import time — not passed by each caller. That includes child loggers (`weather_story_bot.telegram`, `.nws`, `.archive`, `.history`) and third-party ones (botocore, httpx), so every line of an office's run can be joined on either field.

- **Never pass `office` or `aws_request_id` in `extra`.** Once the factory has set them, `Logger.makeRecord` refuses to overwrite an existing record attribute and raises `KeyError`, which turns a log call into a crash. (`history._log_failure` used to pass `office` by hand; it can't any more)
- Why a record factory, not a `logging.Filter`: a logger's filters only run for records created on that logger, never for records propagating up from its children, so a filter on `weather_story_bot` missed every line from `nws.py`, `telegram.py`, `archive.py` and `history.py`. A filter on the root *handler* would see them all, but only after `configure_logging()`, so tests calling `run()` directly would lose the fields
- The factory wraps whichever factory is in place when `handler` is imported instead of replacing it. Anything that calls `logging.setLogRecordFactory` later, without chaining, would drop both fields; `test_handler` would catch that
- Backed by two module-level `contextvars.ContextVar`s (`_aws_request_id`, `_office`), not plain mutable attributes. `ContextVar.set` returns a token; `_invocation_context` and `_office_context` `.reset(token)` it in a `finally`, so cleanup is exact even on an exception — a plain attribute that someone forgets to clear back to `None` leaks into whatever logs next, which is exactly how this leaked once during review before the `ContextVar` swap
- `_invocation_context`, entered once per invocation in `lambda_handler` from `context.aws_request_id`, sets `aws_request_id` for everything inside it — including a later, unrelated `run()` call must **not** still see it once that `with` block has exited
- `_office_context` sets `office` once per office, wrapped around each office's iteration of `run`'s loop, reset after — so `"Run complete"`, which spans every office, carries no office at all
- Code outside a run (unit tests calling `StoryHistory` or `TelegramClient` directly, `scripts/`) gets neither field; assert them in `tests/test_handler.py`, where the context exists
- A new caller-supplied field always still goes through `extra` as usual; only `office`/`aws_request_id` are factory-supplied
- Treat `aws_request_id` as unique but not random. Scheduled invocations get structured IDs: hex digits 3–10 are the scheduled time (seconds, offset by `0x60000000`), and the prefix and tail stay fixed until the schedule is re-activated, e.g. `e16ab440-4453-4ddb-b52a-f9af386f1184`. Code deploys don't change them. Only a direct `aws lambda invoke` gets a random UUID. That structure is observed behaviour (936 invocations, 2026-09-13 to 09-23, no duplicates), not documented. Fine as a correlation key; never sample or shard on its leading characters

| Level | Use when |
|---|---|
| `exception` | counted as `failed`, so the Lambda errors |
| `error` | needs attention, but the run succeeds (alarmed by a metric filter) |
| `warning` | tolerated or retried, no action needed |
| `info` | normal outcomes and contract lines (`testing/log-contracts`) |
