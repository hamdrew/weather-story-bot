# Weather Story Bot — Phase 1 MVP

## Context

NWS Weather Stories are only on weather.gov, which you have to remember to check, and they're hard to read on an iPhone. The Phase 1 roadmap fixes that. A scheduled AWS Lambda finds new MKX (Milwaukee/Sullivan) Weather Stories, saves them to S3, and posts each one's image and description to a Telegram channel. The repo has no code yet, so this spec builds the whole MVP.

**Key research finding:** api.weather.gov has a structured endpoint, so no HTML scraping is needed:
- `GET https://api.weather.gov/offices/MKX/weatherstories` returns `{"stories": [...]}`. Each story has `officeId, startTime, endTime, updateTime, title (≤50), description, altText, priority, order (1–7), download`.
- `download` looks like `https://api.weather.gov/offices/MKX/weatherstories/download/<uuid>` and returns the PNG (about 1.1 MB, 1536×864).
- NWS requires a descriptive `User-Agent` header with contact info.

## Decisions (from shaping)

| Topic | Decision |
|---|---|
| Source | api.weather.gov weatherstories endpoint (not page scraping) |
| Dedupe | Key = office + image UUID. Post when the UUID is new. Repost with an "Updated" prefix when `updateTime` changes. Skip a new UUID or revision whose content fingerprint (image bytes + title, description, start/end/update times) was already posted (Task 12) |
| Destination | One Telegram channel per office, with the bot as admin. MVP config has only MKX |
| Archive | Phase 2 S3 archive pulled in: save image + metadata JSON for every post |
| Schedule | Every 15 minutes (EventBridge Scheduler) |
| IaC | Terraform, with state in an S3 backend (native `use_lockfile`) |
| Secrets | Telegram bot token in SSM Parameter Store (SecureString, created by hand so it never lands in TF state) |
| Python | uv, httpx, Lambda `python3.13` on arm64. Zip is built with `uv pip install --target` |
| First run | Posts whatever stories are active at the time. This is fine for a personal tool |
| Alerting | CloudWatch alarms send to an SNS topic with an email subscription, and alarms also notify on return to OK. Separately, an AWS Budget emails when spend runs high. Alerts never go through Telegram |
| Cost estimate | `make cost` runs Infracost by hand (not before deploys, not in CI), with a committed usage file for the usage-based resources |

## Target layout

```
pyproject.toml / uv.lock / .python-version (3.13)
Makefile                      # test, coverage, lint, format, build, plan, deploy, cost, clean
src/weather_story_bot/
  config.py     # load env: OFFICES_JSON, STATE_TABLE, ARCHIVE_BUCKET, TELEGRAM_TOKEN_PARAM, NWS_USER_AGENT
  models.py     # Story dataclass (+ image_id parsed from download URL)
  nws.py        # NwsClient.list_stories(office), .download_image(story)
  state.py      # PostedStore (DynamoDB): get_update_time(), record_posted()
  archive.py    # StoryArchive (S3): save(story, image_bytes) -> key prefix
  telegram.py   # TelegramClient.send_photo(); build_caption()
  handler.py    # lambda_handler: orchestrates per office
  __main__.py   # local `--dry-run` against the live NWS API (no AWS, no Telegram)
tests/ (+ tests/fixtures/mkx_weatherstories.json captured from the live API)
infra/          # Terraform (monitoring.tf holds the alarms, SNS topic, and budget; infracost-usage.yml holds usage for cost estimates)
```

---

## Task 1: Save spec documentation

Create `agent-os/specs/2026-09-13-0026-weather-story-mvp/` with:
- **plan.md** — this plan
- **shape.md** — scope, the decisions table above, context (visuals: none; references: none, greenfield; product alignment: MVP plus the S3 archive pulled forward from Phase 2; office config ready for multiple offices)
- **standards.md** — says that `agent-os/standards/index.yml` is empty, so no standards apply yet
- **references.md** — no in-repo references. List the external ones: NWS API OpenAPI spec (`https://api.weather.gov/openapi.json`, `office_weatherstory` / `office_weatherstory_image`), the MKX weatherstory page, and Telegram Bot API `sendPhoto`
- No `visuals/` folder, because no visuals were provided

