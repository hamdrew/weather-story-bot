# Handler Tests

`tests/test_handler.py` runs the real `NwsClient`, `PostedStore`, `StoryArchive` and `TelegramClient` over respx + moto. Don't stub `Services`. Ordering bugs (archive -> post -> record -> delete, see `backend/side-effect-order`), key or fingerprint mismatches and wire-shape bugs only show up when the real pieces run together.

- Use the `services` and `api` fixtures. `api` mocks NWS and Telegram, and message ids count up from 100
- Inject time and waits: `run(services, now=...)`, `sleep=lambda _: None`. Never use the real clock (except the `lambda_handler` end-to-end test, which moves `endTime` to 2999)
- Assert on the whole summary with `counts(...)`. Unlisted counts must be 0:

```python
assert run(services)["MKX"] == counts(updated=1, skipped=1)
```

- Change NWS between runs with `revise(api, mkx_payload, image, **changes)`
- If a test posts, reposts or deletes, run again and assert only skips with no new photo or delete calls. Pure reject or fail tests can skip this
- Check side effects through the real stores (`posted_record`, S3 keys, `deleted_ids`), not internals
