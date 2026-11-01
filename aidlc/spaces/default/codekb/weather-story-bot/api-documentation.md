# API Documentation

The system exposes no HTTP API. Its surfaces are one Lambda entry point, one CLI, an environment-variable contract, and the external APIs and data stores it consumes.

## Provided Interfaces

### Lambda handler

- **Entry**: `weather_story_bot.handler.lambda_handler(event, context)` (`infra/lambda.tf`: `handler`, runtime `python3.13`, arm64, 256 MB, 300 s).
- **Event**: ignored. The schedule carries no input.
- **Uses from context**: `context.aws_request_id` (log field and `RUN#` record).
- **Returns**: `dict[office_id, {posted, updated, skipped, rejected, failed}]`.
- **Errors**: raises `ConfigError` for missing settings, `ProcessingError` when any office's `failed` count is non-zero (so Lambda records an error). Async retries are off (`maximum_retry_attempts = 0`).
- **Concurrency**: reserved concurrency `lambda_max_concurrency` (default 10), a spend ceiling. Mutual exclusion is the office lease.

### Environment contract (`config.Settings.from_env`)

| Variable | Meaning |
|---|---|
| `OFFICES_JSON` | `{"MKX": {"chat_id": "-100...", "name": "Milwaukee/Sullivan"}}`; ids match `^[A-Z]{3}$`; non-empty |
| `STATE_TABLE` | DynamoDB table name |
| `ARCHIVE_BUCKET` | S3 bucket name |
| `TELEGRAM_TOKEN_PARAM` | SSM SecureString parameter name |
| `NWS_USER_AGENT` | User-Agent sent to NWS |

### Local CLI

`weather-story-bot --dry-run [--office MKX] [--user-agent TEXT]` (`__main__.py`). `--dry-run` is required. Fetches live NWS data, prints each story's decision label (`new-or-updated (state not read)`, `expired`, `rejected (<reasons>)`) with its caption. Exit 1 on an NWS or download failure. Reads `.env` through python-dotenv when installed; never touches AWS or Telegram.

### Operator scripts and tasks

`scripts/set_run_state.py start|pause [--apply] -` reads `terraform output -json`. Tasks are listed in `technology-stack.md` (Build and tooling).

## Consumed External APIs

### NWS (`nws.py`)

| Call | Detail |
|---|---|
| `GET https://api.weather.gov/offices/{id}/weatherstories` | `Accept: application/ld+json`; body `{"stories": [...]}`; sorted by `order`; 10 s timeout |
| `GET <story.download>` | `Accept: image/png`; empty body is an error |

Story fields read: `officeId, startTime, endTime, updateTime, title, description, altText, priority, order, download`. Retries: 2 attempts, 1 s apart, on transport errors and 5xx. Any other non-success becomes `NwsError`. A malformed story raises `ValueError`, wrapped as `NwsError`.

### Telegram Bot API (`telegram.py`)

| Method | Use |
|---|---|
| `sendPhoto` | multipart; `parse_mode=HTML`; caption limit 1024 UTF-16 units |
| `sendDocument` | fallback when a photo is rejected (413, or 400 with a known marker text) |
| `deleteMessage` | remove the replaced message; "message to delete not found" counts as deleted |

Behaviour: one retry on HTTP 429 when `retry_after` is at most 30 s; transport errors are never retried (the message may have been delivered); error text never includes the URL, which holds the token. The log line `Telegram message sent` is emitted before the result is parsed and feeds the `StoriesPosted` metric.

### SSM and S3

- `ssm:GetParameter` with decryption, once per cold start.
- `s3:PutObject` of `stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{slug}-{story_key[:8]}/{fingerprint[:16]}.png` and `.json` (`archive.archive_prefix`).

## DynamoDB Data Model (`state.py`, `history.py`)

One table per environment, `PK` (S) and `SK` (S), no indexes, no TTL, PITR 35 days, deletion protection. Every item has `schema_version = 1`.

| Item | Key | Written by | Notes |
|---|---|---|---|
| Current story | `PK=OFFICE#<id>`, `SK=STORY#<start_utc_iso>#<story_key>` | `PostedStore.record_posted` | `posted_image_id`, `telegram_message_id`, `archive_prefix`, `fingerprint`, `image_sha256`, `description_sha256`, `posted_at`; `last_seen_at` added by `StoryHistory.touch_last_seen` at most hourly |
| Ledger event | `SK=EVENT#<start>#<story_key>#<at_utc_iso>` | transaction (posted, updated) or `StoryHistory` (rejected, deleted, delete_failed) | immutable; `attribute_not_exists(PK)` |
| Run record | `SK=RUN#<at_utc_iso>` | `StoryHistory.record_run` | `nws_failed`, `stories_seen`, the five counters, `aws_request_id` |
| Lease | `SK=LEASE` | `OfficeLease.take/release` | conditional on `attribute_not_exists(PK) OR expires_at < :now`; 360 s |

Identity: `story_key = sha256(json{title, start_time_utc})`; `content_fingerprint = sha256(json{image_sha256, description})`. Both use a frozen JSON encoding.

A legacy table `<name>-posted` (`office_id`, `image_id`) exists in production only, used by the migration scripts.

## Observability Contract

Metric filters match exact JSON log messages: `Telegram message sent` (metric `StoriesPosted`) and `Ambiguous stories from NWS` (metric `AmbiguousStories`). Namespace is `WeatherStoryBot` in production and `WeatherStoryBot/<env>` elsewhere.
