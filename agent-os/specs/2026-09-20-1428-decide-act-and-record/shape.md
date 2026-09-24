# Decide, Act, and Record — Shaping Notes

Shaped 2026-09-20. Roadmap Phase 1.2.

## Scope

Split the office run into a pure decision and a thin apply, make the local dry run tell the
truth, stop the CLI writing anything, freeze the story identity hash, allow only one run at a
time, and start recording history as data — on a new DynamoDB table carrying the key design
that was going to arrive in Phase 2.2.

## Decisions

### Shaped with the user

- **One spec for all of Phase 1.2, delivered in four deploy stages.** The refactor and the
  recording touch the same code, so splitting them into separate specs means restructuring
  `handler.py` twice, or triplicating the shaping that spans them. But thirteen tasks in one
  deploy is too much to attribute a problem to, so the plan groups them into stages that each end
  deployable and revertible: (1) behaviour-neutral refactor, (2) create the table, (3) migrate and
  flip, (4) recording and the lease. The spec is the thinking; the stages are the delivery.
  - **Stage 2 exists only to shrink stage 3's pause.** Creating the table is additive and provably
    correct on its own, so the window with the schedule off is just migrate-and-flip, and the
    rollback is one environment variable.
  - **Each standard changes in the task that makes it true**, not in a sweep at the end.
  - Until Phase 2.0's staging environment exists, careful deploy staging is the substitute.
- **Migrate to a new table now, with Phase 2.2's full key design.** Generic `PK`/`SK` names,
  sortable sort-key values, `schema_version` on every item. The trigger was the user's own
  question: it is worth doing while things are still MVP-ish.
  - The cost of this migration only ever rises. Measured 2026-09-20: **42 items, 21,736 bytes**,
    all `story#` items in MKX — about 6 new a day since launch on 2026-09-13. By Phase 2.2 that
    is a few thousand items plus three months of ledger events, which never expire.
  - Phase 2.2's remaining DynamoDB work becomes **additive**, with no migration.
  - The old table is not touched. It is the rollback, and `infra/data-retention` forbids
    replacing a table with deletion protection on.
- **No TTL. DynamoDB records are permanent.** Confirmed during shaping that none exists today:
  `infra/storage.tf` has no `ttl` block and `PostedStore.record_posted` writes no expiry
  attribute. The only expiration in the repo is the S3 lifecycle rule for *noncurrent* object
  versions. The new table gets no `ttl` block either, and the resource comment says so, because
  the Phase 2.2 sketch proposes one and someone will otherwise "restore" it. This can change
  later once the S3 archive is strong enough to be the record of last resort.
- **Daily run records use the UTC day and 96 fixed UTC slots.** Slot N is always the same 15
  minutes, so there are no DST gaps or doubled slots, and no per-office timezone is needed —
  that arrives in Phase 2.2. Converting to local dates is a build-time, derived-data concern.
- **The CLI survives**, rewritten as a thin read-only printer over the shared planner. Its one
  irreplaceable job is pointing at live NWS for any office and showing what the bot *would*
  decide, with no AWS and no deploy — which is the first question asked during the 2026-09-14
  and 2026-09-15 incidents. Deleting it would also mean growing it back: Phase 2.2 already wants
  a read-only `check_office.py`. The drift risk that made the dry run lie dies once it calls the
  same planner instead of forking the logic.
- **`--dry-run` stays required.** The deliberate speed bump in `backend/cli`; a future write mode
  is a new, explicit flag and never the default.

### Settled with evidence, as the roadmap demanded

- **A per-office DynamoDB lease, not reserved concurrency.** The evidence says reserved
  concurrency would work *today*; the decision is to skip it anyway, because it cannot express the
  requirement. `= 1` gives *global* exclusion, so once Phase 2.2 makes each office its own
  invocation, MKX blocks GRB. `= 4` allows four concurrent runs with no guarantee they are four
  *different* offices, so two MKX runs can both get a slot and double-post. There is no value
  meaning "one run per office" — it is binary. Building it now would mean shipping a guard, writing
  a standard around it, and deleting both in Phase 2.2, which reads as churn later. **The lease
  moves up from Phase 2.2.**
  - **The lease needs no DynamoDB TTL,** so the no-TTL decision stands. Expiry is a conditional
    write against an ordinary `expires_at` attribute.
  - **It lives in `state.py`, not `history.py`** — it is a safety-chain guard, and `history.py` is
    explicitly the module whose writes are allowed to fail silently.
  - Losing the lease is `skipped` with an INFO line; a DynamoDB *error* taking it is `failed`.
  - **We are not exposed while building it:** the Lambda timeout (300s) is shorter than the cadence
    (900s), so a slow run cannot overlap the next. Only Scheduler's rare at-least-once duplicate
    delivery can double-post, which is why this has been survivable since launch.