## Task 2: Python project scaffold

- `uv init --package`, pin Python 3.13. Runtime dep: `httpx`. Dev deps: `pytest`, `pytest-cov`, `respx`, `moto[dynamodb,s3,ssm]`, `boto3`, `python-dotenv`, `ruff`.
- Configure ruff and pytest in `pyproject.toml`. boto3 counts as dev-only because the Lambda runtime provides it.
- Add `Makefile` targets: `test`, `coverage`, `lint`, `format`, `build`, `plan`, `deploy`, `clean`.
- Add `build/`, `*.zip`, `.terraform/`, `backend.hcl`, and `*.tfvars` to `.gitignore` if they aren't already covered.

## Task 3: NWS client + models

- `Story` frozen dataclass with every API field. `image_id` is the last path segment of `download`. Times are parsed to aware datetimes.
- `NwsClient(http: httpx.Client, user_agent)`:
  - `list_stories(office_id)` calls `/offices/{id}/weatherstories` with `Accept: application/ld+json` and returns the stories sorted by `order`.
  - `download_image(story)` returns bytes.
  - 10 s timeout, one retry on 5xx or transport error. Otherwise it raises `NwsError`.
- Save the live MKX response as a test fixture. Tests cover parsing, ordering, image_id extraction, and error paths (respx).

## Task 4: State store (DynamoDB)

- Table `weather-story-bot-posted`: `office_id` (PK, S) and `image_id` (SK, S), on-demand billing.
- Item attributes: `update_time`, `title`, `posted_at`, `telegram_message_id`, `archive_prefix`.
- `PostedStore.get_update_time(office, image_id) -> str | None`
- `PostedStore.record_posted(story, message_id, archive_prefix)` does a put.
- Decision helper `classify(story, seen_update_time) -> NEW | UPDATED | SEEN`.
- Tests with moto.

## Task 5: S3 archive

- Bucket `weather-story-bot-archive-<account_id>`: public access blocked, SSE-S3, ACLs disabled (`BucketOwnerEnforced`).
- Keys: `stories/{office}/{YYYY}/{MM}/{DD}/{image_id}/{updateTime:%Y%m%dT%H%M%SZ}.png` plus a `.json` next to it holding the raw story object. The date comes from `startTime`. Writes are idempotent, and an update gets a new pair of files.
- Tests with moto.

## Task 6: Telegram client + caption

- `TelegramClient(http, token).send_photo(chat_id, image_bytes, caption, filename)`: multipart upload to `sendPhoto` with `parse_mode=HTML`. Returns `message_id`.
  - On 429 it honors `parameters.retry_after` once.
  - If Telegram rejects the photo (400 `PHOTO_INVALID_DIMENSIONS` / too big), it falls back to `sendDocument`.
- `build_caption(story, office, updated: bool)` builds: optional `🔄 Updated: ` prefix, then `<b>title</b>`, blank line, description, blank line, a link to `https://www.weather.gov/{office_lower}/weatherstory`.
  - Everything is HTML-escaped.
  - The description is truncated with `…` so the caption stays within Telegram's 1024-character limit.
- Token is read from SSM once per cold start and cached at module level.
- Tests: caption escaping and truncation, 429 retry, fallback (respx).

## Task 7: Lambda handler

- `lambda_handler(event, context)` does this for each office in `OFFICES_JSON` (`{"MKX": {"chat_id": "-100…", "name": "Milwaukee/Sullivan"}}`):
  1. Call `list_stories`.
  2. Run `classify` on each story.
  3. For each NEW or UPDATED story in `order`: download → archive → send to Telegram → `record_posted`.
