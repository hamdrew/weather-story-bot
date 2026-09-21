# Product Roadmap

## Phase 1: MVP

- **Detect new stories:** Check the NWS MKX (Milwaukee/Sullivan) office on a schedule and notice when a new Weather Story is published.
- **Push notification via Telegram:** Post each new story's image and description to Telegram. Telegram handles both the notification and the display.
- **MKX only:** Only one office is needed for launch. The design should still make it easy to add more offices later.
- **Failure alerts:** Watch the Lambda and email me when it fails or stops running on schedule. The Gmail app shows the email as a push notification on my iPhone. Alerts don't go through Telegram, because Telegram could be the thing that's broken. Send a follow-up email when things recover, and don't alert on a single flaky run.
- **Silent-problem alerts:** Email me when the bot runs without errors but something is still wrong:
  - **Gone quiet:** No stories posted for a couple of days (for example, the NWS API changed and now returns nothing).
  - **Repost loop:** Far more posts than normal in a short time.
- **Cost alert:** Email me if monthly AWS spend for the account goes over a small budget.
- **Cost estimate command:** A command I can run whenever I want (`make cost`) that shows the estimated monthly AWS cost of what's in `infra/`, using Infracost. It doesn't run before deploys or in CI.

## Phase 1.1: Soak Hardening

Fixes from the first days of running the MVP (spec `2026-09-15-1149-story-updates-and-nws-validation`).

- **Updates notify:** When a story's image or description changes, post it again as "🔄 Updated:" and delete the old message.
- **Reject ambiguous NWS content:** If active stories share an image ID, a title and start time, or the same image, post none of them and email me right away.
- **Ignore expired stories:** Take no action on stories past their end time.
- **Archive by story:** Keep one S3 folder per story (title and start time) with one file pair per distinct revision, and migrate the existing archive and records to match.

## Phase 1.2: Decide, Act, and Record

