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

Done (spec `2026-09-20-1428-decide-act-and-record`; all four stages deployed, recording live since 2026-09-26). The refactor that makes the dry run
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
  - **A record per run per office:** when it ran, whether NWS answered, stories seen and the
    run's outcome counts. Outages and daily totals are derived from these, so they don't depend on
    the schedule's cadence.

  These are best effort. A failed write logs a warning and never blocks a post — they are
  deliberately not part of the safety chain.

  **This originally planned to write events under today's keys and let Phase 2.2 rewrite them,**
  accepting a second migration as the price of capturing history roughly two months sooner —
  because history not written down when it happens can't be recovered later at any price. Shaping
  reversed that: the migration is cheaper now than it will ever be again, so it happens here. See
  the next item.
- **Redesign the DynamoDB keys now, once** (moved here from Phase 2.2 during shaping). A new
  table with generic `PK`/`SK` names, sortable sort-key values (`STORY#`, `EVENT#`, `RUN#`) and a
  `schema_version` on every item. Two things settled it: the table holds 42 items today and never
  will again — it is growing by about 6 a day — so this migration's cost only rises; and the sort key's *values* are ours to
  choose even though its attribute is misleadingly named `image_id`, so sortable keys cost nothing
  extra now. No secondary indexes: the keys serve the bot, and analytics reads an S3 export.
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

Done (spec `2026-09-26-2319-staging-and-production`). A place to watch a real post, now
that the CLI can't send one. Source: standards review, "Environments".

- **Two named deployments from one `infra/`:** an environment name threaded through every resource,
  a separate state key, and a tfvars file each. **Settled while shaping:** `infra/envs/<env>.backend.hcl`
  and `<env>.tfvars` with a `TF_DATA_DIR` per environment, all selected by one required `ENV` in the
  Makefile. Not workspaces, and not Terragrunt, which pays off with many dependent stacks or an
  account per environment, not one module in one account.
- **Production keeps the resource names it has.** Threading an environment name through everything
  would rename the posted-stories table and the archive bucket, and a rename is a *replace* — the
  table has deletion protection on, the bucket is versioned and not empty, and
  `infra/data-retention` says to stop and ask rather than apply a replace. So either production
  stays unsuffixed and only staging takes a suffix, or the names move behind a variable defaulting
  to today's values. Either way, shaping ends with a `terraform plan` showing zero replacements.
  **Settled: production stays unsuffixed.**
- **Things a second environment would silently share** (found while shaping). The log metric
  filters' `WeatherStoryBot` namespace has no dimensions, so staging's posts would feed
  production's `quiet` and `repost-loop`. Staging gets its own namespace, and production's
  keeps its name and history. The budget covers the whole account, so it becomes
  production-only, as does the MVP `posted` rollback table. `infra/terraform.tfvars` is
  auto-loaded, so it moves to `envs/production.tfvars`. Otherwise anything missing from
  staging's file would fall back to production's public chat ids.
- **Staging** runs a subset of production's offices — at least one, and just MKX until Phase 2.2
  adds the others — into private test channels, with its schedule off by default and invoked by
  hand. **Production** runs the full set into the public channels.
- **A separate Telegram bot for staging,** with its own SSM parameter, so a staging bug or a wrong
  chat id physically cannot reach a public channel and a leaked staging token is worthless.
  **Settled while shaping: a separate bot.** Staging's role can read only its own parameter.
- **Staging stays near-free.** DynamoDB on-demand, S3, Lambda and the scheduler all cost nothing
  when idle; the only real fixed additions are alarms past the free tier. Confirm with `make cost`.
- **Two alarms can't be allowed to nag in staging.** `missed-runs` and `quiet` both treat
  missing data as breaching, and staging's schedule is off by default — so a staging stack would
  sit permanently in ALARM on both, emailing on every flap and training me to ignore the alerts
  that matter in production. **Settled (revised 2026-10-02):** staging has all five alarms on its
  own topic, and `make start` / `make pause` switch their actions on and off with the schedule,
  so a paused environment's alarms stay silent. Five per environment fills CloudWatch's 10 free.