- Delivery is at-least-once: state is written only after a successful post, so a failed state write can cause a repost but a story is never lost.
- Errors are isolated per story and per office, and logged as structured JSON. If anything failed, the handler raises at the end so Lambda's `Errors` metric shows it. It returns a summary like `{office: {posted, updated, skipped, failed}}`.
- `__main__.py --dry-run [--office MKX]` fetches live stories and prints the captions it would post.
- Tests: new story posted and recorded. Seen story skipped. Changed `updateTime` reposts with the prefix. A Telegram failure leaves the story unrecorded. One office failing doesn't block the others.

## Task 8: Terraform infrastructure (`infra/`)

- `versions.tf`:
  - Terraform `>= 1.11`, which is the first version where native S3 locking (`use_lockfile`) is GA.
  - `hashicorp/aws ~> 6.0`, locked in `.terraform.lock.hcl`.
  - `default_tags` of `Project = weather-story-bot` and `ManagedBy = terraform`.
  - Also holds `local.name` and the `aws_caller_identity` data source.
- `backend.tf` has `backend "s3" {}` with partial config. `backend.hcl.example` sets bucket, key `weather-story-bot/terraform.tfstate`, region `us-east-2`, `encrypt = true`, and `use_lockfile = true`.
- `variables.tf`:
  - `region` (default `us-east-2`)
  - `offices` (map of object: chat_id, name), validated to be non-empty and keyed by three-letter uppercase office ids
  - `telegram_token_param_name` (default `/weather-story-bot/telegram-token`)
  - `nws_user_agent`
  - `schedule_expression` (default `rate(15 minutes)`)
  - `lambda_zip_path` (default `../build/lambda.zip`)
  - Plus `terraform.tfvars.example`.
- `storage.tf`:
  - DynamoDB table
  - S3 archive bucket with a public access block, SSE-S3 encryption, and `BucketOwnerEnforced` object ownership (ACLs disabled)
- `lambda.tf`:
  - CloudWatch log group `/aws/lambda/weather-story-bot` with 30-day retention.
  - Lambda: python3.13, arm64, 256 MB, **300 s timeout**, env vars, `source_code_hash` from the zip, and `logging_config` with `log_format = "Text"` because the handler writes its own JSON lines.
  - `aws_lambda_function_event_invoke_config` with `maximum_retry_attempts = 0`. The next scheduled run is the retry.
- `iam.tf`:
  - Lambda role with least privilege:
    - `logs:CreateLogStream` and `logs:PutLogEvents` on the log group
    - GetItem and PutItem on the table
    - PutObject on `stories/*` in the archive bucket
    - `ssm:GetParameter` on the token param (no KMS statement, because the AWS-managed `aws/ssm` key already allows decryption)
  - Scheduler role, trusted by `scheduler.amazonaws.com` only when `aws:SourceAccount` is this account, allowed `lambda:InvokeFunction` on the bot.
- `scheduler.tf`: EventBridge Scheduler schedule with `flexible_time_window` set to `OFF` and the target's `retry_policy.maximum_retry_attempts = 0`.
- `outputs.tf`: function name, table name, bucket name.
- `make build` (runs `clean` first):
  - `uv export --no-dev --no-hashes --no-emit-project --frozen -o build/requirements.txt`
  - `uv pip install -r build/requirements.txt --target build/package --python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary :all:`
  - Copy `src/weather_story_bot` into `build/package` and remove `__pycache__` directories.
  - Zip the result to `build/lambda.zip`.
- `make plan` / `make deploy` run `terraform -chdir=infra plan` / `apply`. `make lint` also runs `terraform fmt -check`.

## Task 9: README + one-time setup docs

Replace the placeholder README with these sections:
- what it does
- one-time setup: create the bot with BotFather, create a private channel and add the bot as admin, get the channel chat ID, `aws ssm put-parameter --type SecureString`, create the TF state bucket, copy the `backend.hcl` and `tfvars` examples
- local dev (`make test`, dry run)
- deploy (`make build && make deploy`)
- alerts: after the first deploy, click the link in the "AWS Notification - Subscription Confirmation" email (alerts are dropped until you do). Add a Gmail filter for the alert senders: SNS sends from `no-reply@sns.amazonaws.com`, and for Budgets, check the sender on the first email. Set the filter to "Never send it to Spam", "Always mark it as important", and "Categorize as: Primary", so the alerts notify even when the Gmail app only notifies for Primary or high-priority mail. Explain what each alarm means, what to check first, and how to tune the thresholds
- how to add an office

