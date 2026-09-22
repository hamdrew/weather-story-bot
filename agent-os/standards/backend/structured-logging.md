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
- Use `office` and `image_id` as the join fields whenever you know them
- Put errors in as `str(exc)` or `repr(exc)`, never a URL containing the token (`backend/secrets-in-errors`)
- Loggers: `logging.getLogger(__name__)` in modules. `handler` uses `"weather_story_bot"`, the parent, and tests capture that logger
- `configure_logging` keeps `httpx` and `httpcore` at WARNING because they log request URLs

## `office` and `aws_request_id`

Every line `handler.py` logs gets `office` and `aws_request_id` from `handler._RequestContextFilter`, a `logging.Filter` attached once, at import time, to the `weather_story_bot` logger — not passed by each caller. Don't add `"office"` to a call's `extra` in `handler.py`; the filter already supplies it.

- Backed by two module-level `contextvars.ContextVar`s (`_aws_request_id`, `_office`), not plain mutable attributes. `ContextVar.set` returns a token; `_invocation_context` and `_office_context` `.reset(token)` it in a `finally`, so cleanup is exact even on an exception — a plain attribute that someone forgets to clear back to `None` leaks into whatever logs next, which is exactly how this leaked once during review before the `ContextVar` swap
- `_invocation_context`, entered once per invocation in `lambda_handler` from `context.aws_request_id`, sets `aws_request_id` for everything inside it — including a later, unrelated `run()` call must **not** still see it once that `with` block has exited
- `_office_context` sets `office` once per office, wrapped around each office's iteration of `run`'s loop, reset after — so `"Run complete"`, which spans every office, carries no office at all
- Being attached to the `weather_story_bot` *logger* rather than a handler means it fires even when a test calls `run()` directly, without `configure_logging()` — `caplog` still sees `office` on every record
- It's logger-scoped, not handler-hierarchy-scoped: it only tags records logged directly through `logging.getLogger("weather_story_bot")` (`handler.py`'s own logger), not through a child logger like `nws.py`'s or `telegram.py`'s `logging.getLogger(__name__)`. A module whose lines need `office` too would need the filter attached to its own logger, or the call to pass it explicitly
- A new caller-supplied field always still goes through `extra` as usual; only `office`/`aws_request_id` are filter-supplied

| Level | Use when |
|---|---|
| `exception` | counted as `failed`, so the Lambda errors |
| `error` | needs attention, but the run succeeds (alarmed by a metric filter) |
| `warning` | tolerated or retried, no action needed |
| `info` | normal outcomes and contract lines (`testing/log-contracts`) |
