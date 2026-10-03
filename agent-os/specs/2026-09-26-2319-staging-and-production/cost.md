# Staging and Production Cost Estimate

Recorded 2026-10-02 with `make cost` (Infracost, us-east-2 list prices, no free tier). The three
production columns are the Phase 1.2 estimate, unchanged: this spec adds no resource to production.

## Monthly cost

| Resource | 1 office | 6 offices | All US (122) | Staging |
|---|---:|---:|---:|---:|
| `aws_s3_bucket.archive` | $0.0565 | $0.3392 | $6.8971 | $0.0565 |
| `aws_lambda_function.bot` | $0.0371 | $0.2223 | $4.5209 | $0.0371 |
| `aws_dynamodb_table.state` | $0.0074 | $0.0446 | $1.8078 | $0.0074 |
| `aws_cloudwatch_log_group.lambda` | $0.0015 | $0.0089 | $0.1809 | $0.0015 |
| 5 CloudWatch alarms ($0.10 each) | $0.5000 | $0.5000 | $0.5000 | $0.5000 |
| `aws_dynamodb_table.posted` (MVP, idle) | $0.0000 | $0.0000 | $0.0000 | not created |
| **Total** | **$0.60** | **$1.12** | **$13.91** | **$0.60** |

## What staging costs

- **Staging is priced as a worst case: the schedule stays on.** Staging's schedule can be started
  and paused (`make start` / `make pause`), and it will be left running for soak tests, perhaps
  permanently. So its column is production's one-office usage at the same `rate(15 minutes)`, with
  all five alarms. A paused staging has the same five alarms ($0.50: they exist while paused,
  with their actions switched off) and almost no usage.
- **No budget and no `posted` table.** Both are production-only (`infra/environments`).
- **Real cost is about $0.** The account then has 10 alarms (5 production, 5 staging), exactly
  CloudWatch's 10 free, so the figure above is list price and the worst case. The next alarm
  added anywhere in the account costs $0.10 a month.
- **The $5 account budget holds**, with no change. Staging adds $0.60 of list-price spend at most.
- **Not priced by Infracost:** the EventBridge schedule (free up to 14M invocations), SNS (alarm
  emails, inside the free 1,000) and data transfer out (about 0.2 GB a month at one office).

## Inputs

Identical to production at one office, from `scripts/infracost_usage.py`; staging's posts go to a
private test channel but are the same size and rate. The scenario differs only in leaving out the
production-only `posted` table.
