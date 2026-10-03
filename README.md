# NWS Weather Story Bot

Posts new [NWS Weather Stories](https://www.weather.gov/mkx/weatherstory) to a Telegram channel, so they show up on your phone without having to check weather.gov.

## What it does

Every 15 minutes, an AWS Lambda:

1. Fetches the active stories for each configured office from `api.weather.gov/offices/{office}/weatherstories`.
2. Ignores stories past their `endTime`.
3. Downloads every remaining story's image, and rejects any stories that share an image ID, a title and start time, or identical image bytes. None of them are posted; the run logs one `Ambiguous stories from NWS` error and the `nws-ambiguous` alarm emails you.
4. For each other story, identified by its title and start time (NWS re-issues stories under new image IDs, even with `updateTime` set to 1970):
   - skips it if its image and description match what was last posted for it
   - archives the image and raw metadata to S3, in one folder per story with one file pair per distinct image and description
   - posts the image and description to that office's Telegram channel, logging `Story posted`. A changed story gets a "🔄 Updated:" prefix, and its previous message is then deleted.

A story is recorded as posted only after Telegram accepts it, and an old message is deleted only after its replacement is recorded. A failure can cause a repost, but never a missed story. Telegram won't let bots delete messages older than 48 hours, so an update to an older story leaves both messages, and logs `Telegram delete failed, old message kept`. If any story fails, the invocation reports an error, and the next scheduled run tries again. Rejected stories don't fail the run.

```
EventBridge Scheduler ──► Lambda ──► api.weather.gov
                            ├──► S3 archive   stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title}-{story key}/{fingerprint}.{png,json}
                            ├──► Telegram     sendPhoto (falls back to sendDocument), deleteMessage
                            └──► DynamoDB     weather-story-bot-state (one STORY#<start>#<title+start hash> item per story, under OFFICE#<id>)
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
4. **Store the token in SSM.** Use Parameter Store, not Terraform, so the token never ends up in Terraform state. Terraform doesn't manage the parameter, so it doesn't get the `Environment` tag the other resources carry; tag it here:
   ```sh
   read -rs TELEGRAM_TOKEN
   aws ssm put-parameter --region us-east-2 --type SecureString \
     --name /weather-story-bot/telegram-token --value "$TELEGRAM_TOKEN" \
     --tags Key=Environment,Value=production
   ```
   `--tags` only works when creating the parameter; it can't be combined with `--overwrite`. Rotating the token with `--overwrite` keeps the tag. To tag a parameter that already exists:
   ```sh
   aws ssm add-tags-to-resource --region us-east-2 --resource-type Parameter \
     --resource-id /weather-story-bot/telegram-token --tags Key=Environment,Value=production
   ```
5. **Create a Terraform state bucket** (skip this if you already have one):
   ```sh
   aws s3api create-bucket --bucket <your-tf-state-bucket> --region us-east-2 \
     --create-bucket-configuration LocationConstraint=us-east-2
   aws s3api put-bucket-versioning --bucket <your-tf-state-bucket> --region us-east-2 \
     --versioning-configuration Status=Enabled
   ```
6. **Configure Terraform.** Each environment has a backend config and a var file in `infra/envs/`. Both copies are gitignored:
   ```sh
   cp infra/envs/production.backend.hcl.example infra/envs/production.backend.hcl   # set the bucket name
   cp infra/envs/production.tfvars.example infra/envs/production.tfvars             # set chat_id, nws_user_agent and alert_email
   ```
   `make plan ENV=production` runs `terraform init` itself, in production's own data dir (`infra/.terraform-production/`). There's no `terraform.tfvars`: Terraform loads that automatically, so any variable an environment's file left out would silently take production's value.
   NWS asks API clients to send a `User-Agent` that identifies the app and gives a way to contact you, e.g. `weather-story-bot (you@example.com)`.

## Local development

```sh
make test     # unit tests (respx + moto; no network, no AWS)
make coverage # tests with a coverage report (terminal + htmlcov/index.html)
make lint     # ruff + terraform fmt
make format   # apply ruff/terraform formatting

# Print each live story's decision beside its caption (read-only: no AWS, no Telegram):
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

## Deploy

```sh
make build                   # vendors deps for python3.13/arm64 into build/lambda.zip
make plan ENV=production     # review changes; saves them to infra/deploy-production.tfplan
make deploy ENV=production   # applies exactly that saved plan, then deletes it
```

`ENV` (`production` or `staging`) is required and selects the backend config, var file, data dir and plan file together. `make check-plan ENV=production` fails unless the saved plan only moves resources, adds the `Environment` tag and enables the archive bucket's ABAC (Phase 2.0's first production deploy). The Lambda's role policy may also show `policy = (known after apply)`: its policy document takes ARNs from resources that are being retagged, so Terraform reads it at apply. The check passes that only when the document's statements match the live policy exactly.

