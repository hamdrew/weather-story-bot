# Phase 1.2 Cost Estimate

Recorded 2026-09-26 with `make cost` (Infracost v2.16.3, us-east-2 list prices, no free tier).

## Monthly cost by scale

| Resource | 1 office | 6 offices | All US (122) |
|---|---:|---:|---:|
| `aws_s3_bucket.archive` | $0.0565 | $0.3392 | $6.8971 |
| `aws_lambda_function.bot` | $0.0371 | $0.2223 | $4.5209 |
| `aws_dynamodb_table.state` | $0.0074 | $0.0446 | $1.8078 |
| `aws_cloudwatch_log_group.lambda` | $0.0015 | $0.0089 | $0.1809 |
| 5 CloudWatch alarms ($0.10 each) | $0.5000 | $0.5000 | $0.5000 |
| `aws_dynamodb_table.posted` (MVP, idle) | $0.0000 | $0.0000 | $0.0000 |
| **Total** | **$0.60** | **$1.12** | **$13.91** |

6 offices is MKX, GRB, ARX, DLH, MPX and LOT. All US is every NWS Weather Forecast Office.
Every scenario is priced as **one Lambda invocation per office per run**, the Phase 2.2 design,
at the measured single-office run time.

## What scales and what doesn't

- **Fixed (O(1) in offices):** the five alarms, $0.50 of the $0.60 at one office. They are why
  a single office looks expensive per office and why 6 offices cost less than double.
- **Linear in offices:** everything else. At 122 offices the fixed part is under 4% of the bill.
- **The archive dominates at scale.** Each office adds about 2.4 GB of PNGs a year (125 posts a
  month at 1.64 MB), and the archive is kept forever, so S3 grows every month, like the state table's
  storage but far faster. The figure is after 12 months, so year two costs about twice as much for S3. That is
  where a storage-class decision (e.g. Glacier Instant Retrieval for older years) would pay off first.
- **Lambda is mostly duration.** 3.8 s at 256 MB per office-run; the per-request charge for
  351,360 invocations is $0.07 of the $4.52. In practice the free tier (400,000 GB-s a month)
  covers all 122 offices (about 334,000 GB-s).
- **DynamoDB writes are the new Phase 1.2 cost** and stay small: about 10,750 writes per office a
  month, $0.82 a month for all 122 offices. Storage and PITR at 122 offices (about 2 GB after a
  year, mostly `RUN#` records) add about $0.90.
- **Not priced by Infracost:** the EventBridge schedule (free up to 14M invocations; 351,360 at
  122 offices), SNS (alarm emails, inside the free 1,000), and data transfer out: each post
  uploads its image to Telegram, about 24 GB a month at 122 offices (122 × 125 × 1.64 MB). At the
  $0.09/GB list price that's about $2.20, which would be the third-largest line. It sits inside
  the 100 GB a month of free egress, but it's the first free allowance scale would use up.

Per-office invocation isn't just the Phase 2.2 plan, it's required at this scale: at 3.8 s an
office, one invocation for all 122 would take about 460 s, past the 300 s Lambda timeout.

## Delta from before Phase 1.2

Baseline: commit `0833e30` (before Stage 1) with its own usage file, re-priced with the same
Infracost: **$0.54 a month**. Now, for the same one office: **$0.60** (+$0.07).

| Resource | Before | After | Why |
|---|---:|---:|---|
| DynamoDB | $0.0008 | $0.0074 | **Phase 1.2:** lease take and release, `RUN#`, `last_seen_at`, ledger events |
| S3 | $0.0190 | $0.0565 | Re-measured: 125 posts a month (was 60), 1.64 MB images (was 1.1) |
| Lambda | $0.0150 | $0.0371 | Re-measured: 3.8 s average run (was 1.5 s) |
| Logs | $0.0011 | $0.0015 | Re-measured log volume |

Phase 1.2's own cost is the DynamoDB line: **+$0.007 a month per office**, as predicted. The
rest corrects assumptions that were guesses before the bot had run.

## Per office per month (the inputs)

Measured on MKX from 2026-09-13 to 2026-09-26, unless marked otherwise. The constants live in
`scripts/infracost_usage.py`.

| Input | Value | Source |
|---|---|---|
| Runs | 2,880 | `rate(15 minutes)` |
| Active stories per run | 2 | estimate (MKX lists 1-3) |
| Posts (new + updated) | 125 | 58 archived in ~14 days |
| Updates | 10 | 58 posts over 54 distinct stories |
| Rejected events | 288 | allowance: one ambiguous story for 3 days (none seen so far) |
| Run time | 3.8 s | Lambda `Duration` average, 2026-09-19 to 09-26 |
| Image size | 1.64 MB | archive average |

Writes, 1 WRU each (all items < 1 KB): lease 2 × runs, `RUN#` 1 × runs, `last_seen_at` at most
hourly per unchanged story (1,440) plus once
after each post, since the repost clears it (125), 2 per post (story item + event), 1 per update (deletion
event), 1 per rejection. Reads: one strongly consistent `GetItem` per active story per run
(5,760 RRU).
