# Dashboard and Weekly Warning Digest: Ideas

Date: 2026-09-15, written while shaping the story-updates branch. Status: ideas for a future spec
(`agent-os:shape-spec`), scheduled as **roadmap phase 2.3**, deliberately after the multi-office
work so the queries are built once against the shape they'll run on.

**Refresh "Current state" below before shaping.** Phases 1.2 through 2.2 change the log messages,
the run summary and the office count this was written against.

## Intent

Two monitoring additions: a CloudWatch dashboard for the project, and a weekly email digest of
WARNING (and ERROR) log lines.

## Current state (as of 2026-09-15)

- Lambda `weather-story-bot` runs every 15 minutes from EventBridge Scheduler in us-east-2, logging
  structured JSON to `/aws/lambda/weather-story-bot` (fields: time, level, logger, message, plus
  extras).
- SNS topic `weather-story-bot-alerts` with an email subscription. Alarms: errors, missed-runs,
  quiet, repost-loop, nws-ambiguous. Metric filters in namespace `WeatherStoryBot`: StoriesPosted
  ("Telegram message sent") and AmbiguousStories ("Ambiguous stories from NWS").
- The "Run complete" log line carries a summary: `{office: {posted, updated, skipped, rejected,
  failed}}`.
- WARNING messages today: "Telegram delete failed, old message kept", "Photo rejected, sending as
  document", "Telegram rate limited, retrying", "NWS request failed, retrying", "NWS server error,
  retrying". All are self-recovering.

## Decisions so far

- **Decided: a digest, not an alarm.** Warnings shouldn't alert immediately; they should be reviewed
  in bulk. A WARNING-count alarm only emails when its state *changes*, so warnings that keep
  happening go quiet, and the email can't say which warnings fired.
- **Decided: weekly.** A scheduled job runs a CloudWatch Logs Insights query over the last 7 days,
  counts WARNING and ERROR lines grouped by message (and office where present), and publishes a
  plain-text email to the existing SNS topic. It sends only when there was at least one match.
- **Decided: its own Lambda,** built from the same `build/lambda.zip` (for example a `digest.py`
  entry point), with its own weekly schedule, least-privilege IAM (`logs:StartQuery` and
  `logs:GetQueryResults` on the bot's log group, `sns:Publish` on the alerts topic), and its own
  failure alarm — the bot's `errors` alarm needs two consecutive 15-minute failures, which a weekly
  job never triggers. No missed-runs alarm for the digest.
- **Decided: the dashboard is for looking at, not alerting.** Terraform-managed
  (`aws_cloudwatch_dashboard`), plus saved Logs Insights queries (`aws_cloudwatch_query_definition`)
  for warnings by message and recent "Run complete" summaries.

## Open questions

- Dashboard widgets: invocations, errors, duration, StoriesPosted, AmbiguousStories, alarm status,
  Logs Insights widgets for warnings and run summaries. Which ones are actually worth it?
- Digest schedule day, time and time zone (America/Chicago?), and email format (subject line,
  top-N limit).
- How the digest code follows the standards (injected clients, client errors, retries), and how to
  test it offline. Moto's support for Logs Insights queries is limited, so consider injecting a
  fake logs client.
- Should any current WARNING drop to INFO, or rise to ERROR?
- Cost: dashboards are $3/month each beyond the free tier of 3. Confirm the account is within it,
  and update `make cost` / `infracost-usage.yml` and the README's alarm and cost sections.

## Constraints

- Personal, single-user tool. Keep it cheap and avoid overkill (AWS Config and Security Hub were
  already declined).
- boto3 stays a dev-only dependency; runtime deps must ship arm64 manylinux wheels.
- Alerts never go through Telegram.
- Ask before `make deploy`. Deploys use the MFA admin profile.