In progress (spec `2026-09-20-1428-decide-act-and-record`). The refactor that makes the dry run
honest, plus the writes that start saving history. **Shaping moved the DynamoDB key redesign here
from Phase 2.2**, since the table holds just 42 items today (measured 2026-09-20) and this phase
starts writing append-only items that never expire.
Sources: `agent-os/notes/2026-09-16-standards-review.md` ("Suggested order" #1, "Analytics") and
`agent-os/notes/2026-09-16-year-in-review-ideas.md` ("Data needed vs captured").

- **Decide purely, then act:** Split each office's run into a pure "plan" that decides what should
  happen and a thin "apply" that does it. Today the two are interleaved: expiry filtering,
  ambiguity rejection and the new/updated/unchanged call are all decisions tangled up with
  archiving, sending and recording. Expired stories must still never be downloaded, so the plan is
  two steps: pick the active stories, then decide each one (`post`, `update`, `unchanged`,
  `expired`, `rejected`). **Two log messages are alarm contracts** and either survive the refactor
  word for word or move in the same change as `infra/monitoring.tf`: "Ambiguous stories from NWS"
  feeds the `nws-ambiguous` alarm, and "Telegram message sent" feeds *both* `quiet` and
  `repost-loop`. Rename either one silently and an alarm goes blind or fires spuriously.
- **The dry run stops lying:** `--dry-run` prints captions for every listed story today, including
  ones the Lambda would drop as expired or reject as ambiguous. It should call the same planner
  and print each story's decision next to its caption. Without DynamoDB it can't tell a new story
  from an updated one, so it says so rather than guessing.
- **The CLI makes no writes of any kind:** `--send-telegram` goes away, along with the Telegram
  environment variables and credential handling. A future write mode needs a spec that changes the
  CLI standard first. `--office` gets validated the same way the Lambda validates it. CLAUDE.md
  documents the flag and its environment variables verbatim, so it changes in the same commit.
- **Pin the story identity hash:** Freeze how the fingerprint is encoded, with a test that asserts
  a known hash. A tidy-up of that encoding would otherwise silently repost every active story and
  orphan every stored record.
- **One run per office at a time:** The scheduler promises to deliver each run *at least* once, and
  nothing today stops two overlapping runs from both deciding to post. Limiting the function to a
  single concurrent run is the cheap fix, but **check what actually happens to the loser before
  committing to it.** Both the scheduler target and the function's async config set
  `maximum_retry_attempts = 0`, so a throttled invocation may simply be dropped rather than
  retried — and a dropped run is invisible to the `missed-runs` alarm, which counts invocations
  over an hour and wouldn't notice one missing out of four.
  **Settled while shaping, 2026-09-20: skip reserved concurrency, build the lease here instead.**
  Reserved concurrency cannot express the requirement: `= 1` gives *global* exclusion, so once
  per-office invocations arrive one office blocks another, and `= N` allows N concurrent runs with
  no guarantee they are N *different* offices. There is no value meaning "one run per office", so
  shipping it now means deleting it plus its standard in Phase 2.2. **The per-office lease moves up
  from Phase 2.2 into this phase.** Meanwhile nothing is exposed: the 300s timeout is shorter than
  the 900s cadence, so only Scheduler's rare duplicate delivery can double-post.
  The throttling evidence still holds and is recorded for future designs. Scheduler
  invokes Lambda *asynchronously*, so once Lambda returns 202 the schedule's retry policy stops
  governing. In Lambda's async queue `maximum_retry_attempts` covers *function errors only*;
  throttles (429) and system errors go back on the queue and retry with exponential backoff for
  up to 6 hours. A throttled run is delayed, not dropped, `missed-runs` stays honest, and the
  `missed-runs` stays honest. The account would have allowed it (1000 concurrent, 1000 unreserved);
  we declined it rather than being blocked. **Reserved concurrency of 0 is an off switch**, not "no
  limit", and disables async retries entirely.
- **Record what happened, as data:** The bot keeps the current record per story (overwritten on
  every revision), the raw archive (which never says *when* something was posted), and logs (gone
  after 30 days). So "which story was revised the most", "which were pulled early", "how often did
  NWS send garbage" and "when was the bot blind" are all unanswerable. Three small append-only
  writes fix that, onto the new table:
  - **A ledger event per action** — posted, updated, rejected, deleted, delete-failed — with the
    office, story, time, fingerprint, message id and reasons.
  - **Last seen,** updated only when it's at least an hour stale, so a story pulled before its end
    time is visible.
  - **A daily record per office** counting runs, NWS failures, stories seen and rejections, with a
    bit per 15-minute slot marking the runs where NWS couldn't be reached. Outages are just runs of
    consecutive set bits.

  These are best effort. A failed write logs a warning and never blocks a post — they are
  deliberately not part of the safety chain.

  **This originally planned to write events under today's keys and let Phase 2.2 rewrite them,**
  accepting a second migration as the price of capturing history roughly two months sooner —
  because history not written down when it happens can't be recovered later at any price. Shaping
  reversed that: the migration is cheaper now than it will ever be again, so it happens here. See
  the next item.
- **Redesign the DynamoDB keys now, once** (moved here from Phase 2.2 during shaping). A new
  table with generic `PK`/`SK` names, sortable sort-key values (`STORY#`, `EVENT#`, `DAY#`) and a
  `schema_version` on every item. Two things settled it: the table holds 42 items today and never
  will again — it is growing by about 6 a day — so this migration's cost only rises; and the sort key's *values* are ours to
  choose even though its attribute is misleadingly named `image_id`, so sortable keys cost nothing
  extra now. Event items also carry `GSI1PK`/`GSI1SK` from the very first write, because an index
  added later backfills only items that already have its key attributes — without that, Phase 2.2
  would need a migration after all.
  - **No TTL. Records stay permanent.** There is none today, and the Phase 2.2 sketch's TTL
    proposal is declined for now. Revisit once the S3 archive is the record of last resort.
  - The old table isn't touched. It's the rollback, and `infra/data-retention` forbids replacing
    a table that has deletion protection on.
- **Office and request id on every log line,** set once rather than passed by each caller. Every
  later per-office query and the warning digest depend on it.
- **Standards:** rewrites `backend/cli`; amends `backend/story-identity`,
  `backend/structured-logging`, `backend/side-effect-order`, `backend/injected-clients`,
  `backend/dynamodb-schema`, `testing/handler-tests` and `testing/offline-tests`. Adds a `global/principles.md`: local tools
  are read-only, decide purely then act, sources of truth vs derived data, and the office is the
  unit of isolation.

## Phase 2.0: Staging and Production

A place to watch a real post, now that the CLI can't send one. Source: standards review,
"Environments".

- **Two named deployments from one `infra/`:** an environment name threaded through every resource,
  a separate state key, and a tfvars file each.
- **Production keeps the resource names it has.** Threading an environment name through everything
  would rename the posted-stories table and the archive bucket, and a rename is a *replace* — the
  table has deletion protection on, the bucket is versioned and not empty, and
  `infra/data-retention` says to stop and ask rather than apply a replace. So either production
  stays unsuffixed and only staging takes a suffix, or the names move behind a variable defaulting
  to today's values. Either way, shaping ends with a `terraform plan` showing zero replacements.
- **Staging** runs a subset of production's offices — at least one, and just MKX until Phase 2.2
  adds the others — into private test channels, with its schedule off by default and invoked by
  hand. **Production** runs the full set into the public channels.
- **A separate Telegram bot for staging,** with its own SSM parameter, so a staging bug or a wrong
  chat id physically cannot reach a public channel and a leaked staging token is worthless. (Open:
  one bot with different chat ids is cheaper to manage — settle it while shaping.)
- **Staging stays near-free.** DynamoDB on-demand, S3, Lambda and the scheduler all cost nothing
  when idle; the only real fixed additions are alarms past the free tier. Keep staging's alarm set
  minimal and confirm with `make cost`.
- **Two alarms have to be off or re-tuned in staging.** `missed-runs` and `quiet` both treat
  missing data as breaching, and staging's schedule is off by default — so a staging stack would
  sit permanently in ALARM on both, emailing the shared topic on every flap and training me to
  ignore the alerts that matter in production.
- **New standard `infra/budget`,** which a second environment makes concrete: fixed monthly cost
  stays O(1) in offices, per-office visibility comes from queries rather than metrics, prefer
  pay-per-use with no idle cost, every spec carries a cost section, retention is a cost decision,
  and the budget alarm rises deliberately when a spec raises expected spend.
- **New rule:** staging is where real posts get watched. Production becomes pipeline-only when
  Phase 2.1 lands — until then it's still `make deploy`, and the rule is written down ahead of
  being enforceable.

## Phase 2.1: Deploy from GitHub Actions

Replaces `make deploy` from my laptop, before anything migrates the database or adds offices.

- **Two fixes first:** make the Lambda zip reproducible, or every plan shows a change that isn't
  one; and make `plan`/`deploy` build first or fail outright when the zip is missing, so neither
  the pipeline nor the break-glass path can quietly deploy stale code.
- **One workflow that reuses the Makefile.** Pull requests run lint, test, build and
  `terraform plan`. Merges to `main` run the same steps plus `terraform apply` in a protected
  environment with a required review. Staging applies before production.
- **AWS access through GitHub OIDC** with a narrowly scoped IAM role managed in Terraform, so
  there are no long-lived keys. Values that aren't committed come from Actions variables.
  **CI never holds Telegram credentials.**
- **Versioned zips in S3,** keyed by git SHA, so Terraform never needs a local file, plan and apply
  can be separate jobs with an approval between them, and a rollback is re-applying an older SHA.
- **Decided against a cloud Terraform runner** (HCP Terraform, Spacelift and friends). It can't
  build the zip, so GitHub Actions would still do the build, test and upload — the runner would
  only replace plan and apply. State stays in the S3 backend, which already handles locking at this
  size. If the approval and drift-detection story ever gets painful, the S3-zip seam means swapping
  a runner in is a config change, not a rewrite.
- **Production becomes pipeline-only from here.** Manual `make deploy` stays as the documented
  break-glass path — used deliberately, not routinely.

## Phase 2.2: Wisconsin and Minneapolis Offices

Sources: standards review, sections on `env-config`, `dynamodb-schema`, `side-effect-order`,
`run-outcomes`, `retries`, `alarms` and `test-data`.

- **Four offices, not 120:** MKX (Milwaukee/Sullivan), GRB (Green Bay), ARX (La Crosse) — which
  between them cover nearly all of Wisconsin — and MPX (Twin Cities/Chanhassen), where my brother
  and sister live. Enough to prove the per-office design without pretending to be national. Verify
  the exact Wisconsin county coverage while shaping; DLH covers the far northwest and MPX covers
  some west-central counties. A separate channel per office.
- **One invocation per office.** Offices move out of the `OFFICES_JSON` environment variable — a
  Lambda's environment caps out at 4 KB total — and become one schedule per office, each passing
  its office as the event payload. Stagger the schedules so the offices don't all hit NWS at once.
- **A time zone per office.** Captions and every "year" fact need the office's local calendar; a
  story starting at 7 PM on December 31 lands on January 1 in UTC.
- **DynamoDB work here is additive — Phase 1.2 already did the key redesign and the migration.**
  What's left: create the `GSI1` index for "all offices on this day or year" (Phase 1.2 already
  writes its key attributes, so it backfills on creation). The lease item also already exists. Revisit expiring
  current records and leases then, if the archive has become the record of last resort. Events
  never expire either way.
