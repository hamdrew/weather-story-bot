# Standards Review: N Offices, Yearly Analytics, Best Practices

Date: 2026-09-16. Scope: everything under `agent-os/standards/` as of branch `docs/agent-os-standards`, read against `src/` and `infra/`. These are notes only. No standard or code was changed.

**Status: ideas only.** This came from an informal discussion between Phase 1 and Phase 2. Nothing here changes standards or code until a future spec (likely the Phase 2 multi-office work) picks it up.

**Decided (user's original design intent): one Lambda invocation per office.** A single invocation never handles more than one office.

## Proposed new standard: `infra/budget`

Cost is always a design input, not an afterthought. A draft of what it could say:

- **Fixed monthly cost is O(1) in offices.** Adding an office may add usage cost (invocations, requests, storage, Telegram calls) but never a new fixed monthly line item. That means no per-office alarms, dashboards, custom metrics with an `office` dimension, secrets or KMS keys
  - For scale: at about 120 offices, per-office alarms add roughly $0.10 each per month, and custom metrics with an `office` dimension add roughly $0.30 per office × metric per month (about $180/month for 5 metrics). Check current pricing; the point is that both grow with N
- **Per-office visibility comes from queries and reports, not metrics.** Use Logs Insights `stats ... by office`, the ledger or the daily digest. Alarms stay a small, fixed set that watches aggregates
- **Prefer pay-per-use with no idle cost:** on-demand DynamoDB, EventBridge Scheduler (billed per invocation, not per schedule), Lambda, and S3 lifecycle transitions for old archive images. Nothing always-on (no NAT gateway, no provisioned concurrency, no Glue crawlers, no OpenSearch)
- **Every spec includes a cost section.** It gives the estimated monthly cost at 1 office and at N offices (say 120), what grows with N, and `make cost` (Infracost) output for infra changes. Keep `infra/infracost-usage.yml` updated with realistic usage
- **Inference is batch and capped.** Bedrock runs only in scripts, never per scheduled run. Each run prints an estimate and needs confirmation above a threshold. Labels are cached so nothing is paid for twice
- **Retention is a cost decision.** Logs stay at 30 days. Long-term data is recorded on purpose as small items (ledger, daily run records), never by keeping logs longer
- **The `aws_budgets_budget` alarm stays** as the backstop. If a spec raises expected spend, it raises the budget in the same change, deliberately

## TL;DR

1. **The CLI never causes side effects** (agreed), and its dry run should show what the Lambda would actually *decide*. Today it doesn't: it skips the expired-story filter and the ambiguity checks.
2. **Split each office run into a pure "plan" and an "apply".** The CLI previews the plan, the Lambda applies it, tests can check decisions without moto, and a ledger can record decisions for analytics.
3. **One office per invocation, one writer per office.** EventBridge Scheduler delivers *at least once*, and nothing stops two runs from overlapping today. At N offices, running them all in one sequential loop inside one 300 s Lambda also stops fitting.
4. **Office config leaves `OFFICES_JSON`.** Lambda caps *all* env vars at 4 KB combined, and about 120 offices × about 60 bytes each goes over that.
5. **Record history on purpose.** DynamoDB overwrites the latest revision, logs expire after 30 days, and rejections are never archived. You can't get "fun facts" from data you never kept. Add an append-only posting ledger, and build analytics as a *derived, rebuildable* dataset. Never query the live archive or the dedupe table for it.
6. **Alarms need to account for the office count.** A single global `quiet` alarm can't see one silent office, and a fixed `repost_loop` threshold doesn't scale with N.

---

## Guiding principles I'd add (a new `global/principles.md`, or the index header)

- **Local tools are read-only.** Anything that writes (Telegram, AWS) runs in a deployed environment or a `scripts/` tool whose name says so, never in the dev CLI.
- **Decide purely, then act.** Choosing what to do is a pure function of the inputs (`listing`, `images`, `now`, `stored records`). Side effects happen in a thin, ordered apply step (`backend/side-effect-order`).
- **Sources of truth vs derived data.** The archive (raw NWS) and the ledger (what we did) are the sources of truth and are protected. Analytics tables, indexes and reports are derived: rebuildable, unprotected, and deletable.
- **The office is the unit of isolation.** Concurrency, failure, config, metrics and onboarding are all per office.

---

## Standard by standard

### `backend/cli`: rewrite

What you proposed, plus the fidelity gap I found:

- **Remove `--send-telegram`.** New rule: *the CLI makes no writes of any kind (Telegram, AWS, local state outside stdout/stderr). A future write mode needs a spec that changes this standard first.* That also removes `TELEGRAM_*` env handling, the `.env` token and exit 2 for missing creds, and most of the reason the CLI loads `.env` at all (only `NWS_USER_AGENT` would remain).
- **The dry run mirrors the Lambda's decisions.** `__main__.py` lists stories and prints captions for *all* of them. The Lambda first drops expired stories (`end_time <= now`) and rejects ambiguous listings (`_reject_ambiguous`). So today the CLI can show a caption for a story the Lambda would skip or reject. The rule should be: *the CLI calls the same `plan_office()` as the Lambda and prints each story's decision (`would post`, `expired`, `rejected: duplicate_image`) and its caption.* Without DynamoDB it can't tell `new` from `updated` or `unchanged`, so it should say `new-or-updated (state not read)` and not guess.
- **Validate `--office` with the same validator as `config.py`.** The standard currently says it's "only uppercased, not validated". Without a send path the risk is small, but one validator means one rule, and `--office ../x` should exit 2.
- **For seeing a real post:** that's what a staging deployment is for (see "Environments" below), or a Telegram test channel wired to a staging Lambda. A local caption preview can render the HTML caption to stdout, or to a temp `.html` file if the formatting matters.
- Exit codes become: 0 success, 1 NWS failed (list or any download), 2 usage.

### `backend/env-config`: offices move out of env

- **Hard limit:** Lambda env vars max out at 4 KB total. `OFFICES_JSON` (id + chat_id + name) runs out somewhere past about 50 offices.
- Recommended: offices live in **Terraform as the source of truth** (`var.offices` already is), with **one Scheduler schedule per office** (`for_each`). Each passes `{"office_id": "MKX", "chat_id": "...", "name": "...", "timezone": "America/Chicago"}` as the target `input`. Chat IDs aren't secret (`backend/secrets-in-errors`), so the event payload is fine. The handler validates the event with the same `OfficeConfig` parser and raises `ConfigError` on bad input.
  - Alternatives: an `offices.json` bundled in the zip (config changes need a code deploy), or an SSM parameter (advanced tier holds 8 KB, which only postpones the problem). Both keep a single fan-in Lambda, which is the thing to get away from.
- Add **`timezone` per office.** Captions and "year" analytics need the office's local calendar. A story starting at 7 pm CST on Dec 31 is on Jan 1 in UTC.
- Keep the double validation (Terraform regex + Python regex). Add an **"Adding an office" checklist** next to "Adding a setting": tfvars entry, bot added as a channel admin, a read-only `scripts/check_office.py` (NWS listing reachable, Telegram `getChat` works for the chat_id), and deploy.

### `backend/run-outcomes`: counts per invocation, plus two new outcomes to think about

- With one office per invocation, `"Run complete"` becomes one office's summary. Keep the fixed keys, and add `office` and `aws_request_id` as top-level fields so Logs Insights can `stats ... by office`.
- **Persistent-office failures.** A decommissioned office, NWS 404s or a channel that removed the bot will fail every run forever. Under the "next run may fix it" rule that's `failed`, which keeps the global `errors` alarm stuck on and hides new failures in other offices. Options: a `misconfigured` count (NWS 404 on the office, Telegram 400/403 "chat not found" or "bot was kicked") with its own ERROR line and alarm, or per-office error alarms (see alarms). I'd pick the count: it's cheaper, and it gives a specific runbook.
- **NWS-wide outage.** At N offices, one NWS outage produces N `logger.exception` tracebacks every 15 min. Consider logging one `"NWS unavailable"` line per invocation and still counting `failed`.
- The cold-start token cache note still holds. With per-office invocations there are more warm containers, so after a token rotation the forced config change matters even more.

### `backend/side-effect-order`: add step 0 and an atomic step 4

- **Step 0: take the office lease.** Two invocations for the same office can both see "not posted" and both send. Scheduler guarantees at-least-once delivery, not exactly-once. Options, cheapest first:
  - `reserved_concurrent_executions = 1` on a single-office-at-a-time function. A throttled async invoke is retried later by Lambda's async queue (throttles are retried even with `maximum_retry_attempts = 0`, up to `maximum_event_age_in_seconds`), so the duplicate runs afterwards and skips. **Check the account's concurrency quota first.** Reserved concurrency must leave at least 100 unreserved, so it can't be set on low-quota accounts. This doesn't work once there are N offices on one function.
  - **A DynamoDB lease item per office** (`PK=OFFICE#MKX, SK=LEASE`, conditional put on `attribute_not_exists OR expires_at < :now`, set `expires_at` to the Lambda timeout plus a margin). That scales to N. Losing the lease counts as `skipped` and logs INFO `"Office run already in progress"`.
- **Step 4 becomes one `TransactWriteItems`:** update the current-story item *and* put an immutable ledger item (see "Analytics"), so history can't drift from state. Add a condition on the current item (`attribute_not_exists` or `fingerprint = :previous`) so a stale run can't overwrite a newer record. A failed condition logs a WARNING and doesn't delete anything.
- Record deletes too: after step 5, write a small ledger update (`deleted_at` or `delete_failed`). This is best effort, and a failure is a WARNING, like the delete itself.

### `backend/dynamodb-schema`: design keys from access patterns (the planned spec)

Access patterns I'd expect at N offices + analytics:

| # | Pattern | Frequency |
|---|---|---|
| A1 | Get the current record for (office, story_key) | every run, per story |
| A2 | Take or release the office lease | every run |
| A3 | List all revisions or events for a story | analytics, runbook |
| A4 | List an office's stories in a date range | analytics, runbook |
| A5 | List all offices' posts for a day or year | yearly facts |

Sketch (single table, generic key names so the next migration doesn't rename them again):

| Item | PK | SK | Notes |
|---|---|---|---|
| Current story | `OFFICE#MKX` | `STORY#<start_utc_iso>#<story_key>` | Sortable by start (A4). Look up via a deterministic SK built from the story (A1), still no Scan |
| Revision / event | `OFFICE#MKX` | `EVENT#<start_utc_iso>#<story_key>#<posted_at_iso>` | Immutable (A3, A4) |
| Lease | `OFFICE#MKX` | `LEASE` | TTL'd |
| GSI1 on events | `YEAR#2026` (or `DAY#2026-09-16`) | `<posted_at_iso>#OFFICE#MKX` | A5. At this write volume a year partition isn't hot |

- Rename `office_id`/`image_id` to `PK`/`SK`. The `image_id` sort key name is already misleading.
- Put `schema_version` on every item so migrations can tell shapes apart without guessing from prefixes.
- **TTL on current-story items** (`end_time` + 30 days). The dedupe table stays small at N offices, and TTL deletes need no `DeleteItem` grant (`infra/iam` stays clean). Keep the 30-day margin so a story NWS extends or re-lists shortly after expiry doesn't repost. Event items get **no** TTL, or you move them to S3 on purpose (below).
- Alternatively, **DynamoDB is state only and the ledger lives in S3.** That's simpler to reason about for analytics, but then step 4 can't be atomic. I prefer the transaction.

### `backend/archive-layout`: keep it, and add a separate analytics layout

- **Don't move the archive.** Its human-browsable layout is good. It's just not an analytics source: `.png` and `.json` share a prefix, and Athena/Glue read every object under a table location. Athena only skips files starting with `_` or `.`, so it can't filter by extension.
- New rule: *analytics reads a **derived** dataset under `analytics/`, rebuilt from the archive + ledger by a script. It is never written by the Lambda or read by it.* The layout is Hive-style: `analytics/revisions/office=MKX/year=2026/part-*.parquet` (or JSONL).
- "Never add derived fields to `.json`" stays exactly right. Derived fields belong in `analytics/`.
- Add to the story identity docs: **the global story id is `(office_id, story_key)`**. `story_key` alone isn't unique across offices, even though the path and partition key hide that today.

### `backend/story-identity`: small additions

- Global identity = `office_id` + `story_key` (above).
- Freeze the hash encoding explicitly (`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)`) *in the standard*, and add a test that pins a known hash. The defaults are stable today, but a "harmless" refactor to `separators` would silently repost every active story and orphan every stored key.
- Analytics will want a **title normalization** for grouping ("Snow Tonight" vs "Snow tonight"). That's a derived field in `analytics/`, never an input to `story_key`.

### `backend/structured-logging`

- Add `aws_request_id` (from `context`) and, once invocations are per office, `office` on every line through a `LoggerAdapter` or a contextvar filter, so it doesn't depend on each call remembering to pass it.
- Consider **CloudWatch EMF** for `posted/updated/rejected/failed` counts per office in place of log metric filters. It removes several log contracts. The cost: each office × metric pair is a billed custom metric (about $0.30/month each), so 120 offices × 5 metrics ≈ $180/month. Too much at N. So: **keep metric filters without an office dimension for alarms, and use Logs Insights or the ledger for per-office views.** Write that decision into the standard so nobody "improves" it later.

### `backend/retries`

- The core stays right. One addition for N offices: **spread load and don't stampede NWS.** Either give each office's schedule a deterministic minute offset (`cron(3/15 ...)`, `cron(7/15 ...)`) or use `flexible_time_window { mode = "FLEXIBLE", maximum_window_in_minutes = 5 }`. Put that in the standard so N schedules don't all fire at :00.
- If a queue ever appears (SQS fan-out), "retries = 0" means `maxReceiveCount = 1` plus a DLQ with an alarm. Say so explicitly, because a queue with zero retries and no DLQ silently drops work.

### `backend/injected-clients`

- Add: **no threads or asyncio inside the Lambda for parallelism. Parallelism comes from invocations.** That keeps the shared `httpx.Client`, `sleep` injection and the cold-start cache simple.

### `backend/untrusted-nws-data`

- Scope stays **per office per listing**. Add a note that the checks never compare across offices: neighboring WFOs can legitimately share a regional graphic, and the image-SHA check would reject both if it ever went global.
- **Persist rejections** (ledger `REJECT#` event, or a line in `analytics/`), not just the ERROR log. Log retention is 30 days, so "how often did NWS send us garbage this year" is unanswerable today.

---

### `infra/alarms`

- **`quiet` can't see one silent office at N.** A per-office quiet alarm is noisy too, because some WFOs rarely publish stories. Recommendation: keep the global one, and add a **daily health digest** built from the ledger (offices with no posts in X days vs their own history) sent to the alert email. That's a report, not an alarm.
- **Scale `repost_loop` with office count:** `threshold = var.repost_alarm_max_posts_per_office * length(var.offices)`. A repost loop in one office can still hide under a big N, so the `"Story posted"` vs `"Telegram message sent"` runbook check stays.
- `errors` ("2 runs in a row") changes meaning once many invocations happen per 15 min, so re-tune it on invocation count or error rate, and see the `misconfigured` count above.
- `missed_runs`: with per-office schedules, a single deleted schedule wouldn't trip a function-level alarm. Terraform `for_each` makes that unlikely, but note the gap in the description.

### `infra/data-retention`

- The table becomes **state + ledger**. Keep deletion protection and PITR. TTL applies to current-story and lease items only, never to events.
- **Log retention** (30 days today) becomes a stated decision: fine for debugging, and analytics must never depend on logs.
- `analytics/` prefix: derived, so no versioning dependency, and it's OK to delete and rebuild. Put it in a separate bucket or a prefix the Lambda role can't reach (`infra/iam`).
- Consider an S3 lifecycle transition of archive `.png`s to a cheaper class after a year (never expiration). At N offices the archive grows roughly N-fold.

### `infra/iam`

- The Lambda role gets **no** access to `analytics/` and no `Scan`. The analytics build script runs with admin or a separate read-only role, like migrations.
- `dynamodb:TransactWriteItems` isn't its own IAM action. It's authorized via `PutItem`/`UpdateItem`/`ConditionCheckItem` on the table, so worth a comment when it's adopted.
- If CI/CD lands (roadmap phase 2): the OIDC role trust is pinned to `repo:hamdrew/weather-story-bot:environment:production`, and **CI never has Telegram creds**. That fits "tests are offline" and the new CLI rule.

---

### `testing/handler-tests`

- Keep "real clients over respx + moto" for integration. Add **pure tests of `plan_office()`** (table-driven: listing + stored records + now → decisions). Most decision edge cases (expiry, ambiguity, unchanged vs updated) stop needing moto.
- Add multi-office cases: one office's NWS 503 doesn't affect another's posts, the same `story_key` in two offices is two stories, and a lost lease skips.
- Add a concurrency test: two "runs" interleaved at the lease or conditional write produce one send.

### `testing/test-data`

- `mkx_payload`/`mkx_stories` are office-specific names. Generalize to `listing_payload("MKX")` with fixture files per office, and capture a second office's real listing (different time zone, `priority: true`, empty `altText`) when adding offices.
- The "production quirks become dated cases" rule is excellent. Add the office to the comment, since quirks may be per-WFO.

### `testing/offline-tests`

- Once `--send-telegram` goes away, the CLI tests assert that no Telegram host is ever called, rather than "missing creds exit 2".
- Add `TELEGRAM_*` env clearing to the autouse fixture instead of CLI tests only. It's cheap insurance.

### `testing/log-contracts`

- Unchanged. The ledger reduces how many log lines are contracts, because runbooks can query the ledger instead of comparing `"Story posted"` with `"Telegram message sent"`.

---

## Analytics: what "fun facts" need that isn't captured today

| Fact | Needs | Captured today? |
|---|---|---|
| Stories per office / month / year, busiest day | posted_at, office, start | Partly (archive path gives start date; posted_at only for the *latest* revision in DynamoDB) |
| Most-revised story | every revision event | Archive has one file pair per revision, but not when it was posted |
| Longest-lived story, stories pulled before `endTime` | first seen, last seen | **No** (last seen is never recorded) |
| Most common words in titles ("snow", "severe") | titles | Yes (archive JSON) |
| First snow story of the season per office | titles + local date | Yes, if local timezone is known |
| Priority stories | `priority` | Yes (raw JSON) |
| How often NWS sent ambiguous data | rejections | **No** (logs, 30-day retention) |
| Posting lag (NWS `startTime` to our post) | posted_at per revision | **No** for superseded revisions |
| Delete failures (the 48h limit) | delete outcome | **No** (WARNING log only) |

**Ledger event** (one immutable item per action), minimal fields:

```
office_id, story_key, event: posted|updated|rejected|deleted|delete_failed,
at (UTC), fingerprint, telegram_message_id?, archive_prefix?, reasons?, schema_version
```

**Optional observation tracking** (for "last seen"): update `last_seen_at` on the current-story item only when it's at least an hour stale. That's about 24 writes per story per day instead of 96, which is cheap on on-demand billing at 120 offices. It's worth doing only if "stories pulled early" matters to you.

**Build path, cheapest first:**

1. A `scripts/build_analytics.py` (read-only on sources, `--apply` to write `analytics/`) that reads the ledger + archive JSON and writes Parquet. Query locally with **DuckDB** (`read_parquet('s3://.../analytics/**/*.parquet', hive_partitioning=true)`). No Glue, no Athena, no always-on cost.
2. Only if you want it in the console: an Athena table with partition projection over `analytics/` (not the archive).
3. The yearly "fun facts" post itself is a side effect. It belongs in its own scheduled Lambda or script and gets its own place in `backend/side-effect-order`, never in the CLI.

---

## Environments (not a standard yet, but the CLI change leans on it)

- A **staging** deployment (separate tfstate key or workspace, `-staging` name suffix, a test Telegram channel, 1-2 offices, schedule disabled by default and invoked manually) replaces "run it locally and watch it post". It also gives CI/CD a place to apply before production.
- Standard: *production resources are only changed by `make deploy` (or CI); staging is where you watch real posts.*

---

## Suggested order

1. **Now, small:** CLI rewrite (no side effects, mirrors decisions); a reserved-concurrency or lease guard against duplicate invocations; pin the hash encoding with a test.
2. **Before a second office:** `plan_office()` split; per-office timezone; the "adding an office" checklist; per-office schedules with staggered times; the `misconfigured` outcome decision.
3. **Before about 50 offices:** config out of `OFFICES_JSON` (hard 4 KB wall); alarm thresholds scaled with N; digest in place of per-office quiet alarms.
4. **Analytics spec:** new DynamoDB keys + ledger (one migration, following `backend/dynamodb-schema`); TTL on state; `scripts/build_analytics.py` + DuckDB. Start the ledger early, because facts about a year need a year of data, and history you didn't record can't be backfilled.

## Open questions for you

- ~~Do "stories pulled before `endTime`" and "last seen" matter enough to pay for observation writes?~~ **Yes** (2026-09-16): record last seen. Analytics goals and the data they need live in `2026-09-16-year-in-review-ideas.md`, including a per-office daily run record that replaces any log aggregation.
- Should rejections reach the channel's analytics at all, or only the ops side?
- Is a staging stack acceptable cost-wise (it's small: a Lambda, a table, a bucket, a schedule that's off by default)?
- For channel promotion to a wider audience: one bot for all channels, or a bot per region (limits the blast radius of a token leak, but more secrets to rotate)?
