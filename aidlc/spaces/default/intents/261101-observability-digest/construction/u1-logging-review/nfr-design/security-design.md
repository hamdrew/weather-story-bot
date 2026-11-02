# Security Design: u1-logging-review

## Sources

- `nfr-requirements/security-requirements.md` (NFR4.1, NFR4.2, NFR5.1 to NFR5.3) and `tech-stack-decisions.md`
- `functional-design/functional-spec.md` (secrets check, W2, W3) and `rules.md` (BR3.1 to BR3.3, BR4.1)
- `src/weather_story_bot/handler.py` (`configure_logging`) and `telegram.py` (`_call`)

The unit is a document, so this design covers the controls that U2 builds from the review's decisions. No
authentication, encryption or network design applies.

## Design

| Requirement | Control | How U2 builds it |
|-------------|---------|------------------|
| NFR5.1 | Keep secrets out by construction: no log call receives a URL, request object or environment mapping; exception text comes from the exception type or Telegram's description. | `_call` keeps raising `TelegramError(f"{method} request failed: {type(exc).__name__}") from None`. `error=repr(exc)` is used only at the call sites L07 (boto errors), L11 and L13 (`TelegramError` subclasses, whose text is built as above) and L19 (boto errors); L17 (NWS, a public URL) already uses it. The rule is limited to those sites. If a Telegram call ever used `raise_for_status()`, the resulting `httpx.HTTPStatusError` would carry the URL, so the leak test also covers an HTTP error status on every Telegram method. |
| NFR5.2 | Cap the libraries that log requests. | `configure_logging` keeps `httpx` and `httpcore` at WARNING when it moves into the LogFormatter module; the move is covered by a test that reads both levels back. |
| NFR4.1 | Prove it, by asserting on what is actually written. | One parametrized test drives each handled Telegram failure (transport error, 429 then success, photo rejected, unexpected result, delete failed) with respx and a recognizable token. It calls `configure_logging()` first, so `httpx` and `httpcore` records are captured under the same level cap production uses (without it the root logger sits at WARNING in tests and an INFO request-URL record would never be seen). It passes every captured record through the shipped LogFormatter, so extra fields and the exception text are included, and asserts the token is nowhere in the output. A control assertion in each case checks that the respx route matched the token-bearing URL, so a mis-matched route cannot give a vacuous pass. This test and the NFR5.2 level test are separate checks and both are needed. |
| NFR4.2 | Cover the new path. | The `run.slow` test in W2 (patched `time.monotonic`: past 150 s, at or below 150 s, ordering before "Run complete"), and the renamed fields exercised by the tests that already read them. `mise run coverage` confirms 80% or more. |
| NFR5.3 | Change no posting behaviour. | The edits touch log calls, field names and one new timing check; the planner, Telegram client calls and stores are unchanged, and the existing suites stay green. |

## Failure behaviour

- If the leak test fails, the build fails (`checks` job); nothing deploys.
- The LogFormatter does not raise for the field types the bot logs (strings, numbers, lists and dicts of them; `default=str` covers the rest). U2 adds a `try/except` fallback that emits a minimal record (time, level, logger, message) if serialising an extra field or the exception ever fails, with a test that passes a circular structure; this is how ADR-005's "never raises" is made true.

## Rejected

- Redacting the token inside the formatter: it would hide a leak instead of preventing it, and it adds a path that could raise.
- A regular-expression scan of the source for `token`: brittle, and it cannot see runtime text.
