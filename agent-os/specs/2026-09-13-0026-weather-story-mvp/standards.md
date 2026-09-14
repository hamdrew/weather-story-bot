# Standards for Weather Story MVP

These standards were added after Tasks 1–9 were built. Tasks 10–11 and later changes to the clients follow them.

- **backend/client-errors** — `NwsClient` and `TelegramClient` each raise one public error type (`NwsError`, `TelegramError`) that wraps transport errors, bad statuses and malformed payloads. `handler.run` is the only catch-all.
- **backend/injected-clients** — Clients take their `httpx`/boto3 client and `sleep` from the caller. Only `handler._build_services` and `__main__` create clients.
- **backend/retries** — At most one retry inside a client. NWS GETs retry once on transport errors or 5xx. Telegram sends retry only on a 429 with `retry_after <= 30`.
- **backend/secrets-in-errors** — The Telegram token URL never appears in errors, tracebacks or logs (`from None`, no `str(exc)`, httpx loggers at WARNING).

Full text: `agent-os/standards/backend/`.