- **New standard `infra/budget`,** which a second environment makes concrete: fixed monthly cost
  stays O(1) in offices, per-office visibility comes from queries rather than metrics, prefer
  pay-per-use with no idle cost, every spec carries a cost section, retention is a cost decision,
  and the budget alarm rises deliberately when a spec raises expected spend.
- **New rule:** staging is where real posts get watched. Production becomes pipeline-only when
  Phase 2.1 lands — until then it's still `make deploy`, and the rule is written down ahead of
  being enforceable.

## Phase 2.1: Deploy from GitHub Actions

In progress (spec `2026-10-05-1123-deploy-from-github-actions`). Replaces `make deploy` from my
laptop, before anything migrates the database or adds offices. Stage 1 (reproducible zip,
`terraform test`, Checkov) is deployed to both environments (Gate 1 passed 2026-10-08).

- **Two fixes first:** make the Lambda zip reproducible, or every plan shows a change that isn't
  one; and make `plan`/`deploy` build first or fail outright when the zip is missing, so neither
  the pipeline nor the break-glass path can quietly deploy stale code.
- **One workflow that reuses the Makefile.** Pull requests run lint, test, build and
  `terraform plan`. Merges to `main` run the same steps plus `terraform apply` in a protected
  environment with a required review. Staging applies before production.
- **Idea: static security checks on the Terraform,** with a scanner such as Trivy or Checkov,
  run as a Makefile target so pull requests and my laptop run the same checks. (Open: which tool,
  whether findings block the merge or just report at first, and how suppressions are recorded
  so an ignored check always carries its reason — settle it while shaping.)
  **Settled while shaping: Checkov, locked in its own uv project (`tools/checkov/`, since it pins `boto3` exactly), blocking from day one.** Every
  suppression is an inline `checkov:skip=ID:reason`, and `make scan` fails on a skip without a
  reason. Not Trivy: its GitHub Action tags were hijacked in March 2026 (CVE-2026-33634) to steal
  CI secrets, and a locked Python package runs identically on the laptop and in CI.
- **Idea: Terraform unit tests** with `terraform test`, run offline from a Makefile target so pull
  requests and my laptop run them the same way. Phase 2.0's hand checks in `terraform console` are
  the first cases: names and namespaces per environment, the token parameter's validation refusing
  another environment's path (including the slash-less form), the production-only `count`s, the
  `Environment` tag, and Task 5's tag conditions staying attached to exact ARNs. (Open: a
  `mock_provider` fills computed values with placeholders, including
  `aws_iam_policy_document.json`, so asserting on policy conditions may need the real provider
  with `command = plan` and no credentials, or assertions on the document's inputs. Settle it
  while shaping.) **Settled: a `mock_provider` and assertions on the documents' inputs.** The real
  provider would need credentials or skip flags in `providers.tf`, and the laptop's
  `override.tf` pins an MFA profile.
- **AWS access through GitHub OIDC** with a narrowly scoped IAM role managed in Terraform, so
  there are no long-lived keys. Values that aren't committed come from Actions variables.
  **CI never holds Telegram credentials.**
