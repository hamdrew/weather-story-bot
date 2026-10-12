# Deploy from GitHub Actions Cost Estimate

Recorded 2026-10-09 with `make cost` (Infracost, us-east-2 list prices, no free tier), for Stage 2
(Tasks 5 and 6), the only stage that adds a resource. The production and staging columns are
unchanged from the staging-and-production spec: this phase adds nothing to either environment.

## Monthly cost

| Resource | 1 office | 6 offices | All US (122) | Staging | Bootstrap |
|---|---:|---:|---:|---:|---:|
| `aws_s3_bucket.archive` | $0.0565 | $0.3392 | $6.8971 | $0.0565 | |
| `aws_lambda_function.bot` | $0.0371 | $0.2223 | $4.5209 | $0.0371 | |
| `aws_dynamodb_table.state` | $0.0074 | $0.0446 | $1.8078 | $0.0074 | |
| `aws_cloudwatch_log_group.lambda` | $0.0015 | $0.0089 | $0.1809 | $0.0015 | |
| 5 CloudWatch alarms ($0.10 each) | $0.5000 | $0.5000 | $0.5000 | $0.5000 | |
| `aws_s3_bucket.artifacts` | | | | | $0.0000 |
| **Total** | **$0.60** | **$1.12** | **$13.91** | **$0.60** | **$0.00** |

## What the bootstrap stack costs

- **IAM roles, policies and the OIDC provider are free.** So is GitHub Actions on a public repo.
- **The artifacts bucket is cents at most, and Infracost prices it at $0.0000.** It holds one zip
  per distinct build (about 10 MB, so S3 Standard storage is $0.00023 per zip-month) and one saved
  production plan per pipeline run. Lifecycle rules expire zips after 90 days, plans after 14 and
  noncurrent versions after 7, so it stops growing: a few dozen objects, under 1 GB, well below
  $0.03 a month. Requests (one PUT per deploy, a handful of GETs) are fractions of a cent.
- **Nothing here scales with offices.** One bucket, four roles and two boundaries, whether the bot
  watches 1 office or 122 (`infra/budget`).
- **The $5 account budget holds**, with no change.

## Not priced by Infracost

- CloudTrail data events are off, so S3 object-level calls cost nothing extra.
- Data transfer: a zip is uploaded from a runner and read by Lambda in the same region.
