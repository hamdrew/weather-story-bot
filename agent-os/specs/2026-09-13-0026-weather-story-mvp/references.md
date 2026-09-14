# References for Weather Story MVP

## Similar Implementations

None. The repository had no application code when this spec was written.

## External References

### NWS API — office weather stories

- **Location:** `https://api.weather.gov/openapi.json`, operations `office_weatherstory` (`GET /offices/{officeId}/weatherstories`) and `office_weatherstory_image` (`GET /offices/{officeId}/weatherstories/download/{imageId}`)
- **Relevance:** The data source for stories and their images.
- **Key patterns:**
  - Response is `{"stories": [...]}`. Each story has `officeId`, `startTime`, `endTime`, `updateTime`, `title` (≤50 chars), `description`, `altText`, `priority`, `order` (1–7), and `download`.
  - Images are PNGs, about 1.1 MB at 1536×864.
  - Requests need a descriptive `User-Agent` header with contact info.
  - The list response is cached for about 3 minutes (`max-age=180`).
  - **Image UUIDs aren't stable.** Observed 2026-09-14: the same MKX story (identical PNG bytes, identical metadata including `updateTime`) was re-issued under a new UUID. Don't treat a new UUID alone as a new story (plan Task 12).

### NWS MKX Weather Story page

- **Location:** `https://www.weather.gov/mkx/weatherstory`
- **Relevance:** The human-readable page each Telegram caption links to.
- **Key patterns:** Not used as a data source. It reuses fixed image filenames (`/images/mkx/wxstory/Tab2FileL.png`), so images can't be told apart by URL.

### Telegram Bot API

- **Location:** `https://core.telegram.org/bots/api#sendphoto`, `#senddocument`
- **Relevance:** Delivers each story to the office channel.
- **Key patterns:**
  - Upload the photo as multipart. Photo captions are limited to 1024 characters.
  - `parse_mode=HTML` needs `<`, `>`, and `&` escaped.
  - A 429 response includes `parameters.retry_after`.
  - Photos over 10 MB, or with extreme dimensions, are rejected; `sendDocument` works as a fallback.

### CloudWatch alarms, metric filters, SNS, and Budgets

- **Location:**
  - `https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html`
  - `https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html`
  - `https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html`
  - `https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html`
  - Terraform resources: `aws_cloudwatch_metric_alarm`, `aws_cloudwatch_log_metric_filter`, `aws_sns_topic_subscription`, `aws_budgets_budget`
- **Relevance:** Failure, silent-problem, and cost alerts (plan Task 10).
- **Key patterns:**
  - Lambda's `Errors` metric counts unhandled exceptions and timeouts.
  - `treat_missing_data = "breaching"` is what makes "nothing happened" alarms work.
  - Alarms with periods of 1 hour or longer can evaluate at most 7 days.
  - JSON metric filters use `{ $.field = "value" }`.
  - SNS email subscriptions stay `PendingConfirmation` until the link is clicked.
  - CloudWatch can't publish to a topic encrypted with the AWS-managed `aws/sns` key.

### DynamoDB point-in-time recovery

- **Location:**
  - `https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery_Howitworks.html`
  - Terraform `aws_dynamodb_table` (hashicorp/aws 6.64.0), `point_in_time_recovery` block
- **Relevance:** Backups for the posted-stories table (plan Task 13).
- **Key patterns:**
  - `point_in_time_recovery { enabled, recovery_period_in_days }`, with a 1–35 day window (default 35). Enabling can take about 10 minutes.
  - Billed on table size (data plus LSIs); the window length doesn't change the price. us-east-2: $0.20 per GB-month, $0.15 per GB restored (AWS Price List, 2026-09-14).
  - A restore always creates a new table. Stream, TTL and PITR settings, tags and alarms aren't copied to it.
  - Infracost usage key: `pitr_backup_storage_gb` on `aws_dynamodb_table`.

### Infracost

- **Location:** `https://github.com/infracost/infracost` (README and `infracost-usage-example.yml`)
- **Relevance:** The `make cost` estimate (plan Task 11).
- **Key patterns:**
  - Install with `brew install infracost`, then run `infracost setup` for authentication. The CLI also reads `INFRACOST_API_KEY`.
  - `infracost breakdown --path <dir> --usage-file <file>` estimates monthly cost straight from Terraform files.
  - Usage-based costs are left out unless a usage file supplies values. The file format is `version: 0.1` with a `resource_usage:` map keyed by Terraform resource address (for example `aws_lambda_function.bot`).
  - `--sync-usage-file` writes the usage keys each resource supports into the file.
  - **CLI v2 (2.16.3) changes all of the above:** `breakdown` forwards to `scan [path]`, the usage file is set with `usage_file` in a project entry of `infracost.yml`, and `inspect --file <scan.json>` re-renders a saved result. The `resource_usage` key names are unchanged. See plan.md Task 11, "As built".
