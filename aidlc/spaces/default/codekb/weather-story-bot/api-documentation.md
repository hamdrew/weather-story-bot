# API Documentation: weather-story-bot

The system exposes no network API. Its surfaces are one Lambda entry point, CLIs, outbound HTTP/AWS calls, a DynamoDB/S3 data contract and two log-message contracts.

## Inbound

### Lambda: `weather_story_bot.handler.lambda_handler(event, context)`

- **Trigger**: EventBridge Scheduler, async, no input (`event` is ignored today; Phase 2.2 plans to pass the office in the event).
- **Config (env vars)**: `OFFICES_JSON` (`{"MKX": {"chat_id": "-100…", "name": "…"}}`), `STATE_TABLE`, `ARCHIVE_BUCKET`, `TELEGRAM_TOKEN_PARAM`, `NWS_USER_AGENT`. Missing/invalid → `ConfigError`.
- **Returns**: `{"<OFFICE>": {"posted": n, "updated": n, "skipped": n, "rejected": n, "failed": n}}`.
- **Errors**: raises `ProcessingError` when any office has `failed > 0` (counts as a Lambda error for the `errors` alarm). Retries: none (async retries 0, schedule retries 0).

### CLI: `weather-story-bot --dry-run [--office MKX] [--user-agent UA]`

Required `--dry-run`; reads NWS only (no AWS, no Telegram); prints `--- #<order> <story_key> [<label>]`, image URL and caption per story. Labels: `expired`, `rejected (<reasons>)`, `new-or-updated (state not read)`. Exit 0 ok, 1 on NWS error, 2 on argparse error. Loads `.env` if `python-dotenv` is installed.

### Operator scripts

| Command | Contract |
|---|---|
| `scripts/set_run_state.py {start,pause} <outputs.json or -> [--apply] [--profile weather-deploy]` | Reads `terraform output -json` (`schedule_name`, `alarm_names`, `region`); dry run unless `--apply`; idempotent; start = schedule then alarms, pause = alarms then schedule |
| `scripts/build_zip.py <src> <dst>` | Stdlib only; prints base64 sha256 (Terraform `filebase64sha256` form) |
| `scripts/infracost_usage.py write <dir>` / `report <json>` | Writes per-scenario usage files; prints side-by-side costs |
| `scripts/migrate_story_keys.py`, `scripts/migrate_table_keys.py` | Completed one-off migrations; dry run unless `--apply` |

## Outbound

### NWS (`nws.py`, base `https://api.weather.gov`)

| Call | Headers | Handling |
|---|---|---|
| `GET /offices/{office}/weatherstories` | `User-Agent` (app + contact), `Accept: application/ld+json` | Parses `stories[]` via `Story.from_api`; sorted by `order`; malformed → `NwsError` |
| `GET {story.download}` | `Accept: image/png` | Empty body → `NwsError` |

Timeout 10 s; one retry after 1 s on transport error or 5xx; non-2xx → `NwsError`. Fields used: `officeId`, `startTime`, `endTime`, `updateTime`, `title`, `description`, `altText`, `priority`, `order`, `download` (image id = last path segment).

### Telegram Bot API (`telegram.py`, base `https://api.telegram.org/bot<token>/`)

| Method | Use | Handling |
|---|---|---|
| `sendPhoto` | multipart `photo`, `caption` (HTML, ≤1024 UTF-16 units), `parse_mode=HTML` | 413 or 400 with photo markers → retry as `sendDocument` |
| `sendDocument` | fallback | returns `message_id` |
| `deleteMessage` | remove replaced message | "message to delete not found" counts as deleted; older than 48 h raises → `delete_failed` |

Timeout 30 s; transport errors never retried (message may have been delivered); one retry on 429 when `retry_after ≤ 30 s`. The token never appears in exceptions or logs.

### AWS

SSM `GetParameter` (token, `WithDecryption`, cold start only); DynamoDB `GetItem` (consistent), `PutItem` (conditional), `UpdateItem`, `DeleteItem`, `TransactWriteItems`; S3 `PutObject` under `stories/*`.

## DynamoDB State Table Contract

Table `weather-story-bot[-staging]-state`, `PK`/`SK` strings, on-demand, PITR 35 days, deletion protection, no TTL, no indexes. Every item has `schema_version = 1`.

| SK | Item | Written by |
|---|---|---|
| `STORY#<start_utc_iso>#<story_key>` | current posted revision: `posted_image_id`, `telegram_message_id`, `archive_prefix`, `fingerprint`, `image_sha256`, `description_sha256`, `posted_at`, `last_seen_at`, title/times | `PostedStore.record_posted` (transaction), `StoryHistory.touch_last_seen` |
| `EVENT#<start_utc_iso>#<story_key>#<at>` | immutable ledger event: `event` ∈ posted/updated/rejected/deleted/delete_failed | transaction (posted/updated); `StoryHistory` best effort (others) |
| `RUN#<at>` | per-office run record: counts, `stories_seen`, `nws_failed`, `aws_request_id` | `StoryHistory.record_run` |
| `LEASE` | office lease: `holder`, `taken_at`, `expires_at` (360 s) | `OfficeLease.take/release` |

`PK = OFFICE#<office_id>`. `story_key` and `content_fingerprint` are sha256 over a frozen JSON encoding (`state._sha256_json`); changing it would orphan every stored record.

Legacy: production-only MVP table `weather-story-bot-posted` (`office_id`/`image_id`), untouched rollback.

## S3 Archive Contract

`stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title-slug}-{story_key[:8]}/{fingerprint[:16]}.{png,json}` (UTC start). JSON is the raw NWS story verbatim. Versioned; noncurrent versions expire after 35 days; current objects never expire.

## Log Contracts (do not change the message text)

| Message | Level | Consumer |
|---|---|---|
| `Telegram message sent` | INFO | metric filter `StoriesPosted` → `quiet`, `repost-loop` alarms |
| `Ambiguous stories from NWS` | ERROR | metric filter `AmbiguousStories` → `nws-ambiguous` alarm |
| `Run complete` | INFO | runbook (alarm descriptions, README) |
| `Story posted`, `Telegram delete failed, old message kept` | INFO / WARNING | runbook |