- **What the evidence actually established** about throttled invocations, which still matters for
  any future design:
  - EventBridge Scheduler invokes Lambda **asynchronously**, so the schedule's
    `maximum_retry_attempts = 0` stops governing once Lambda returns 202.
  - In Lambda's async queue, `MaximumRetryAttempts` covers **function errors only**. Throttles
    (429) and system errors go back on the queue and retry with exponential backoff for up to
    **6 hours**.
  - So `missed-runs` — which counts `Invocations` over an hour, with four runs per hour — stays
    honest either way.
  - The account allowed it: 1000 concurrent, 1000 unreserved. We are declining it, not blocked.
  - **Recorded for the future: reserved concurrency of 0 is an off switch**, not "no limit", and it
    disables async retries entirely.

### Found while shaping

- **Today's sort key can already hold sortable values.** The roadmap says Phase 1.2's events
  "pile into one partition per office that can't be queried by time". The *attribute* named
  `image_id` is misleadingly named, but its values are ours to choose, and
  `EVENT#<start>#<story_key>#<at>` under `PK=MKX` is range-queryable today. This is what made
  the full key redesign worth pulling forward rather than settling for a rename.
- ~~**Event items must carry `GSI1PK`/`GSI1SK` from the first write.**~~ Reversed 2026-09-23:
  DynamoDB is the wrong analytics engine, and Phase 3 already reads a dump in S3, so nothing would
  query `GSI1`. A GSI can also key on ordinary attributes events carry anyway (`PK`, `event_at`),
  so a future index backfills without special attributes. The only index that must be decided
  at creation is an LSI, and the table gets none.
- **The planner must not log.** The `Ambiguous stories from NWS` ERROR line feeds the
  `nws-ambiguous` metric filter, so it stays in the handler, emitted from the planner's returned
  rejections. A pure function that logs is not pure, and the CLI must not fire alarms.
- **`plan` is two steps, not one.** Ambiguity rejection needs image bytes, but expired stories
  must never be downloaded. So: `select_active` (pure, no images) → caller downloads →
  `decide` (pure, over `(Story, image)` pairs).
- **The Lambda role needs `dynamodb:UpdateItem`.** It has only `GetItem` and `PutItem` today
  (`infra/iam.tf:26-29`), and both last-seen and the daily record's `ADD` need `UpdateItem`.

## Context

- **Visuals:** None.
- **References:** See `references.md`. Chiefly the current `handler.py`, the Phase 1.1 spec's
  migration pattern, and `scripts/migrate_story_keys.py`.
- **Product alignment:** Roadmap Phase 1.2, executed as written except that the DynamoDB key
  redesign moves here from Phase 2.2. Serves the Phase 3 Year in Review, whose 2027 edition
  needs a year of history that cannot be backfilled — the NWS API lists only *active* stories.

## Standards Applied

Rewritten or amended by this spec:

- `backend/cli` — rewritten: no writes of any kind, mirrors the planner's decisions
- `backend/story-identity` — the frozen hash encoding and its pin test
- `backend/side-effect-order` — where the best-effort history writes sit (outside the chain)
- `backend/structured-logging` — `office` and `aws_request_id` set once, not passed per call
- `backend/injected-clients` — the history store takes its client like every other wrapper
- `backend/dynamodb-schema` — the new keys become current; the MVP section retires
- `testing/handler-tests` — pure planner tests beside the real-client integration tests
- `testing/offline-tests` — `TELEGRAM_*` clearing moves into the autouse fixture
- `global/principles` — **new**: local tools are read-only; decide purely then act; sources of
  truth vs derived data; the office is the unit of isolation

Constraining but unchanged:

- `backend/run-outcomes` — the five fixed counts survive the refactor untouched
- `backend/untrusted-nws-data` — the ambiguity rule moves modules without changing behaviour
- `testing/log-contracts` — three messages survive word for word or move with `monitoring.tf`
- `infra/data-retention` — why the old table stays; why `make plan` must show zero replacements
- `infra/iam` — exact actions on the narrowest ARNs for the new table
