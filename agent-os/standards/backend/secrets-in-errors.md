# Secrets in Errors and Logs

The Telegram bot token is part of every Telegram request URL. Never let that URL reach an exception message, a traceback or a log.

```python
except httpx.TransportError as exc:
    # Never include the URL, which contains the bot token.
    raise TelegramError(f"{method} request failed: {type(exc).__name__}") from None
```

- Use `from None`, not `from exc`: the chained httpx error's message contains the URL
- Report the method name and exception type, never `str(exc)`, `repr(exc)` or the URL
- Keep `httpx` and `httpcore` loggers at WARNING (they log full URLs at INFO)
- Tests assert `TOKEN not in str(err)` and `err.__cause__ is None`
- The token comes only from SSM at runtime, never from env vars or Terraform. The local CLI never reads it (`backend/cli`)
- Chat IDs and NWS URLs aren't secret; logging them is fine
