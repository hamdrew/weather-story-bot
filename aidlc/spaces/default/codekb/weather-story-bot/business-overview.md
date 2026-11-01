# Business Overview

## Purpose

weather-story-bot watches the National Weather Service (NWS) "Weather Stories" for one or more forecast offices and posts each new or changed story, as an image with a caption, to a Telegram channel per office. People get the graphics on their phone without checking weather.gov.

## Business Context

- **Owner and users**: a single owner (`@hamdrew`, `.github/CODEOWNERS`); readers are the subscribers of the Telegram channels.
- **Source of truth**: `api.weather.gov/offices/{id}/weatherstories`. NWS data is treated as untrusted: ambiguous listings are rejected, not posted.
- **Offices**: configured as a map of three-letter office id to Telegram chat id and name (`OFFICES_JSON`). Production started with `MKX`; the README documents adding offices, and the cost model prices 1, 6 and 122 offices.
- **Environments**: `production` and `staging`, each with its own bot, channel, state table, archive bucket, alarms and permissions boundary.

## Key Functionality

| Capability | Behaviour | Where |
|---|---|---|
| Fetch | List active stories per office and download each image | `nws.py` |
| Filter | Ignore stories past `endTime`; take no action on them | `planner.select_active` |
| Validate | Reject stories that share an image id, a title and start time, or identical image bytes | `planner._find_ambiguous` |
| Decide | `post` (new), `update` (content changed), `unchanged`, `expired`, `rejected` | `planner.decide` |
| Post | Send the image with an HTML caption; an update gets a "Updated:" prefix and the old message is deleted | `handler.py`, `telegram.py` |
| Remember | Record the posted revision and a ledger event in one DynamoDB transaction | `state.py` |
| Archive | Save each revision's image and raw metadata to S3 | `archive.py` |
| Observe | Per-run records, story sightings, structured JSON logs, five CloudWatch alarms | `history.py`, `infra/monitoring.tf` |
| Operate | Start or pause an environment's schedule and alarm actions | `scripts/set_run_state.py` |

## Business Rules and Invariants

1. A story is recorded as posted only after Telegram accepts it. A repost is acceptable; a missed story is not.
2. A story's identity is its title plus start time (`story_key`), not its image id, because NWS re-issues stories under new image ids. Content identity is the image bytes plus the description (`content_fingerprint`).
3. An old Telegram message is deleted only after its replacement is recorded. Telegram cannot delete messages older than 48 hours, so an update to an older story leaves both messages and logs a warning.
4. Only one run acts on an office at a time (a DynamoDB lease per office).
5. History writes (rejections, sightings, run records, deletion events) are best effort and never block a post.
6. Records and archive files are permanent: no table TTL and no S3 expiration of current objects; deleted or replaced data is recoverable for 35 days.
7. The Telegram token lives only in a per-environment SSM parameter, never in Terraform variables or state.

## Operational Model

- A 15-minute EventBridge schedule invokes the Lambda. Terraform creates the schedule DISABLED; the owner starts it with `mise run start <env>`.
- Merges to `main` deploy staging, then production after the owner approves the saved plan.
- Alerts go to an SNS email topic; a monthly AWS Budget (production only) covers the account.

See `architecture.md` for the structure and flow, and `component-inventory.md` for the parts.

## Sources

- `README.md` (What it does, Deploy, Alerts), `src/weather_story_bot/handler.py`, `planner.py`, `state.py`, `infra/*.tf`, `aidlc/active-memory/team.md` (Deployment).
