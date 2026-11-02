# Requirements: Seeing the bot's health, its warnings and its errors

Sources: the intent statement (`ideation/intent-capture/intent-statement.md`), the scope document
(`ideation/scope-definition/scope-document.md`), the initiative brief and the wireframes from Ideation, the
answers in `requirements-analysis-questions.md` (Q1 to Q9), and the code knowledge base for
`weather-story-bot` (`business-overview.md`, `architecture.md`, `code-structure.md`) plus a read of
`src/weather_story_bot/` and `infra/monitoring.tf`.

## Intent Analysis

The owner wants to know at a glance whether the weather-story bot is healthy, to see every warning and
error it records, to be emailed when any warning or error happens, and to trust that no alarm silently
stops working because someone reworded a log message. They also want a full review of the bot's logging,
and to learn observability on AWS while doing it.

This is an enhancement to an existing system: a Python 3.13 Lambda that posts NWS Weather Stories to
Telegram, with Terraform-managed CloudWatch alarms emailing an SNS alerts topic. It touches the logging in
every module, the Terraform monitoring, and the tests, in both environments (staging and production).

What exists today, which these requirements build on:

- Seven WARNING-level log kinds and seven ERROR-level kinds (one `Ambiguous stories from NWS`, six caught failures logged with a stack trace).
- Caught failures add to the run's `failed` count; `lambda_handler` then raises `ProcessingError`, so the run fails. The `errors` alarm only goes into alarm after failed runs in two 15-minute periods in a row, so one isolated failed run emails nobody. That gap is the main reason for FR4.
- Five alarms: `errors`, `missed-runs`, `quiet`, `repost-loop`, `nws-ambiguous`. Three of them (`quiet`, `repost-loop`, `nws-ambiguous`) depend on metric filters that match exact log messages (`Telegram message sent`, `Ambiguous stories from NWS`).
- Logs are kept 30 days. `mise run start` / `mise run pause` toggle the alarms listed in Terraform's `alarm_names`.

## Functional Requirements

### FR1 Dashboard

One CloudWatch dashboard per environment shows the bot's health, warnings and errors on one page, top to
bottom. *Origin: intent (health view, Q15, Q16), scope, Rough Mockups Q1 to Q8.*

- **FR1.1** At the top, a verdict reads exactly one of `HEALTHY`, `NOT HEALTHY` or `UNKNOWN`. It mirrors the alarms' state right now, whatever time range the dashboard shows:
  - `UNKNOWN` when the bot should have run but no data came in: the `missed-runs` alarm is in ALARM (no invocation in its last one-hour period), or any health-signal alarm is in INSUFFICIENT_DATA. It wins over the other two, because the other signals can't be trusted without data.
  - `NOT HEALTHY` when any other health signal (FR1.3) is off, or the error-log alarm (FR4) is in ALARM.
  - `HEALTHY` otherwise. Warnings never change the verdict.
- **FR1.2** The verdict area lists every health signal that is off, the error kinds that made it `NOT HEALTHY`, and the total counts of errors and of warnings in the dashboard's time range.
- **FR1.3** Below the verdict, one tile per health signal, each with its current value, a trend, and its alarm state. The health signals are the four today's alarms watch (Q5). A signal is off while its alarm is in ALARM, using today's thresholds unchanged:
  - runs on schedule: `missed-runs`, off when there was no invocation in the last hour;
  - no failed runs: `errors`, off after failed runs in two 15-minute periods in a row;
  - a story posted recently: `quiet`, off when nothing was posted for `quiet_alarm_days` days;
  - no repost loop: `repost-loop`, off when more than `repost_alarm_max_posts` posts went out in 3 hours.
