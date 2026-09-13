# Weather Story MVP — Shaping Notes

## Scope

The full Phase 1 MVP. A scheduled AWS Lambda checks the NWS MKX (Milwaukee/Sullivan) office for Weather Stories every 15 minutes. For each new or updated story, it archives the image and metadata to S3, posts the image and description to a Telegram channel, and records the story in DynamoDB so it isn't posted twice. CloudWatch alarms and an AWS Budget email me when the bot fails, stops running, goes quiet, reposts in a loop, or costs more than expected. A `make cost` command shows the estimated monthly cost of the infrastructure whenever I want to check.

## Decisions

- **Source is the NWS API, not the web page.** `GET https://api.weather.gov/offices/{office}/weatherstories` returns structured stories. Each has a `download` URL containing a unique image UUID. The weatherstory web page instead reuses fixed image filenames (`Tab2FileL.png`), which makes change detection unreliable.
- **Dedupe key = office + image UUID.** A new UUID gets posted. If a known UUID's `updateTime` changes, it's reposted with an "Updated" prefix.
- **Telegram channel per office**, with the bot added as admin. The MVP config has only MKX, but offices are a config map (office → chat ID, name), and the office ID is part of every DynamoDB and S3 key.
- **S3 archive pulled forward from Phase 2.** Every posted story (and every update) saves its PNG plus the raw story JSON.
- **Terraform** for infrastructure, with remote state in S3 (native lockfile).
- **Telegram bot token in SSM Parameter Store** as a SecureString. It's created by hand so the value never lands in Terraform state.
- **Python via uv, HTTP via httpx.** Lambda runs `python3.13` on arm64. Third-party deps are vendored into the zip at build time.
- **Every 15 minutes** via EventBridge Scheduler.
- **At-least-once delivery.** State is written only after a successful Telegram post. A rare repost is acceptable; a missed story is not.
- **First run posts whatever stories are active at the time.** No seeding step, because this is a personal tool.
- NWS requires a descriptive `User-Agent` with contact info. It's configurable.
- **Alerts go by SNS email, not Telegram.** Telegram could be the thing that's broken. The Gmail iOS app provides the iPhone push notification. Every alarm also sends an email when it returns to OK.
- **Five monitors:**
  - **Errors:** 2 failed runs in a row. One flaky run doesn't alert.
  - **Missed runs:** No invocations in an hour.
  - **Gone quiet:** No stories posted in 2 days.
  - **Repost loop:** More than 8 posts in 3 hours.
  - **Cost:** A monthly AWS Budget.
  The quiet and repost-loop alarms catch bugs that don't raise errors, so the Errors metric can't see them.
- **Post counts come from a log metric filter** on the Telegram client's `"Telegram message sent"` log line. It's logged before the DynamoDB write, so posts that fail to record still count toward the repost-loop alarm. The code doesn't publish its own metrics, so no extra IAM permission or runtime dependency is needed.
- **Thresholds are Terraform variables.** The starting values are guesses until there's real MKX posting data.
- **Cost estimates come from Infracost, run by hand.** `make cost` runs `infracost breakdown` on `infra/`. It doesn't run before deploys or in CI, and no baseline gets written down.
  - **Chosen over a custom Python script** that would look up prices with the AWS pricing API. Infracost is much less code, and it picks up new Terraform resources without anyone keeping a list up to date.
  - **Usage-based costs need a usage file.** Almost everything here is billed by usage, so Infracost would show $0 without one. A committed `infra/infracost-usage.yml` holds monthly usage worked out from the 15-minute schedule and expected story volume, with a comment on each value explaining where it came from.
  - **One-time setup:** Install the CLI and get a free Infracost API key. The key stays in the local Infracost config and is never committed. The command needs no AWS credentials.

## Context

- **Visuals:** None
- **References:** None in the repo (greenfield). External API docs are listed in references.md.
- **Product alignment:** Matches Phase 1 of `agent-os/product/roadmap.md` (MKX only, Telegram delivery, easy to add offices, failure, silent-problem, and cost alerts, and the cost estimate command). The Phase 2 story archive is intentionally pulled in. Per-office channels match the Phase 2 multi-office plan.

## Standards Applied

backend/client-errors, backend/injected-clients, backend/retries, backend/secrets-in-errors. See standards.md.
