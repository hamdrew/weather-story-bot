# Injected Clients

Wrappers around external services (HTTP or AWS) take their client from the caller. They never create one or read env vars.

```python
class NwsClient:
    def __init__(
        self,
        http: httpx.Client,
        user_agent: str,
        *,
        base_url: str = BASE_URL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None: ...

PostedStore(boto3.client("dynamodb"), table_name)
```

- Only `handler._build_services` (Lambda) and `__main__` (CLI) create clients and read config
- Why: one connection pool shared across clients and reused by warm Lambda invocations; tests pass a client that respx/moto intercept
- Anything that waits takes a keyword-only `sleep`; tests pass `lambda _: None` or `list.append`
- Timeouts are module constants, passed on every request