- **Tags and ABAC for the deploy roles** (from Phase 2.0, which enabled ABAC on the archive
  buckets). The roles need `s3:TagResource`, `s3:UntagResource` and `s3:ListTagsForResource`;
  without them the provider silently falls back to `PutBucketTagging`, and every bucket tag change
  fails. Scoping the deploy roles themselves by tag (`aws:ResourceTag` + `aws:RequestTag` +
  `aws:TagKeys`, a staging role that can't touch production) is the harder, more instructive half:
  many of the actions Terraform calls don't support tag conditions. Settle how far to go while
  shaping. **Settled: names, tags and a boundary.** Four roles in a separate bootstrap stack that
  only I apply (MFA), so the pipeline can't widen its own permissions: a read-only PR plan role, a
  `main`-only plan role, and an apply role per environment, each assumable only from its GitHub
  environment. Apply roles use exact production names or the `-staging` prefix, tag conditions
  wherever an action supports them (the gaps written down), and a per-environment permissions
  boundary on every role they create. An explicit Deny means even a bad plan can't delete the table
  or the archive. Not `ReadOnlyAccess` for plans: it can read the Telegram token.
- **Versioned zips in S3,** so Terraform never needs a local file, plan and apply can be separate
  jobs with an approval between them, and a rollback is a revert. **Changed while shaping:** keyed
  by the zip's content hash rather than the git SHA, so a docs-only merge plans as a no-op and a
  revert rebuilds byte-identical bytes. Production's saved plan travels through a private S3
  bucket, not a GitHub artifact, since the repo is public and the plan holds tfvars values.
  Dependabot can't get OIDC tokens, so the plan I approve is made on `main`, not in the PR.
- **Decided against a cloud Terraform runner** (HCP Terraform, Spacelift and friends). It can't
  build the zip, so GitHub Actions would still do the build, test and upload — the runner would
  only replace plan and apply. State stays in the S3 backend, which already handles locking at this
  size. If the approval and drift-detection story ever gets painful, the S3-zip seam means swapping
  a runner in is a config change, not a rewrite.
- **Production becomes pipeline-only from here.** Manual `make deploy` stays as the documented
  break-glass path — used deliberately, not routinely. **Settled:** `make plan`/`make deploy`
  refuse `ENV=production` without `BREAK_GLASS=1`. Staging applies on every merge to `main`, and
  production waits for my approval.

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
  Cross-office questions ("all offices on this day or year") are analytics and go through the S3
  export, not a GSI. The lease item also already exists. Revisit expiring
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
  records, under its own prefix the posting Lambda can't reach.
  - **"No always-on analytics infrastructure" is about query *engines*** — no Athena, no Glue
    crawlers, no OpenSearch sitting there costing money. DuckDB reads Parquet and NDJSON straight
    off S3 and replaces Athena entirely at this size, where Athena's 10 MB per-query minimum and a
    catalog would be setup cost for nothing. It does **not** mean the build step has to run on a
    laptop — see the next item.
  - **Always rebuild from scratch, never incrementally.** At megabytes a year a full rebuild takes
    seconds and deletes a whole class of bugs: no watermark, no "last exported" state, no partial
    recovery.
- **A scheduled export in the cloud, not a local run.** Analytics work should not depend on a
  laptop, for the same reason Phase 2.1 takes `make deploy` off one. Run it monthly, also
  invocable by hand.
  - **The real value is the feedback loop, not the dataset.** Running it while the season is live
    is how you find out you're capturing the wrong fields *while you can still change them*.
    Discover a gap in January 2027 and that data is gone — NWS lists only active stories. It also
    acts as a canary: an export that sees no new ledger events means the writes broke.
  - **Split the dump from the transform.** The dump is DynamoDB's native export to S3
    (`ExportTableToPointInTime`, using the PITR already on): no dump code, no `Scan` permission,
    no read capacity. It may not need a Lambda at all if an EventBridge Scheduler universal target
    can start it (verify when shaping). Its DynamoDB JSON (typed `{"S": ...}` attributes) is
    unwrapped downstream with the Parquet conversion and querying, where a heavy dependency is free.
    **DuckDB cannot go in the bot's zip:** it ships `manylinux_2_26/2_28` aarch64 wheels and
    `make build` targets `manylinux2014`, so adding it would fail the build.
  - **Lands after Phase 2.1.** Adding a second Lambda (if one is still needed) before pipeline deploys just means another
    thing deployed by hand — the same problem in a different coat. It needs its own failure alarm,
    since the bot's error alarm wants two consecutive 15-minute failures.
- **Inference runs after the fact, never in the posting Lambda.** A small model labels archived
  stories; a stronger one writes the narrative from the computed facts as its only input. A
  deterministic check fails the build if any number, date, office or title in the generated text
  isn't in the facts. Invented facts in something shared with an NWS office aren't acceptable.
  Inferred facts are labeled as inferred.
  - **Run it in the cloud, deliberately.** Beyond the Year in Review, this is the part of the
    project meant to teach managing AI models in the cloud, which is coming up at work. That
    justifies picking the *more instructive option among appropriate ones* — **Bedrock batch
    inference** over a loop of on-demand calls (roughly half the price, and the actual skill: S3
    manifests, job state, service roles), **model evaluation jobs** to choose the labeling model,
    and **Guardrails** on the narrative, which earns its place anyway since the PDF may reach an
    NWS office. It does **not** justify fine-tuning, SageMaker, Knowledge Bases, Agents or
    provisioned throughput — nothing in this data needs them, and they belong in a scratch project
    rather than grafted onto the weather bot.
  - `infra/budget`'s rule still holds: inference is batch and capped, each run prints a cost
    estimate and needs confirmation above a threshold, and labels are cached so nothing is paid
    for twice. Expect roughly 18M input tokens for a full year at four offices and ~1.3M for
    Season One in total, whether it runs once or in small pieces (see the next item).
- **Idea: label as things are archived, not all at once in December.** Spread the inference over
  the season instead of one big job at the end. A scheduled job picks up archived revisions that
  have no label for the current model and prompt version and labels them, so the same cache fills
  steadily. It stays after the fact: a separate job reads the archive, and the posting Lambda
  still never calls a model. Beyond the December bill, two reasons:
  - **A real cost line to watch** before the Year in Review depends on it. The estimate above is
    a guess until a few weeks of actual spend replace it.
  - **The feedback loop again.** A bad prompt or a mislabelled story shows up in October, while
    it can still be fixed, instead of in the week the PDF is due.

  This turns "a one-time job" into a small recurring pay-per-use line, capped and confirmed like
  the rest under `infra/budget`. (Open: nightly or weekly; **Bedrock batch jobs run
  asynchronously and have a minimum job size, so check at spec time whether a scheduled batch
  or on-demand calls from an S3-event consumer is the better fit.** Batch is the more
  instructive option and the cheaper one, if the minimum doesn't get in the way. Lands after
  Phase 2.1, so the new job deploys through the pipeline.)
- **Idea: the story within a story — what changed when a story was updated.** Every story folder
  holding more than one revision pair is a candidate. Deterministic first, inferred second:
  - **Computed facts per consecutive pair:** which raw JSON fields changed (`endTime` extended,
    description edited, image replaced), how big the text edit was, the gap between the revisions
    (from the ledger's `posted`/`updated` events), and how far the new image is from the old
    (the same perceptual-hash or embedding distance planned for design flair).
  - **Inferred, labeled as such:** a small model describes what differs between the two images and
    texts in plain words ("the Sunday graphic gave way to a Monday forecast table"). Any guess at
    *why* stays gentle and secondary. The narrative gets only the computed facts and the
    descriptions, and the grounding check applies.
  - **Tone guardrails hold:** appreciation, not diagnosis, and never anyone's name. A text
    fix reads as care ("caught in 4 minutes"), not as a mistake.
  - **First test case, found 2026-10-05:** MKX "Pleasant Fall Weather This Week" (start
    2026-10-04T19:00Z). The title, description and start time were identical, but NWS replaced
    the whole graphic overnight (Sunday's template with a patchy-frost bullet, then a Monday
    farm-field table), and the bot posted it as an update. Archived at
    `stories/MKX/2026/10/04/1900Z-pleasant-fall-weather-this-week-d6753582/`, revisions
    `8cbb9eb8f9557422` and `7a890d33d35abe3b`.
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
  publish at all. Build the digest from the run records, comparing each office against its
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
