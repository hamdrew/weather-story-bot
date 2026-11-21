# Quickstart: validating U2 Log Events

How to prove the unit works, offline and then on staging. Design detail is in [research.md](research.md), the line
shape in [contracts/log-line.md](contracts/log-line.md).

## 1. Offline gates

```bash
mise run lint ::: test ::: tftest ::: scan
```

```bash
mise run coverage
```

Expected: everything green, and project line coverage at least 80%.

## 2. The contract checks on their own

```bash
uv run pytest tests/test_logging_review.py tests/test_log_secrets.py -v
```

Expected: the drift check passes on `src/`, each bad-sample test reports its rule's failure, and every Telegram
failure path shows its token-bearing route was called with no secret in any record.

## 3. The local dry run is unchanged

Run the dry run on `origin/main` and then straight away on the U2 branch, so NWS has had no time to change its
stories, and compare their stdout. Take the baseline from a separate worktree: uncommitted U2 edits would follow a
branch switch, and the local `main` may be behind.

```bash
git fetch origin && git worktree add /private/tmp/u2-baseline origin/main
```

```bash
(cd /private/tmp/u2-baseline && uv run weather-story-bot --dry-run)
```

```bash
uv run weather-story-bot --dry-run
```

```bash
git worktree remove /private/tmp/u2-baseline
```

Expected: the same decisions and captions on both. Warnings, if any, print as plain text to stderr on both. If the two
differ, run the pair again before treating it as a failure: NWS may have updated a story between them.

## 4. Staging, before approving production (FR-020)

After merging, the pipeline deploys staging and then waits for approval before production. Before approving:

1. Wait for the first scheduled staging run after the deploy, or start one if the staging schedule is paused (`mise run start staging` changes a live environment, so the owner runs it).
2. In CloudWatch Logs Insights, select the staging function's log group (`/aws/lambda/<staging function name>`), set the time range to cover that run, and run:

   ```text
   fields @timestamp, timestamp, requestId, level, logger, office, event, message, time, aws_request_id
   | filter ispresent(level)
   | sort @timestamp asc
   | limit 200
   ```

   `ispresent(level)` keeps the application lines and leaves out the runtime's `START`, `END` and `REPORT` lines,
   which have their own keys (among them `time`). An empty cell means the line has no such key.

3. Check, in this order (SC-006). The check passes only if every item holds:
   1. the query returns at least one row; zero rows is a fail;
   2. every row has `timestamp`, `requestId`, `level` and `logger`;
   3. for each office in staging's configuration (`offices` in the local `infra/envs/staging.tfvars`), the lines written while it was processed have `office` set to it, and "Run complete" has no `office`;
   4. no row has `time` or `aws_request_id` (the old formatter's keys);
   5. if the run posted, "Telegram message sent" has `event` = `telegram.message_sent`, and the dashboard's posts tile counts it.

If the run posted nothing, items 1 to 4 prove the shape, and item 5 waits for the first staging run that posts. The
ambiguous-stories filter is not exercised here. It is accepted because it reads the same `message` key in the same
way as the posts filter.

Note any key on the lines that the contract does not list and the runtime evidently owns. Report it, so that it can
join the drift check's forbidden names in a later change.

**If any item fails**: decline the production approval. Then open a revert pull request of the U2 merge. Its pipeline
run puts staging back on the old format; decline that run's production approval too, since production never had U2.
The fix comes in a new pull request.
