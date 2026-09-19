# Offline Tests

Tests never touch real NWS, Telegram or AWS. The risk is a real send: a post to the live channel, a write to the real account (via AWS_PROFILE / `aws login`) or use of a dev's `.env` token.

- HTTP: `respx`. AWS: `moto` via the `aws`/`dynamodb`/`s3` fixtures
- The autouse `aws_env` fixture sets fake creds and unsets `AWS_PROFILE`. Don't bypass it
- CLI tests stub `load_dotenv` and clear `TELEGRAM_*` env vars
- Prove nothing was sent with an empty router:

```python
with respx.mock() as router:
    assert cli.main([...]) == 2
    assert not router.calls
```

## Faking failures

- Fake them at the wire first: `.respond(503)`, `side_effect=httpx.ConnectError(...)`, moto state
- Use `monkeypatch.setattr` on a real object's method only for failures moto can't produce (e.g. throttled PutItem)
- Never swap a client for `MagicMock`
