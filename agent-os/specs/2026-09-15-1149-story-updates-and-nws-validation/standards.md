# Standards for Story Updates and NWS Validation

- **backend/untrusted-nws-data** (added with this spec) — Reject every active story that shares an image ID, title + `startTime`, or image SHA-256 with another; log one `Ambiguous stories from NWS` ERROR line; count `rejected`; don't raise. Ignore expired stories. Don't use `updateTime` or UUIDs to detect changes.
- **backend/client-errors** — `TelegramClient.delete_message` raises only `TelegramError`. The handler catches it so a failed delete keeps the new post; `handler.run` stays the only catch-all.
- **backend/injected-clients** — `run` takes `now` from the caller, so tests control which stories are expired.
- **backend/retries** — `deleteMessage` goes through `_call`: a 429 with `retry_after <= 30` retries once, transport errors don't. The next update is the only later retry.
- **backend/secrets-in-errors** — Delete errors come from `_call`, which never includes the token URL.

Full text: `agent-os/standards/backend/`.
