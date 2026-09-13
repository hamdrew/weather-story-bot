# NWS Weather Story Bot

Posts new [NWS Weather Stories](https://www.weather.gov/mkx/weatherstory) to a Telegram channel, so they show up on your phone without having to check weather.gov.

## What it does

Every 15 minutes, an AWS Lambda:

1. Fetches the active stories for each configured office from `api.weather.gov/offices/{office}/weatherstories`.
2. Skips stories it has already posted. It tracks them in DynamoDB by office and image ID.
3. For each new story, and each story whose `updateTime` changed:
   - downloads the image
   - archives the image and raw metadata to S3
   - posts the image and description to that office's Telegram channel (updates get a "🔄 Updated:" prefix)

A story is recorded as posted only after Telegram accepts it. A failure can cause a repost, but never a missed story. If any story fails, the invocation reports an error, and the next scheduled run tries again.

```
EventBridge Scheduler ──► Lambda ──► api.weather.gov
                            ├──► S3 archive   stories/{office}/{YYYY}/{MM}/{DD}/{image_id}/{updateTime}.{png,json}
                            ├──► Telegram     sendPhoto (falls back to sendDocument)
                            └──► DynamoDB     weather-story-bot-posted
```

## One-time setup

Prerequisites: [uv](https://docs.astral.sh/uv/), Terraform ≥ 1.11, and the AWS CLI with credentials for the target account.

1. **Create the bot.** Message [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token.
2. **Create the channel.** Create a private Telegram channel and add the bot as an administrator that can post messages.
3. **Get the channel's chat ID.** Post any message in the channel, then run:
   ```sh
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | grep -o '"chat":{"id":-100[0-9]*'
   ```
   The ID starts with `-100`.
4. **Store the token in SSM.** Use Parameter Store, not Terraform, so the token never ends up in Terraform state:
   ```sh
   read -rs TELEGRAM_TOKEN
   aws ssm put-parameter --region us-east-1 --type SecureString \
     --name /weather-story-bot/telegram-token --value "$TELEGRAM_TOKEN"
   ```
5. **Create a Terraform state bucket** (skip this if you already have one):
   ```sh
   aws s3api create-bucket --bucket <your-tf-state-bucket> --region us-east-1
   aws s3api put-bucket-versioning --bucket <your-tf-state-bucket> \
     --versioning-configuration Status=Enabled
   ```
6. **Configure Terraform.** Both copies are gitignored:
   ```sh
   cp infra/backend.hcl.example infra/backend.hcl             # set the bucket name
   cp infra/terraform.tfvars.example infra/terraform.tfvars   # set chat_id, nws_user_agent and alert_email
   terraform -chdir=infra init -backend-config=backend.hcl
   ```
   NWS asks API clients to send a `User-Agent` that identifies the app and gives a way to contact you, e.g. `weather-story-bot (you@example.com)`.

## Local development

```sh
make test     # unit tests (respx + moto; no network, no AWS)
make coverage # tests with a coverage report (terminal + htmlcov/index.html)
make lint     # ruff + terraform fmt
make format   # apply ruff/terraform formatting

# Print the captions that would be posted for live stories (no AWS, no Telegram):
NWS_USER_AGENT="weather-story-bot (you@example.com)" \
  uv run python -m weather_story_bot --dry-run --office MKX
```

The dry run also loads a `.env` file from the project root, if present, so you don't have to
export variables by hand:

```sh
cp .env.example .env   # set NWS_USER_AGENT (gitignored)
uv run python -m weather_story_bot --dry-run --office MKX
```

Variables already set in your shell take precedence over `.env`.

To see how the posts actually render, add `--send-telegram`. It downloads each story image and
posts it to a test channel through the same `post_story` code the Lambda uses. It doesn't touch
DynamoDB or S3, so it posts every active story on each run. Set these in `.env` or your shell,
and add the bot to the channel as an admin that can post:

```sh
TELEGRAM_BOT_TOKEN="123456:ABC-your-bot-token"
TELEGRAM_CHAT_ID="-1001234567890"   # or "@your_test_channel"

uv run python -m weather_story_bot --dry-run --office MKX --send-telegram
```

## Deploy

```sh
make build    # vendors deps for python3.13/arm64 into build/lambda.zip
make plan     # optional: review changes
make deploy   # terraform apply
```

Smoke test:

```sh
aws lambda invoke --function-name weather-story-bot out.json && cat out.json
# {"MKX": {"posted": 2, "updated": 0, "skipped": 0, "failed": 0}}
```

Invoke it again and every story should show as `skipped`. Logs are structured JSON in the CloudWatch log group `/aws/lambda/weather-story-bot`.

## Alerts

CloudWatch alarms email `alert_email` through the SNS topic `weather-story-bot-alerts`, and send a second email when the alarm returns to OK. Alerts never go through Telegram, because Telegram might be what's broken. Separately, an AWS Budget emails `alert_email` directly when spend runs high.

**After the first deploy**, open the "AWS Notification - Subscription Confirmation" email and click the link. Until you do, SNS drops every alarm email. To check:

```sh
aws sns list-subscriptions-by-topic \
  --topic-arn "$(terraform -chdir=infra output -raw alert_topic_arn)"   # must not say PendingConfirmation
```

**Make the alerts notify on your phone.** In Gmail, add a filter for the alert senders:

- SNS alarm emails come from `no-reply@sns.amazonaws.com`.
- Budget emails come from an AWS address. Check the sender on the first one you receive and add it to the filter.

Set the filter to **Never send it to Spam**, **Always mark it as important**, and **Categorize as: Primary**. Then the Gmail app notifies you even if it's set to notify only for Primary or high-priority mail.

To test the whole path, force an alarm and wait for both emails (the OK email follows at the next evaluation):

```sh
aws cloudwatch set-alarm-state --alarm-name weather-story-bot-errors \
  --state-value ALARM --state-reason "test"
```

### What each alert means

| Alert | Fires when | What to check first |
|---|---|---|
| `weather-story-bot-errors` | Runs failed in 2 consecutive 15-minute periods. One flaky run doesn't alert. Any failed story or office, and any timeout, counts. | The `ERROR` lines in the log group. They name the office and story, plus the NWS, Telegram or AWS error. |
| `weather-story-bot-missed-runs` | No invocations in the last hour. | The EventBridge Scheduler schedule `weather-story-bot` is enabled, and the scheduler role can still invoke the function. |
| `weather-story-bot-quiet` | No stories posted for `quiet_alarm_days` days, even though runs aren't failing. | The `Run complete` summaries in the logs. If they show only `skipped` while weather.gov has new stories, NWS may have changed the API. |
| `weather-story-bot-repost-loop` | More than `repost_alarm_max_posts` stories posted in 3 hours. | The Telegram channel for duplicates, and `Telegram message sent` log lines for the same `image_filename` again and again, without a matching `Story posted` line (for example, DynamoDB writes failing after each post). |
| `weather-story-bot-monthly` (budget) | Actual account spend passes 80% of `monthly_budget_usd`, or forecasted spend passes 100%. | AWS Cost Explorer, grouped by service. The budget covers the **whole account**, not just this bot. |

Each alarm email includes the same hints and a link to the log group.

`quiet` and `repost-loop` count the Telegram client's `Telegram message sent` log line through a log metric filter (`WeatherStoryBot/StoriesPosted`), so don't change that message text. It's logged as soon as Telegram accepts a message, so posts whose DynamoDB write then fails still count. Until a full day of data exists, `quiet` may show `INSUFFICIENT_DATA`.

### Tuning thresholds

The starting values are guesses until there's real posting data. Override them in `infra/terraform.tfvars` and run `make deploy`:

```hcl
monthly_budget_usd     = 5  # USD per month, whole account
quiet_alarm_days       = 2  # 1-7; CloudWatch can't look back further than 7 days
repost_alarm_max_posts = 8  # posts per 3 hours
```

If you slow the schedule down to less than once an hour, `missed-runs` will fire on every gap. Change its `period` in `infra/monitoring.tf` to match.

## Adding an office

1. Create another channel with the bot as admin, and get its chat ID (steps 2–3 above).
2. Add the office to `offices` in `infra/terraform.tfvars`. Keys are the three-letter NWS office IDs:
   ```hcl
   offices = {
     MKX = { chat_id = "-100…", name = "Milwaukee/Sullivan" }
     GRB = { chat_id = "-100…", name = "Green Bay" }
   }
   ```
3. Run `make deploy`. On its first run, the Lambda posts all of the new office's active stories.