- **The per-office lease already exists** (moved into Phase 1.2). What remains here is that
  recording a post becomes one atomic
  write so state and history can't drift apart. This deliberately reverses Phase 1.2's best-effort
  ledger: an atomic write puts the ledger back into the safety chain, so a ledger failure now fails
  the record after Telegram has already accepted the message. That's survivable under "a repost is
  OK, a missed story is not", but the reversal gets written into `backend/side-effect-order`
  rather than happening quietly.
- **A "misconfigured" outcome** for offices that fail every single run — a decommissioned office,
  a 404, a channel that kicked the bot — so they don't hold the error alarm on forever and hide
  real failures elsewhere.
- **Scale the alarm thresholds with the office count,** and note that a single global "gone quiet"
  alarm can't see one silent office.
- **Adding an office becomes a checklist:** tfvars entry, bot added as a channel admin, a read-only
  check script that confirms NWS and Telegram both answer, then deploy.
- Generalize the MKX-specific test fixtures and capture a second office's real listing.

## Phase 2.3: Dashboard and Weekly Warning Digest

Source: `agent-os/notes/2026-09-15-monitoring-and-digest.md`. Deliberately after the offices, so the
queries get built once against the shape they'll actually run on.

- **A CloudWatch dashboard** to look at on demand — not an alerting surface — managed in Terraform,
  with saved queries for warnings and recent run summaries.
