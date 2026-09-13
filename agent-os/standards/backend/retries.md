# Retries

Retry at most once inside a client. The next scheduled run (every 15 min) is the real retry, and Lambda async retries are 0.

Decide by side effects:

| Call | Transport error / 5xx | 429 |
|---|---|---|
| Read-only (NWS GET) | retry once after `retry_delay` | - |
| Creates something (Telegram send) | never retry | retry once if `retry_after <= 30` |

- Never retry a create on a transport error: the first attempt may have been delivered, so a retry risks a duplicate post
- Don't wait longer than `MAX_RETRY_AFTER_SECONDS`; raise and let the next run pick it up
- Wait through the injected `sleep` so tests can assert on the delays
- No retry libraries (tenacity etc.); keep the loop explicit in `_get`/`_call`
- Log each retry with `logger.warning(..., extra={...})`
