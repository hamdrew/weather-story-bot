# Business Overview: weather-story-bot

## Purpose

A personal tool that pushes National Weather Service (NWS) Weather Stories to Telegram. Weather Stories are the forecast graphics a local NWS office publishes ahead of notable weather; on weather.gov they are easy to miss and hard to read on an iPhone. The bot checks each configured office every 15 minutes and posts each new or changed story's image and description to that office's Telegram channel (`agent-os/product/mission.md`, `README.md`).

- **Users**: the owner only today ("Just me"). The roadmap's Phase 4 considers opening the channels to the public, staying clearly unofficial.
- **Live since**: 2026-09-13 (MKX, Milwaukee/Sullivan). Staging and a GitHub Actions deploy pipeline followed (Phases 2.0 and 2.1).

## Key Functionality

| Capability | What it does |
|---|---|
| Detect | Lists an office's active stories from `api.weather.gov`; ignores stories past their `endTime` |
| Validate | Rejects every story in a listing that shares an image ID, a title + start time, or identical image bytes with another; alerts by email instead of posting |
| Decide | Identifies a story by title + start time (`story_key`) and its content by image bytes + description (`content_fingerprint`); outcomes `post`, `update`, `unchanged`, `expired`, `rejected` |
| Archive | Saves image + raw NWS JSON to S3, one folder per story, one file pair per content revision; kept forever |
| Deliver | Posts to Telegram (`sendPhoto`, falling back to `sendDocument`); a changed story is reposted with a "🔄 Updated:" prefix and the old message deleted |
| Record | Records the post in DynamoDB only after Telegram accepts it, atomically with a ledger event; also records rejections, deletions, run records and last-seen times |
| Alert | Email (never Telegram) via CloudWatch alarms: errors, missed runs, quiet, repost loop, NWS ambiguity; plus an account-wide AWS Budget |
| Preview | `--dry-run` CLI prints each live story's decision and caption without AWS or Telegram |

## Business Rules (load-bearing)

- **A repost is acceptable; a missed story is not.** State is written only after Telegram accepts a message; an old message is deleted only after its replacement is recorded.
- **Don't trust NWS data.** Ambiguous listings are rejected wholesale, and the identity/fingerprint deliberately ignore NWS-volatile fields (image UUID, `updateTime`).
- **History is permanent.** No TTL on the table or archive; 35-day undo windows (PITR, S3 noncurrent versions).
- **Production deploys go through the pipeline** with human approval; laptop production deploys need `BREAK_GLASS=1`.
- **Local tools are read-only.** Only deployed code and explicitly named `scripts/` tools write.

## Domain Vocabulary

- **Office**: an NWS forecast office, three uppercase letters (MKX, GRB, ARX, DLH, MPX). The unit of isolation, lease and (soon) invocation.
- **Story / revision**: a story is title + start time; each distinct image + description is a revision.
- **Ledger**: append-only `EVENT#` items (`posted`, `updated`, `rejected`, `deleted`, `delete_failed`) in the state table.
- **Environment**: `production` (unsuffixed names) or `staging` (`-staging` suffix), each with its own bot, channel, table, bucket and alarms.

## Current Direction

The planning record lives in `agent-os/` (see [component-inventory.md](component-inventory.md#agent-os-planning-record)). Phase 2.2 (five offices, one invocation per office, a `misconfigured` outcome) is in progress; Phases 2.3 (dashboard and weekly digest), 3 (Year in Review) and 4 (more offices, public channels) follow. The active intent replaces agent-os with AI-DLC as the planning workflow; see [code-quality-assessment.md](code-quality-assessment.md#agent-os-coupling) for where the codebase depends on it.