## Task 10: Monitoring and alerts (`infra/monitoring.tf`)

Why: the handler raises `ProcessingError` whenever anything fails, and timeouts also count as errors. So Lambda's `Errors` metric already covers failures in NWS, Telegram, DynamoDB, S3, SSM, and config. What it can't see is a run that succeeds while something is still wrong, or a schedule that stops running. The monitors below cover those gaps.

- **Variables** (add to `variables.tf` and `terraform.tfvars.example`):
  - `alert_email` (string, required)
  - `monthly_budget_usd` (number, default `5`)
  - `quiet_alarm_days` (number, default `2`, validated to be 1–7 because CloudWatch can evaluate at most 7 days)
  - `repost_alarm_max_posts` (number, default `8`), counted over a 3-hour window
- **SNS:** Create topic `weather-story-bot-alerts` with an `email` subscription to `var.alert_email`.
  - Leave the topic unencrypted, or use a customer-managed KMS key that allows `cloudwatch.amazonaws.com`. With the AWS-managed `aws/sns` key, CloudWatch can't publish alarm notifications.
- **Metric filter:** On the Lambda log group, pattern `{ $.message = "Telegram message sent" }` → metric `StoriesPosted` in namespace `WeatherStoryBot`, value `1`, no default value. New posts and "Updated" reposts both count.
  - `TelegramClient.send_photo` logs that line as soon as Telegram accepts the message, before parsing `message_id` and before the DynamoDB write. Counting the handler's `"Story posted"` line instead would hide a repost loop, because that line only runs after `record_posted` succeeds.
- **Alarms:** Every alarm sets both `alarm_actions` and `ok_actions` to the topic. Each `alarm_description` says what probably happened, what to check first, and links to the log group in the CloudWatch Logs console (`https://<region>.console.aws.amazon.com/cloudwatch/home?region=<region>#logsV2:log-groups/log-group/$252Faws$252Flambda$252Fweather-story-bot`).

| Alarm | Metric | Stat / period | Condition | Missing data |
|---|---|---|---|---|
| `errors` | `AWS/Lambda` `Errors` (FunctionName) | Sum / 15 min | ≥ 1 in 2 of 2 periods | notBreaching |
| `missed-runs` | `AWS/Lambda` `Invocations` (FunctionName) | Sum / 1 h | < 1 for 1 period | **breaching** |
| `quiet` | `WeatherStoryBot` `StoriesPosted` | Sum / 1 day | < 1 for `quiet_alarm_days` periods | **breaching** |
| `repost-loop` | `WeatherStoryBot` `StoriesPosted` | Sum / 3 h | > `repost_alarm_max_posts` for 1 period | notBreaching |

- The `missed-runs` and `quiet` alarms must treat missing data as breaching. When the schedule stops or nothing gets posted, no data points are published at all.
- **Budget:** An `aws_budgets_budget` of type `COST`, monthly, limited to `var.monthly_budget_usd`. Email `var.alert_email` directly (no SNS) when ACTUAL spend passes 80% and when FORECASTED spend passes 100%. It covers the whole account, not just this project.
- **Outputs:** Add `alert_topic_arn`.
- **Tests:**
  - Add a handler test that checks exactly one `"Story posted"` log record per new or updated story, and none for skipped stories.
  - Add tests that a `"Telegram message sent"` record is logged for every message Telegram accepts, including when the `message_id` is unusable or `record_posted` fails, and not when Telegram rejects the message. The metric filter depends on that message text.
  - Run `terraform validate`.
