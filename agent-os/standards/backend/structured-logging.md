# Structured Logging

Log a fixed message and put the data in `extra`. `JsonFormatter` turns each `extra` key into a JSON field, so metric filters and Logs Insights can match `$.message` exactly and filter on fields.

```python
logger.warning(
    "Telegram delete failed, old message kept",
    extra={"office": office.office_id, "telegram_message_id": replaced.telegram_message_id},
)
```

- Never use f-strings or `%` args in the message. Every line becomes unique and the data is buried in text
- `extra` keys can't be reserved `LogRecord` attributes (`filename`, `name`, `message`, `module` and so on). They raise `KeyError`, so use a prefixed name like `image_filename`
- Use `office` and `image_id` as the join fields whenever you know them
- Put errors in as `str(exc)` or `repr(exc)`, never a URL containing the token (`backend/secrets-in-errors`)
- Loggers: `logging.getLogger(__name__)` in modules. `handler` uses `"weather_story_bot"`, the parent, and tests capture that logger
- `configure_logging` keeps `httpx` and `httpcore` at WARNING because they log request URLs

| Level | Use when |
|---|---|
| `exception` | counted as `failed`, so the Lambda errors |
| `error` | needs attention, but the run succeeds (alarmed by a metric filter) |
| `warning` | tolerated or retried, no action needed |
| `info` | normal outcomes and contract lines (`testing/log-contracts`) |