To run other Terraform commands, point them at the same environment's data dir:

```sh
TF_DATA_DIR=.terraform-production terraform -chdir=infra output
```

Smoke test:

```sh
aws lambda invoke --function-name weather-story-bot out.json && cat out.json
# {"MKX": {"posted": 2, "updated": 0, "skipped": 0, "rejected": 0, "failed": 0}}
```

Invoke it again and every story should show as `skipped`. Logs are structured JSON in the CloudWatch log group `/aws/lambda/weather-story-bot`.

## Staging

Staging is where real posts get watched: its own bot, a private channel, its own state and archive, and a schedule that starts off. Create it once:

1. **Bot and channel.** Do [One-time setup](#one-time-setup) steps 1-3 again with a second bot, in a private channel whose only admin is the staging bot. Never make it an admin of a public channel.
2. **Token.** Store it under staging's own name, tagged `staging` (the Lambda role's tag condition reads the tag; `--tags` can't be combined with `--overwrite`):
   ```sh
   read -rs TELEGRAM_TOKEN
   aws ssm put-parameter --region us-east-2 --type SecureString \
     --name /weather-story-bot-staging/telegram-token --value "$TELEGRAM_TOKEN" \
     --tags Key=Environment,Value=staging
   ```
3. **Configure Terraform.** Copy the staging examples and fill them in (state bucket, the private channel's `chat_id`, `nws_user_agent`, `alert_email`):
   ```sh
   cp infra/envs/staging.backend.hcl.example infra/envs/staging.backend.hcl
   cp infra/envs/staging.tfvars.example infra/envs/staging.tfvars
   ```
4. **Deploy.** The plan should create only `-staging` resources, with no budget, the schedule `DISABLED` and all five alarms' actions off:
   ```sh
   make build
   make plan ENV=staging
   make deploy ENV=staging
   ```
   Then confirm the subscription email for the `weather-story-bot-staging-alerts` topic.
5. **Start it.** The first run fires immediately and posts MKX's active stories to the private channel, then it runs every 15 minutes. Wait for the next run, which should log every story as `skipped`, then pause it:
   ```sh
   make start ENV=staging
   make pause ENV=staging
   ```

## Starting and pausing an environment

Every environment is created paused: a `DISABLED` schedule and alarms whose actions are off. `make start ENV=<env>` enables the schedule and the alarm actions, and `make pause ENV=<env>` disables both. Both ask for your MFA code (the `weather-deploy` profile Terraform uses), so run them in a terminal. `scripts/set_run_state.py` does the work and does nothing without `--apply`, which the make targets pass. It is idempotent, and it reads the schedule and alarm names from the environment's Terraform outputs, so deploy an environment before you start it.

- Terraform ignores the schedule's `state` and each alarm's `actions_enabled` after creating them, so `make deploy` never undoes a start or a pause. That includes production, whose schedule and alarms stay as they are: `make pause ENV=production` is how you stop it, never a Terraform change.
- Pausing keeps the alarms. `missed-runs` and `quiet` treat missing data as breaching, so they sit in ALARM while paused, without emailing. Starting re-enables their actions, and the first runs bring them back to OK, which sends an OK email.

## Alerts

CloudWatch alarms email `alert_email` through the SNS topic `weather-story-bot-alerts`, and send a second email when the alarm returns to OK. Alerts never go through Telegram, because Telegram might be what's broken. Separately, an AWS Budget emails `alert_email` directly when spend runs high.

**After the first deploy**, open the "AWS Notification - Subscription Confirmation" email and click the link. Until you do, SNS drops every alarm email. To check:

```sh
aws sns list-subscriptions-by-topic \
  --topic-arn "$(TF_DATA_DIR=.terraform-production terraform -chdir=infra output -raw alert_topic_arn)"   # must not say PendingConfirmation
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
| `weather-story-bot-nws-ambiguous` | NWS listed active stories that share an image ID, a title and start time, or an identical image, so the bot skipped all of them. Fires on the first run that sees it. | The `Ambiguous stories from NWS` log lines: `stories` lists each rejected story's `image_id`, `title` and `reasons`. Usually NWS fixes its data within a run or two, and the OK email follows. |
| `weather-story-bot-monthly` (budget) | Actual account spend passes 80% of `monthly_budget_usd`, or forecasted spend passes 100%. | AWS Cost Explorer, grouped by service. The budget covers the **whole account**, not just this bot. |

Each alarm email includes the same hints and a link to the log group.

Staging (`weather-story-bot-staging-*`, on its own `weather-story-bot-staging-alerts` topic) has the same five alarms. Every environment's alarms are created with their actions off and are switched on and off with the schedule (`make start` / `make pause`), so a paused staging doesn't email about the idleness itself. Staging's metrics use the `WeatherStoryBot/staging` namespace, so its posts never count toward production's `quiet` and `repost-loop`. The budget is production-only.

`quiet` and `repost-loop` count the Telegram client's `Telegram message sent` log line through a log metric filter (`WeatherStoryBot/StoriesPosted`), so don't change that message text. It's logged as soon as Telegram accepts a message, so posts whose DynamoDB write then fails still count. "Updated" reposts count too. Until a full day of data exists, `quiet` may show `INSUFFICIENT_DATA`. `nws-ambiguous` counts the handler's `Ambiguous stories from NWS` line (`WeatherStoryBot/AmbiguousStories`), so don't change that message text either.

### Tuning thresholds

The starting values are guesses until there's real posting data. Override them in `infra/envs/production.tfvars` and run `make plan ENV=production && make deploy ENV=production`:

```hcl
monthly_budget_usd     = 5  # USD per month, whole account
quiet_alarm_days       = 2  # 1-7; CloudWatch can't look back further than 7 days
repost_alarm_max_posts = 8  # posts per 3 hours
```

If you slow the schedule down to less than once an hour, `missed-runs` will fire on every gap. Change its `period` in `infra/monitoring.tf` to match.

## Cost estimate

`make cost` estimates the monthly AWS cost of everything in `infra/` with [Infracost](https://www.infracost.io/). It reads the Terraform files directly, so it needs no Terraform plan and no AWS credentials. It's for running by hand, not before deploys or in CI.

One-time setup:

```sh
brew install infracost
infracost auth login   # opens a browser; the free account's credentials stay in Infracost's local config
infracost doctor       # checks that auth works
```

Then:

```sh
make cost
```

It prices `infra/` for four scenarios side by side: **1 office** (MKX today), **6 offices** (Wisconsin and its neighbours), **all 122** NWS forecast offices and **staging** (one office with the schedule left on, the worst case). Each column shows every costed resource at full precision, with a total at the bottom. At the committed estimates that's about $0.60, $1.12, $13.91 and $0.60 a month. The full scan result is saved to `build/infracost.json`. Infracost's own tables round to whole dollars, which would show `$0` for most of this, so `make cost` prints its own table.

The production scenarios assume one Lambda invocation per office per run, the design offices are moving to. Infracost doesn't price the EventBridge schedule, which is free up to 14 million invocations a month (about 350,000 for all 122 offices), or data transfer out: each post uploads its image to Telegram, about 24 GB a month for all 122 offices, inside the 100 GB of free egress (about $2.20 at list price).

**The estimate does not subtract the AWS free tier.** Every request, GB-second and GB is priced at list price, so the real bill can be lower.

Infracost also lists FinOps suggestions (such as S3 lifecycle rules). To see them:

```sh
infracost inspect --file build/infracost.json --failing
```

### Updating the usage assumptions

Almost everything here is billed by usage, which Infracost can't read from Terraform. `scripts/infracost_usage.py` holds the monthly usage of one office (runs, stories, posts, run time, image size), with a comment on each value saying where it came from. `make cost` multiplies those rates out into one usage file per scenario in `build/`, and `infracost.yml` points one scan project at each. When the schedule, story volume, run time or retention changes, update the constants at the top of the script and run `make cost` again.

Usage keys are Terraform resource addresses, such as `aws_lambda_function.bot`. A misspelled key or address is silently ignored, so check that the resource's cost changed in the table. Infracost rounds DynamoDB storage down to whole GB, so anything under 1 GB shows as $0.

## Recovering data

Both data stores keep a 35-day undo window. Recovery is done by hand with an admin profile (`AWS_PROFILE=mfa-administrator`). The Lambda role can't delete or restore anything.

The DynamoDB table also has deletion protection, so `terraform destroy`, or a change that makes Terraform replace the table, fails instead of deleting it. To really remove the table, set `deletion_protection_enabled = false` in `infra/storage.tf` and apply that first.

### Restoring the state table

The DynamoDB table has point-in-time recovery, so it can be restored to any second in the last 35 days. A restore always creates a new table. Never restore over the live one, which Terraform manages.

1. Pick a time just before the bad change. Check the window:
   ```sh
   aws dynamodb describe-continuous-backups --table-name weather-story-bot-state \
     --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription'
   ```
2. Restore into a scratch table and wait for it:
   ```sh
   aws dynamodb restore-table-to-point-in-time \
     --source-table-name weather-story-bot-state \
     --target-table-name weather-story-bot-state-restore-202609141200 \
     --restore-date-time 2026-09-14T12:00:00Z \
     --billing-mode-override PAY_PER_REQUEST
   aws dynamodb wait table-exists --table-name weather-story-bot-state-restore-202609141200
   ```
3. Compare it with the live table and copy the items you need back with `put-item`. For a full rollback, scan the restored table and put every item. The table is only a few KB. Disable the schedule first if a run could interfere.
4. Delete the scratch table. Restored tables don't get PITR, tags or alarms:
   ```sh
   aws dynamodb delete-table --table-name weather-story-bot-state-restore-202609141200
   ```

### Recovering archive files

The archive bucket is versioned. A deleted or overwritten file keeps its old version for 35 days, then S3 removes it. The date and time in a key are the story's start in UTC.

```sh
BUCKET=$(TF_DATA_DIR=.terraform-production terraform -chdir=infra output -raw bucket_name)
aws s3api list-object-versions --bucket "$BUCKET" --prefix stories/MKX/2026/09/14/
```

- **Deleted file:** delete its delete marker (the entry under `DeleteMarkers` with `IsLatest: true`), and the previous version becomes current again:
  ```sh
  aws s3api delete-object --bucket "$BUCKET" --key <key> --version-id <delete-marker-version-id>
  ```
- **Overwritten file:** copy the old version back over the current one:
  ```sh
  aws s3api copy-object --bucket "$BUCKET" --key <key> --copy-source "$BUCKET/<key>?versionId=<old-version-id>"
  ```

## Adding an office

1. Create another channel with the bot as admin, and get its chat ID (steps 2–3 above).
2. Add the office to `offices` in `infra/envs/production.tfvars`. Keys are the three-letter NWS office IDs:
   ```hcl
   offices = {
     MKX = { chat_id = "-100…", name = "Milwaukee/Sullivan" }
     GRB = { chat_id = "-100…", name = "Green Bay" }
   }
   ```
3. Run `make plan ENV=production`, review it, then `make deploy ENV=production`. On its first run, the Lambda posts all of the new office's active stories.