- **Out of scope:**
  - Duration alarm (a timeout already counts as an error, and failing on very large data is acceptable)
  - Throttles
  - DynamoDB and S3 metrics
  - EventBridge Scheduler metrics (a missed run already alarms)
  - Alarms on warning log lines

## Task 11: Cost estimate command (`make cost`)

Why: every resource except the CloudWatch alarms is billed by usage, and the bill depends on the schedule and story volume more than on the resource list. This task adds a command I can run whenever I want to see the estimated monthly cost. It doesn't run before deploys or in CI.

- **Tool:** Infracost CLI. It reads `infra/` as HCL, so it needs no Terraform plan and no AWS credentials.
  - One-time setup is `brew install infracost` and `infracost setup`. That stores a free API key in the local Infracost config, or the key can be set as `INFRACOST_API_KEY`. The key is never committed.
- **Usage file** `infra/infracost-usage.yml` (committed):
  - Generate the template with `infracost breakdown --path infra --usage-file infra/infracost-usage.yml --sync-usage-file`. That fills in the usage keys for every supported resource.
  - Fill in the values, starting from 2,880 runs a month (one every 15 minutes over 30 days). Base the rest on typical run duration, stories per run, posts per month, image size (about 1.1 MB PNG plus JSON per post), and log volume.
  - Put a comment on each value saying how it was worked out, so it's easy to update when the schedule or thresholds change.
  - Delete keys that don't apply to this project rather than leaving them at zero.
- **Makefile:** Add `cost` to `.PHONY`.
  - `cost` runs `infracost breakdown --path infra --usage-file infra/infracost-usage.yml`.
  - If `infracost` isn't on `PATH`, fail with a one-line hint pointing to the README setup section.
  - Check the flags against the installed CLI version when implementing.