- **A weekly digest email** of warnings and errors grouped by message and office, sent only when
  there was something to report. A digest beats a warning-count alarm, because an alarm only emails
  when its state *changes*, so warnings that keep happening go quiet and the email can't say which
  ones fired.
- Its own small Lambda from the same zip, its own weekly schedule, least-privilege access, and its
  own failure alarm — the bot's error alarm needs two consecutive 15-minute failures, which a
  weekly job would never trip.
- **Refresh the note's "Current state" section before shaping,** since Phases 1.2 through 2.2 change
  the log messages it's written against.

## Phase 3: Year in Review

Source: `agent-os/notes/2026-09-16-year-in-review-ideas.md`. Absorbs the old "story archive" item,
which the S3 archive plus a derived dataset already cover.

- **Celebrate the stories and the people who make them,** from a reader's point of view. Facts about
  the bot's machinery are a sidebar, never the headline, and individual forecasters are never
  identified.
- **A PDF infographic per office,** delivered over Telegram, styled after the look of Weather Story
  graphics but clearly labeled as unofficial and fan-made, with no NWS or NOAA logos or seal. MKX
  first, designed for N offices.
- **A derived, rebuildable dataset** built by a script from the archive, the ledger and the daily
  records, under its own prefix the posting Lambda can't reach. Queried locally — no always-on
  analytics infrastructure.
- **Inference runs after the fact, never in the posting Lambda.** A small model labels archived
  stories; a stronger one writes the narrative from the computed facts as its only input. A
  deterministic check fails the build if any number, date, office or title in the generated text
  isn't in the facts. Invented facts in something shared with an NWS office aren't acceptable.
  Inferred facts are labeled as inferred.
- **2026 is "Season One: September to December."** The bot went live on 2026-09-13 and NWS only
  lists *active* stories — there's no history to backfill. A full-year edition is 2027, which is
  exactly why Phase 1.2 starts recording now.
- Publishing is a new side effect: it needs its own place in the side-effect order and a guard
  against double posting.

## Phase 4: More Offices and Channel Promotion (long-term)

Opening the channels to a wider audience only makes sense alongside covering more of the country,
so these travel together. Sources: standards review, "Before about 50 offices" and `infra/alarms`.

- **Grow past the four offices,** regionally and then toward national coverage. The code should
  already handle it after Phase 2.2 — offices live in Terraform rather than an environment
  variable, each gets its own invocation, lease and time zone, and the schedules are staggered. The
  things that actually bite at scale aren't in the code.
- **Make onboarding cheap.** Every office needs a Telegram channel created, the bot made an admin,
  a tfvars entry and a check. That's fine for four and painful for forty. The checklist and check
  script from Phase 2.2 are the starting point; at some point it wants to be one command.
- **A daily health digest instead of per-office quiet alarms.** The global "gone quiet" alarm can't
  see one silent office, and a per-office version would be noisy, because some offices rarely
  publish at all. Build the digest from the daily run records, comparing each office against its
  *own* history. That's a report, not an alarm, which keeps fixed monthly cost O(1) in offices per
  `infra/budget` — per-office alarms and per-office custom metrics are exactly what that standard
  exists to prevent.
- **Then promote the channels to a wider audience.** Get them listed where people actually look:
  Telegram channel directories and catalogs, weather forums and enthusiast communities, the
  relevant state and regional subreddits, and — since the Year in Review may already be going to
  them — the NWS offices themselves. Each channel needs a name, description and photo written for
  strangers rather than for me, and a pinned post explaining what it is.
- **Stay clearly unofficial.** Public listings are exactly where this starts to look like an NWS
  product. No NWS or NOAA logos, seal or branding anywhere in the channel identity, and say in the
  description that it's an unofficial feed of public data, with a link to the source. The graphics
  are public domain; implying endorsement isn't.
- Open: one bot for all channels, or a bot per region — smaller blast radius if a token leaks, but
  more secrets to rotate.
