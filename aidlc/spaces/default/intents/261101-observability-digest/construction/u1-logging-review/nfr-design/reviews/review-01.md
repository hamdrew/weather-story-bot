## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-02T01:51:40Z
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Major | aidlc/spaces/default/intents/261101-observability-digest/construction/u1-logging-review/nfr-design/security-design.md > Design, row NFR4.1 | The leak test as described can pass without proving anything about library logging. The existing handler tests only raise the `weather_story_bot` logger to INFO (`caplog.set_level(logging.INFO, logger="weather_story_bot")`), and in tests `configure_logging` is not called, so `httpx` and `httpcore` fall back to the root level (WARNING by default). A request-URL record from httpx at INFO, which is the real token-leak vector NFR5.2 guards against, would never reach the captured records. The design also does not say the test confirms the token really appeared in the mocked request URL, so a mis-matched respx route would yield a vacuous pass. | Specify that the leak test calls `configure_logging()` (or sets the root logger to INFO) before driving the failures, so httpx and httpcore records are captured under the same level cap production uses. Add a control assertion that the respx route matched the token-bearing URL. Say that the NFR5.2 level test and the leak test are separate checks and both are needed. | New |
| R-02 | Minor | aidlc/spaces/default/intents/261101-observability-digest/construction/u1-logging-review/nfr-design/security-design.md > Failure behaviour and Rejected | The design relies on "the LogFormatter never raises (ADR-005)" and rejects formatter redaction because it "adds a path that could raise". The shipped `JsonFormatter` (`handler.py`) has no guard: `json.dumps(..., default=str)` can still raise (for example circular structures) and `formatException` is unguarded. Python's logging then drops the record to stderr. The claim is an assertion with no stated control or test. | State the concrete control U2 builds (a try/except fallback that emits a minimal record) and name a test for it, or soften the claim to "does not raise for the field types the bot logs". | New |
| R-03 | Minor | aidlc/spaces/default/intents/261101-observability-digest/construction/u1-logging-review/nfr-design/security-design.md > Design, row NFR5.1 | The row says the `error` = `repr(exc)` change is safe because those exceptions "never carry the Telegram URL". That holds for the `TelegramError` paths in `telegram.py` (`_call` raises with `from None` and builds text from the exception type or the description), but it is asserted rather than shown, and no log call site is named where `repr(exc)` is used. A later `raise_for_status()` or an `httpx.HTTPStatusError` on a Telegram call would include the URL. | Name the call sites that gain `error=repr(exc)` and restrict the rule to them, or add to the leak test an assertion that no `error` field comes from an httpx status error on a Telegram URL. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| traceability sensor (nfr-design) | passed (run by the orchestrator) | All five NFRs (NFR4.1, NFR4.2, NFR5.1, NFR5.2, NFR5.3) are in `traceability.json`, each with a target. I checked that each target matches a control row in `security-design.md`. |

### Summary

Every NFR maps to a buildable control, and the claims about `telegram.py` (`from None`, type-name or description-only exception text, `httpx` and `httpcore` capped at WARNING in `configure_logging`) hold against the code. The main weakness is the leak test: unless it enables INFO capture for the HTTP libraries and confirms the token was in the mocked URL, it can pass without testing the vector NFR5.2 guards against. Two minor points concern the unproven "never raises" claim and the unnamed `repr(exc)` call sites.
