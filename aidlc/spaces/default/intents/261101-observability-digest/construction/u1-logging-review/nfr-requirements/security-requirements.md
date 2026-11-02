# Security Requirements: u1-logging-review

## Sources

- `functional-design/functional-spec.md` and `rules.md` (BR3.1 to BR3.3, secrets check) [FR6.2]
- `inception/requirements-analysis/requirements.md`: FR6.2, NFR4 to NFR6
- Project rules: the Telegram token is never in Terraform variables or state; each environment keeps its token in its own SSM parameter

The unit is a Markdown review with no runtime component, no data store and no network surface, so authentication,
authorization and encryption do not apply to it. What it decides does touch security: what the bot may write
to its logs. The requirements below are the ones U2 must meet when it carries the decisions out.

## Requirements

NFR4.1, NFR4.2, NFR5.1 to NFR5.3 are requirements on the code and tests U2 writes; U1's own deliverable is the
document. Telegram's `description` text is accepted as non-secret: it is Telegram's own error wording and never
echoes the request URL.

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR5.1 | No log line carries the Telegram token, a Telegram URL, a caption, image bytes or a request or response body. Exception text is built from the exception type or Telegram's description only. | BR3.1, BR3.2; reviewed per call in the review's secrets table | FR6.2, NFR5 |
| NFR5.2 | `httpx` and `httpcore` stay capped at WARNING, so request URLs (which contain the token) are never logged at INFO. | Existing `configure_logging`; U2 keeps it when the formatter moves | FR6.2 |
| NFR4.1 | An offline test proves the token never reaches a log record on each handled Telegram failure path (transport error, 429, photo rejected, unexpected result, delete failed). Only the delete-failed path already asserts this (`tests/test_handler.py`); the other four paths need new assertions, so this is mostly new test work in U2. | BR3.3; runs in `mise run test` with respx, no credentials | FR6.2, NFR4 |
| NFR4.2 | The new `run.slow` path and every renamed field keep line coverage at or above 80%, with offline tests. | `mise run coverage`; the `run.slow` test in the functional spec's W2 | NFR4 |
| NFR5.3 | The log-field renames (D1 to D3) and the new warning change nothing the bot posts to Telegram or how. | Existing suites stay green | NFR5 |

## Threat considerations

| Threat | Where | Mitigation |
|--------|-------|------------|
| Token written to CloudWatch Logs (kept 30 days, readable by anyone with log access) | Telegram client error text, library request logs | NFR5.1, NFR5.2, NFR4.1 |
| A field value that holds a secret introduced by a later change | any new `extra` field | The review's rule BR3.1 stands for later changes; the NFR4.1 test fails on a leak |
| Story content leaking through logs | `Ambiguous stories` ERROR field | Only ids, titles and reasons are logged (BR3.2) |

## Not applicable

Authentication, authorization, encryption at rest or in transit and compliance regimes: the unit adds none, and the
bot's existing controls (SSM for the token, IAM boundaries) are untouched.
