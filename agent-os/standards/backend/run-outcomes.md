# Run Outcomes

`handler.run` returns one set of counts per office. The keys are fixed: `posted`, `updated`, `skipped`, `rejected`, `failed`.

| Count | Meaning | Run result |
|---|---|---|
| `posted` / `updated` | new post / repost of a changed story | success |
| `skipped` | unchanged, or expired (no action at all); `1` for the office when another run holds its lease | success + INFO `"Office run already in progress"` |
| `rejected` | ambiguous NWS data we refuse (`backend/untrusted-nws-data`) | success + ERROR log + `nws-ambiguous` alarm |
| `failed` | exception taking the office lease, or on list, download, reading posted stories (fails the whole office) or process | `ProcessingError` -> Lambda Errors -> `errors` alarm |

- Choosing a count: if the next run may fix it (our side or a transient error), it's `failed`. Upstream data we refuse on purpose gets its own count, an ERROR log line and a metric-filter alarm, and the run still succeeds
- `lambda_handler` logs `"Run complete"` with the summary **before** raising `ProcessingError`, so runs with failed stories still leave a summary. Errors before `run()` (`ConfigError`, SSM or boto3 failures in `_build_services`) raise with no summary. Look for the Lambda traceback instead
- The office lease (`state.OfficeLease`): losing it to another run is `skipped`, not a failure. Scheduler's at-least-once delivery makes overlaps expected, and they must not trip the `errors` alarm. A DynamoDB error *taking* it is `failed`, never "proceed anyway": without the lease the run can't know it's alone. A failed *release* is a WARNING only; the lease expires before the next run
- A new count needs `counts()` in `tests/test_handler.py` updated, plus an alarm or dashboard decision

## Cold-start cache

`_services` (HTTP pool, boto3 clients, Telegram token from SSM) is built once per container.

- A token rotated in SSM isn't picked up until new containers start. After rotating, apply a real function config change through Terraform to force them. Until then, runs may fail with the old token
- Tests reset it with `monkeypatch.setattr(handler, "_services", None)`