- **FR1.4** An errors-and-warnings area shows:
  - a count by kind, with each kind's level (error or warning);
  - a list of the most recent entries, newest first, each with its time, level, kind and detail;
  - both over the same window, which is the dashboard's own time range (default 7 days, at most the 30-day log retention) (Q6);
  - a line saying how many more entries the window holds when the list is cut short (the list's length is set in design).
- **FR1.5** A detail area with one chart per health signal (FR1.3), drawing the same metric its alarm watches over the dashboard's time range, with the alarm threshold shown on the chart.
- **FR1.6** At phone width the page reads in one column in the same order, and the recent list keeps time, level and kind visible.
- **FR1.7** Each area states in words when it has nothing to show (no entries in the window) or no data (the `UNKNOWN` case), rather than showing an empty chart.
- **FR1.8** The page carries no environment label; each environment's dashboard has its own name.

### FR2 Warning and error coverage

*Origin: intent ("none missed", Q10, Q16), Q1, Q3.*

- **FR2.1** Every WARNING the bot logs is a warning kind on the dashboard: the seven logged today (`NWS request failed, retrying`, `NWS server error, retrying`, `Telegram rate limited, retrying`, `Photo rejected, sending as document`, `Telegram delete failed, old message kept`, `Office lease release failed`, `History write failed`) and any added later, with no change to the dashboard needed.
- **FR2.2** Every ERROR (or CRITICAL) the bot logs is an error kind on the dashboard: `Ambiguous stories from NWS`, the six caught failures logged today, and any added later, with no change to the dashboard needed. Lambda run failures come from the Lambda `Errors` metric rather than a log line; they show as the "no failed runs" signal (FR1.3) and stay with the existing `errors` alarm.
- **FR2.4** "Logged by the bot" means any record at WARNING or above written to the Lambda's log group by any Python logger in the function, the bot's own (`weather_story_bot`) and third-party ones (for example httpx or botocore). Records the Lambda runtime writes outside Python logging (for example a timeout line) are covered by the Lambda `Errors` metric, not by FR2.
- **FR2.3** Each warning and error kind has a stable identity that does not depend on the wording of its log message, so rewording a message keeps it the same kind.

### FR3 Warning alarm

Any warning emails the owner through the existing alerts topic, retries that then succeed included.
*Origin: Q17 (Intent Capture), Q2.*

- **FR3.1** A new alarm goes into ALARM when one or more warnings of any kind (FR2.1) happen in a 15-minute period (threshold 1, one period, missing data not breaching), and emails the owner.
- **FR3.2** Like the existing alarms, it emails on going into ALARM and on returning to OK, not once per warning. A warning that lands while the alarm is already in ALARM sends no extra email; it shows on the dashboard. The owner accepted this (review R-01), so "none missed" by email means every warning falls in a period the alarm was in ALARM for.

### FR4 Error-log alarm

Any ERROR the bot logs emails the owner, alongside the existing failed-run alarm. *Origin: Q3, Q9.* This
replaces the intent statement's "errors get no new notification of their own": Q9 was decided after it.

- **FR4.1** A new alarm goes into ALARM when one or more errors of any logged kind (FR2.2) happen in a 15-minute period (threshold 1, one period, missing data not breaching), and emails the owner; it does not depend on the run failing. It emails on state changes, the same way as FR3.2.
- **FR4.2** The existing `errors` (failed run) and `nws-ambiguous` alarms keep working; whether `nws-ambiguous` stays a separate alarm is left to design, as long as an ambiguous listing still emails the owner.

### FR5 Sturdy alarms

*Origin: intent (Q1, Q3, Q13), scope.*

- **FR5.1** No alarm and no dashboard widget depends on the exact wording of a log message. The three that do today (`quiet`, `repost-loop`, `nws-ambiguous`) move to a signal that survives rewording.
- **FR5.2** An automated, offline test fails whenever a change would leave an alarm or a dashboard widget without its signal: for example renaming or removing what a metric filter, metric or query reads.
- **FR5.3** The existing alarms keep their current thresholds, windows and email behaviour unless a requirement here changes them.
- **FR5.4** Every new alarm joins the set `mise run start` and `mise run pause` toggle. *Origin: existing system (`alarm_names` in `infra/monitoring.tf`).*

### FR6 Logging review

*Origin: scope (full logging review, broader tidy-up), Q8.*

- **FR6.1** A written review in the repository covers every log call in `src/weather_story_bot/`: its level, message, fields, and whether it is consistent with the others, with a finding and a decision for each problem found.
- **FR6.2** The review checks that no log line carries a secret (for example the Telegram token) or a full request body. *Origin: project rule on the Telegram token.*
- **FR6.3** The code changes the review decides on are made: consistent levels and fields across modules (the broader tidy-up), beyond what FR2 to FR5 need.

## Non-Functional Requirements

- **NFR1 Cost**: the added AWS cost (dashboards, metrics, alarms, queries) stays at or under $5 a month across both environments. Checked by a cost estimate in design from AWS pricing, where log query cost is estimated from the bytes scanned at the default 7-day window and a stated number of dashboard views a week, then by the first month's bill. *Origin: intent (Q9).*
- **NFR2 Glance time**: the verdict and the totals (FR1.1, FR1.2) are visible without scrolling in a 1440 x 900 browser window and in a 390 px wide phone browser, so the owner can tell whether the bot is healthy in under a minute. Checked by opening the deployed staging dashboard at both sizes. *Origin: intent (Q3).*
- **NFR3 Time zone**: times shown to the owner on the dashboard are in America/Chicago. *Origin: project rule.*
- **NFR4 Offline tests**: every new or changed test runs offline (respx, moto, Terraform mock provider) and passes in the `checks` job; line coverage stays at or above 80%. *Origin: team testing posture.*
- **NFR5 No regressions**: what the bot posts to Telegram, and how, does not change; the existing test suites stay green. *Origin: intent (Q5).*
- **NFR6 Delivery**: the work reaches production through the pipeline, one revertible pull request per slice, each saying what to watch after merge. *Origin: team practices.*

## Constraints

- AWS only; no third-party or paid monitoring services outside AWS.
- Terraform in `infra/`, one root for both environments; environment differences go through variables and `local.production`.
- httpx stays the only runtime dependency; boto3 stays dev-only.
- Production deploys are pipeline-only; `deploy`, `start`, `pause` and `bootstrap-deploy` are the owner's to run.
- Logs are kept 30 days, which bounds the dashboard window.

## Assumptions

- **A1**: The new alarms email through the existing alerts topic in both environments, as the current alarms do; staging's alerts reach the owner too. *Reason: the existing alarms work that way.*
- **A2**: The $5 cap covers both environments together. *Reason: the owner pays for both.*

## Out of Scope

- A weekly digest.
- Dashboards for offices the bot doesn't cover yet.
- Any change to what the bot posts to Telegram, or how.
- Third-party or paid monitoring outside AWS.
- New notification channels other than the existing email alerts.
- Detecting a stale dashboard beyond the `missed-runs` alarm and the `UNKNOWN` verdict (Q7).
- Keeping logs longer than 30 days.

## Open Questions

- How the dashboard shows times in America/Chicago (NFR3): the console's time zone setting, or formatting inside the widgets. Left to design.
- Whether the "unusual" patterns nothing records today (slow runs, NWS sending no stories) become new warnings is a logging-review decision (FR6.1); once one is logged at WARNING it is covered by FR2.1 and FR3.