- **README:** Add a short "Cost estimate" section covering one-time setup, `make cost`, and how to update the usage file. Also note whether the output subtracts the AWS free tier (check the real output, don't assume).
- **As built (Infracost CLI v2.16.3):** v2 differs from the flags above.
  - `breakdown` is deprecated and forwards to `scan`. `scan` has no `--usage-file`, `--path` or `--sync-usage-file` flags.
  - The usage file is set in a root `infracost.yml` (`projects: [{path: infra, usage_file: infra/infracost-usage.yml, terraform_vars: {...}}]`). The placeholder `terraform_vars` stop missing-variable warnings, since `terraform.tfvars` is gitignored.
  - With no sync command, usage keys were checked by confirming each value changed its cost component in `infracost scan --json`.
  - Tables and summaries round to whole dollars (the whole stack shows `$0`). `make cost` runs `scan --json` into `build/infracost.json`, prints `inspect --file … --group-by resource --costs-only --llm` (full precision), and prints the total from the JSON.
  - Auth is `infracost auth login`. `infracost setup` also configures agents, IDEs and CI, which aren't needed here.
  - The free tier is not subtracted (verified: Lambda requests and GB-seconds are priced from the first unit).
- **Out of scope:**
  - Running before deploys, in CI, or as a PR comment (see the Phase 2 CI/CD roadmap item)
  - Writing down a baseline estimate
  - Comparing the estimate with actual spend (the budget alert in Task 10 covers overspending)

## Task 12: Content fingerprint dedupe (added 2026-09-14)

Why: Task 4 assumed an image UUID identifies one story. On 2026-09-14, NWS re-issued MKX "High Swim Risk" under a new UUID (`4b014770…` → `e7a27513…`). The PNG was byte-identical and the story JSON matched except for `download`, including `updateTime`. The bot classified it as NEW and posted it a second time, about 6.5 hours after the first.

- **Fingerprint:** `content_fingerprint(story, image_bytes)` in `state.py` is the SHA-256 of canonical JSON holding the image's SHA-256 plus `title`, `description`, `startTime`, `endTime` and `updateTime` (times normalized to UTC).
  - The fields are listed explicitly rather than "raw JSON minus `download`", so new API fields or an `order` reshuffle can't hide a duplicate.
  - `updateTime` is included so a revert to earlier content (A → B → A) still posts, since the revert gets a new `updateTime`.
  - The image is included because two different graphics can share a title and `updateTime`.
- **Storage:** Same table, no schema or IAM change. After a post, `record_posted` writes the story item (now with a `fingerprint` attribute), then a fingerprint item with sort key `content#<fingerprint>` holding `image_id`, `telegram_message_id` and `archive_prefix`. Image UUIDs never contain `#`, so the keys can't collide.
  - These are two separate PutItems. If the second one fails, the run fails (and alarms as usual). The story is still recorded as SEEN, and only a later re-issue of that exact revision could repost. That's consistent with at-least-once delivery.
- **Handler flow** for NEW or UPDATED stories: download → fingerprint → look up `content#<fingerprint>`.
  - **Match:** `record_duplicate` writes the new UUID's item with the story's `update_time`, `duplicate_of` (the original `image_id`), and the original's `telegram_message_id` and `archive_prefix`, so later runs see it as SEEN without downloading. Nothing is archived or posted. The handler logs `"Duplicate story skipped"` and counts it as `skipped`.
  - **No match:** archive → post → `record_posted` as before.
- **Existing items** from before this change have no fingerprint item. A re-issue of one of them posts once more. Backfilling from the S3 archive (each prefix has the PNG and raw JSON) is an optional one-off after deploy.
- **Tests:**
  - Fingerprint: stable for the same content; changes when the image bytes, title, description, or any of the three times change; ignores `download` and `order`; equal for equivalent times in different offsets.
  - Store: `record_posted` writes the fingerprint item; `find_by_fingerprint` returns it; `record_duplicate` makes the new UUID SEEN.
  - Handler: a story re-issued under a new UUID with identical bytes and metadata is skipped, recorded with `duplicate_of`, logged, not archived, and not posted; the next run skips it without downloading. A new UUID with a different image, or the same image with a new `updateTime` or description, still posts.
- **Out of scope:** Deleting the duplicate Telegram message already posted on 2026-09-14; a GSI; perceptual (near-identical) image matching.

---

## Verification

1. `make lint && make test`: all unit tests pass (respx + moto, no network).
2. `uv run python -m weather_story_bot --dry-run --office MKX`: prints captions for the live MKX stories.
3. `make build`, then check that `build/lambda.zip` contains `weather_story_bot/` and `httpx/`.
4. `terraform -chdir=infra init -backend-config=backend.hcl && terraform -chdir=infra plan`, then `apply`.
5. `aws lambda invoke --function-name weather-story-bot out.json`:
   - active stories appear in the Telegram channel
   - DynamoDB has items for `MKX`
   - S3 has a `.png` + `.json` per story
6. Invoke again: nothing is reposted (summary shows `skipped`).
7. Wait for a scheduled run and confirm CloudWatch logs show one invocation every 15 minutes.
8. Confirm the SNS email subscription. Then check that `aws sns list-subscriptions-by-topic --topic-arn "$(terraform -chdir=infra output -raw alert_topic_arn)"` doesn't show `PendingConfirmation`.
9. For each alarm, run `aws cloudwatch set-alarm-state --alarm-name <name> --state-value ALARM --state-reason "test"`. Check that the ALARM email shows up as a Gmail app notification on the iPhone, and that the OK email follows at the next evaluation.
10. After a few invocations, confirm `WeatherStoryBot/StoriesPosted` has data points in CloudWatch Metrics, and that all alarms are `OK`, not `INSUFFICIENT_DATA`. The `quiet` alarm may stay `INSUFFICIENT_DATA` until a full day has passed.
11. Confirm the budget appears in the AWS Budgets console with both notifications.
12. `make cost` with no AWS credentials set:
    - it prints a monthly breakdown that includes the Lambda, DynamoDB table, S3 bucket, log group, and CloudWatch alarms
    - usage-based resources show nonzero costs from the usage file, with no "usage costs not included" warnings for them
    - with `infracost` removed from `PATH`, it prints the setup hint and exits non-zero
