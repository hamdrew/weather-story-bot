# Client Errors

Each client raises exactly one public error type. It wraps transport errors, bad HTTP statuses and malformed payloads.

```python
class NwsError(Exception):
    """The NWS API could not be reached or returned an unusable response."""


try:
    stories = [Story.from_api(i) for i in response.json()["stories"]]
except (ValueError, KeyError, TypeError) as exc:
    raise NwsError(f"Unexpected response for {office_id}: {exc}") from exc
```

- Callers catch only client error types: `except (NwsError, TelegramError)`
- Why: callers don't need httpx internals, and the client controls the message (see secrets-in-errors)
- Internal control flow uses private subclasses (`_PhotoRejectedError`)
- Only exception: `handler.run` catches `Exception` per office and per story so one failure can't block the rest. It must `logger.exception` and count `failed`, which makes `lambda_handler` raise `ProcessingError`
