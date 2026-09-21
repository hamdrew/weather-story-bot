# References for Decide, Act, and Record

## Similar Implementations

### The current interleaved run

- **Location:** `handler.run` and `_process_story` in `src/weather_story_bot/handler.py:72-191`
- **Relevance:** This is what Task 3 and Task 4 pull apart. Every decision in it becomes a pure
  planner outcome; everything else stays as the apply step.
- **Key patterns to preserve:** the expiry filter runs *before* any download
  (`handler.py:88-90`); `_reject_ambiguous` needs image bytes, so it can only run after;
  `_AMBIGUITY_CHECKS` (`handler.py:120-124`) is a clean table that moves unchanged; failures are
  isolated per office and per story, and each one only ever costs a `failed` count.

### The Phase 1.1 migration

- **Location:** `scripts/migrate_story_keys.py` and `tests/test_migrate_story_keys.py`;
  runbook in `agent-os/specs/2026-09-15-1149-story-updates-and-nws-validation/shape.md`
- **Relevance:** Task 9 follows it exactly — the second migration of this table, run five days
  after the first.
- **Key patterns:** dated module docstring with before/after and a runbook; dry run by default;
  `--apply` to write; `--delete-old` as a separate later step once the new Lambda is proven;
  `MigrationError` raised before any write when the data does not look as expected; every step
  idempotent; moto-backed tests with seeded old-shape data; run with admin creds, not the Lambda
  role.
- **Cutover pattern:** pause the EventBridge schedule outside Terraform, `--apply`, then deploy,
  so no run of either version lands in between. Terraform does not set the schedule's `state`,
  so its default `ENABLED` turns it back on.

### The existing store, as the shape to copy and move away from

- **Location:** `PostedStore` in `src/weather_story_bot/state.py:62-114`
- **Relevance:** Task 6 keeps its typed-attribute, `ConsistentRead=True` style and changes only
  the keys. Task 7's `history.py` is a deliberate sibling, not an extension: `state.py` is the
  safety chain and `history.py` is explicitly not.

### Log-contract tests

- **Location:** `tests/test_handler.py:347`, `393-431`, `498-501`; `tests/test_telegram.py:198`,
  `220`
- **Relevance:** These are the assertions that must still pass verbatim after the refactor. They
  are the mechanical proof that the alarms did not go blind.

## Source Notes

### Standards review, 2026-09-16

- **Location:** `agent-os/notes/2026-09-16-standards-review.md`
- **Relevance:** Origin of the plan/apply split, the CLI rewrite, the hash pin, the concurrency
  guard, the ledger and `global/principles.md`. Its "Suggested order" #1 and "Analytics" sections
  are this spec's direct sources.
- **Superseded here:** its `backend/dynamodb-schema` section proposed deferring the key redesign;
  this spec brings it forward. Its TTL proposal is **declined for now** — records stay permanent.

### Year in Review ideas, 2026-09-16

- **Location:** `agent-os/notes/2026-09-16-year-in-review-ideas.md`
- **Relevance:** "Data needed vs captured" defines the three writes, and the "Daily run record"
  section specifies the 96-slot bitmap. Its open question on UTC vs local days is answered here:
  **UTC**.
- **The deadline behind this spec:** the bot went live 2026-09-13 and NWS lists only *active*
  stories, so nothing can be backfilled. A full-year 2027 edition needs recording live well
  before 2027-01-01.

## External

### Lambda asynchronous invocation and throttles

- **Location:** https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html and
  https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html
  (checked 2026-09-20)
- **Key points:** EventBridge Scheduler invokes Lambda **asynchronously**. In the async queue,
  `MaximumRetryAttempts` governs **function errors only**; throttles (429) and system errors are
  returned to the queue and retried with exponential backoff for up to **6 hours**. So a
  throttled run is delayed, not dropped, and `missed-runs` stays honest.
- **Trap:** reserved concurrency of **0** disables async retries entirely. It must be 1.
- **Account check** (`aws lambda get-account-settings`, us-east-2, 2026-09-20): 1000 concurrent,
  1000 unreserved — reserving 1 leaves 999, well clear of the 100-unreserved floor.

### Production table, measured 2026-09-20

- `weather-story-bot-posted`: **42 items, 21,736 bytes**, all `story#` items in MKX (about 517
  bytes each). No legacy bare-UUID or `content#` items remain, so Phase 1.1's `--delete-old` ran.
- Growth: about **6 new story items a day** at one office since 2026-09-13. A title or start-time
  edit creates a new `story_key` by design, so this counts re-titled variants as new stories.
- Projection for Task 9 and for Phase 3 sizing: roughly 8,800 story items a year at four offices,
  plus ledger events and 1,460 daily records — order of 10-25 MB a year. A full `Scan` stays cheap.

### DynamoDB secondary index backfill

- **Relevance:** A GSI added later indexes only items that carry its key attributes, which is why
  event items must be written with `GSI1PK`/`GSI1SK` from the very first write. Without that,
  Phase 2.2 would still need a migration.
