# Phase 2.2: Wisconsin and Minneapolis Offices

Spec folder: `agent-os/specs/2026-10-29-1409-wisconsin-and-minneapolis-offices/`

## Context

The bot has posted MKX's Weather Stories since 2026-09-13. Phase 2.2 grows it to five offices:
MKX, GRB, ARX and DLH (all of Wisconsin between them) and MPX (Twin Cities). Each office posts to its own channel
and has its own schedule and Lambda invocation. Before that is safe, three things have to be true:

- recording a post is atomic with its ledger event, so state and history can't drift apart
- an office that fails on every run can't hold the `errors` alarm on and hide real failures
- the alarms still mean something when N offices run each cycle

The roadmap entry (`agent-os/product/roadmap.md`, Phase 2.2) is the source. Shaping settled the
rest.

### What shaping found beyond the roadmap

- **Production's apply role can't create per-office schedules.** `infra/bootstrap/locals.tf`
  names production's schedule exactly `weather-story-bot`. Its alarms are an exact list of five,
  so a `misconfigured` alarm would be denied too. Staging uses a `weather-story-bot-staging*`
  prefix and is unaffected. Per `infra/pipeline`, the bootstrap change goes first, applied by
  hand.
- **`infra/budget` forbade per-office schedules**, but EventBridge Scheduler bills per invocation,
  not per schedule. The user relaxed the rule: per-office cost is allowed, as long as it is
  estimated in `cost.md` and approved before deploying. "With the addition of offices, this tool
  starts moving towards a public service."
- **`NwsError` and `TelegramError` carry no status code.** Only the message has it, so the
  `misconfigured` outcome needs a structured way to tell a 404 or "chat not found" from a transient
  failure.
- **The old schedule is deleted and per-office schedules are created DISABLED**
  (`infra/environments`). The cutover deploy therefore leaves the environment idle until
  `mise run start`, and `scripts/set_run_state.py` has to handle a list of schedules first.
- **`var.offices` is `sensitive`,** because its chat ids would print in public plan logs.
  Terraform refuses sensitive values in `for_each`, and anything derived from them is sensitive
  too (`length(var.offices)`, an output of its keys). Office ids are public; only the chat ids
  need hiding.
- **Offices live in the `*_TFVARS` GitHub secrets** (the laptop's `mise run deploy staging` reads
  the local `infra/envs/staging.tfvars` instead). The pipeline runs only on pull requests and
  pushes to `main`, so an offices-only change deploys nothing. The add-an-office checklist has to
  cover that.
- **The README's "Adding an office" is stale.** It tells you to `mise run deploy production`,
  which is now pipeline-only.

## Decisions (from shaping)

- **Scope:** the whole roadmap entry, in deploy-gated stages.
- **Office config comes in the schedule's event payload:** `{office_id, chat_id, name,
  timezone}`. `OFFICES_JSON` goes away. The handler validates the event the way `Settings`
  validates env vars, and a bad event raises `ConfigError`.
- **Time zone:** an IANA `timezone` field on each office, validated (`zoneinfo` in Python, a
  shape check in Terraform). Nothing uses it until Year in Review. Captions don't change.
- **Staging runs MKX and MPX,** both posting into the existing private staging channel (the
  assumption is that MPX reuses that channel). Production runs all five, each in its own public
  channel.
- **DLH joins the roadmap's four** (added while shaping), so the offices cover all of Wisconsin.
  It covers the far-northwest counties none of the others reach.
- **The check script reads the bot token from SSM** with the MFA profile, under `!` with
  `aws configure export-credentials`. It makes only read-only Telegram calls (`getMe`, `getChat`,
  `getChatMember`) and never posts.
- **`infra/budget` is amended:** per-office cost is allowed when `cost.md` estimates it and the
  user approves it before deploying. Shared alarms on aggregates stay the default; per-office
  *visibility* still comes from queries.
- **Out of scope, but added to the roadmap:** a "Public release" side effort that runs in
  parallel with Year in Review, not as a sequential phase. It covers channel links in the README,
  listings in Telegram directories and weather forums, pinned "about this office" messages and
  interacting with the bot.
- **Per-office invocation comes before `misconfigured`** (reordered after review). Once the
  office arrives in the event, a hand invocation with a bogus office or chat id tests
  `misconfigured` without deploying bad config. And `cost.md`, which prices the new alarm, is
  approved before that alarm ships.

## Working agreement

Stop after each numbered task. Each task follows TDD for behaviour changes and ends with
`mise run lint ::: test` (plus `tftest` and `scan` when it touches infra) and a code review. Then
stage the changes and ask before committing. Gates are the user's to run: `deploy`, `start`,
`pause` and `bootstrap-deploy` all need MFA. Verify each gate against real AWS with the `readonly`
profile, and report times in America/Chicago.

---

## Task 1: Save spec documentation

Create the spec folder with `plan.md` (this plan), `shape.md`, `standards.md` (the full text of the
standards below), `references.md` and no `visuals/` (none were provided). Also:
- `roadmap.md`: add the **Public release** side effort, marked parallel to Phase 3, and mark
  Phase 2.2 in progress
- `infra/budget` and `global/principles`: the amendment above (estimate + approval before deploy)

## Stage 1: Atomic post record

### Task 2: Record the post and its ledger event in one transaction
- `state.PostedStore.record_posted` writes the current-story `Put` and the `posted`/`updated`
  event `Put` (`attribute_not_exists(PK)`) in one `TransactWriteItems`. Move the event item
  builder out of `history.py` so both share it, and stop `handler._apply_post_or_update` writing
  that event separately
- Pass a `ClientRequestToken` derived from office, story key and message id. Without it, a
  botocore retry of a transaction that succeeded (but whose response was lost) fails on the
  event's `attribute_not_exists`. The run would then count `failed` and orphan the old message
- If the transaction fails (including a cancelled event-key collision), the record fails and
  counts as `failed`. The next run reposts, and the old message isn't deleted, as today.
  Deleted/delete-failed events, rejections, `last_seen` and run records stay best effort
- IAM: transactions are authorized per item action (`PutItem`), so no new action is needed.
  Confirm this in the AWS docs during the task, and leave the boundary alone if it holds
- Standards: rewrite the Phase 2.2 paragraph in `backend/side-effect-order` as current behaviour;
  update `backend/dynamodb-schema` and the `history.py` and `state.py` docstrings
- Tests: handler tests over moto prove that a failed transaction writes neither item and that the
  next run reposts. Keep the existing step-failure tests

### Gate 1: one transaction per post
Deploy staging (`mise run deploy staging`). The gate passes on the first real post after the
deploy, in staging or production: its `STORY#` and `EVENT#` items both exist and share the
message id. A hand invocation usually posts nothing, so either wait for NWS to publish, or delete
one staging `STORY#` item by hand to force a repost (a staging data change, your call). Gate 3's
first MPX run checks it again at scale. Merge, let the pipeline deploy production, and watch
24h: `errors`, `repost-loop`, `"Failed to process story"` lines and the run records' `failed`
counts. (The posted event no longer goes through `history.py`, so `"History write failed"`
can't report it.) Rollback: revert the commit. The data stays compatible, since the items are the
same shape.

## Stage 2: Bootstrap for per-office names

### Task 3: Allow per-office schedules and the `misconfigured` alarm
- `infra/bootstrap/locals.tf`: production's schedule names become `weather-story-bot-???`.
  IAM's `?` matches one character, so the pattern matches `weather-story-bot-mkx` but never
  `weather-story-bot-staging-mkx`. Keep `weather-story-bot` itself until Task 9 (Gate 3's rollback
  recreates it). Add `misconfigured` to the alarm list
- Lambda and Scheduler boundaries: no change (the function name stays the same)
- `infra/bootstrap/tests/*`: assert that the new patterns match the right names and that
  production's patterns never match staging's names. `mise run tftest ::: scan`

### Gate 2: apply the bootstrap
You run `mise run bootstrap-plan`, review it, then `mise run bootstrap-deploy`. Confirm with
`readonly` that the production apply policy lists the new ARNs. Rollback: revert, then
bootstrap-deploy again. Nothing in the main stack uses the new names yet.

## Stage 3: One invocation per office

### Task 4: Generalize the office test fixtures
- `tests/conftest.py`: `office_payload(office_id)` / `office_stories(...)` over
  `tests/fixtures/<office>_weatherstories.json`, keeping `mkx_payload` as a thin alias or
  replacing its uses. Capture MPX's real listing once with a live `curl` (the only network use),
  and date it in the fixture's comment
- Update `testing/test-data`

### Task 5: The office comes from the event
- `config.py`: `Settings` loses `offices`. A new `OfficeConfig.from_event(event)` validates
  `office_id` (the regex), `chat_id`, `name` and `timezone` (`zoneinfo.ZoneInfo`), and raises
  `ConfigError` with a message that names the field
- `handler.run` takes one `OfficeConfig`. `"Run complete"` keeps its fixed keys, with `office`
  and `aws_request_id` from the record factory. The lease, run record and per-office isolation
  are unchanged
- An empty or invalid event (e.g. the old schedule firing once mid-cutover) raises `ConfigError`.
  That is one Lambda error, below the `errors` alarm's 2-in-a-row
- Standards: `backend/env-config` (the event payload replaces `OFFICES_JSON`; the office regex in
  both places), `backend/cli` (its `--office` line names `OFFICES_JSON` parsing),
  `testing/handler-tests`; README and `.vscode/launch.json` if they mention the env var

### Task 6: Per-office schedules, scaled alarms, cost
- `infra/variables.tf`: each `offices` entry gains `timezone` (shape validation).
  `schedule_expression` becomes `schedule_interval_minutes` (default 15, validated to divide 60),
  which keeps the "longer than `LEASE_DURATION`" check
- `infra/scheduler.tf`: `for_each = nonsensitive(toset(keys(var.offices)))`, with a comment that
  office ids are public and only chat ids are sensitive. Look up each office's entry inside the
  resource. Each schedule is named `${local.name}-${lower(office)}` and runs
  `cron(<offset>/<interval> * * * ? *)`, with offset = sorted index `% interval`. The target
  `input` is the office's JSON. Update the `CKV_AWS_297` skip reason (the input holds chat ids,
  which are not secrets). Remove `OFFICES_JSON` from `lambda.tf`
- `infra/outputs.tf`: `schedule_names` (a list, built from the nonsensitive keys).
  `scripts/set_run_state.py` toggles every schedule in it, plus its tests and launch.json
- `infra/monitoring.tf`, with N = `nonsensitive(length(var.offices))`:
  - `missed-runs` fires on LessThan a threshold of `N × 60/interval − 60/interval + 1`. That is 1
    at N = 1, as today. It counts invocations, so it fires once about one office's worth of runs
    is missing, from any mix of offices; the runbook says so
  - `repost_alarm_max_posts` becomes `repost_alarm_max_posts_per_office`, and the threshold is that
    × N. Remove the old name from both tfvars secrets: an unknown variable in a var file is only a
    warning, so a leftover value would be silently ignored
  - `errors` and `quiet` get descriptions saying that a single global alarm can't see one silent
    office
  - The runbooks name the per-office schedules
- New and renamed variables go in `infra/envs/*.tfvars.example` (`infra/alarms`)
- `scripts/infracost_usage.py` and `infracost.yml`: per-office schedules, plus the
  `misconfigured` alarm that Task 7 adds (it takes each environment to 6 alarms, 12 in total,
  past CloudWatch's 10 free ones). Run `mise run cost` and write `cost.md` at 1, 6 and 122 offices,
  list price first (the user approves it at Gate 3)
- `infra/tests/*`: schedules per office, input shape, stagger (including more offices than
  interval minutes), threshold math, and `expect_failures` for each new validation
- Standards: `infra/alarms`, `infra/environments`, `infra/budget`, `infra/iam` (schedule names)

### Gate 3: per-office cutover
- **Before deploying:** approve `cost.md`. Add `timezone` everywhere and drop
  `repost_alarm_max_posts` in three places:
  - the local `infra/envs/staging.tfvars`, adding MPX in the staging channel (`mise run deploy
    staging` reads this file)
  - `STAGING_TFVARS`, with the same change
  - `PRODUCTION_TFVARS`, which keeps MKX only
- **Staging:** run `mise run deploy staging`, then `mise run start staging`, and invoke both
  offices by hand. Confirm two `RUN#` items with the right offices, no cross-office writes, and
  staggered fire times. MPX's first run posts all its active stories, which re-checks Gate 1's
  `STORY#`/`EVENT#` pairs.
- **Production:** merge, let the pipeline deploy production, then run `mise run start production`
  right away (until then the new schedule sits DISABLED and `missed-runs` fires). Watch 24h.
- **Rollback:** revert and redeploy, then `mise run start`. The old schedule comes back DISABLED.
  Production's revert goes through the pipeline and its approval, so it has a gap with no
  schedule. The reverted code tolerates the updated secrets: `map(object({chat_id, name}))` drops
  the extra `timezone`, and an undeclared variable in a var file is only a warning.

## Stage 4: The `misconfigured` outcome

### Task 7: Offices that fail every run stop holding the errors alarm
- First confirm what NWS returns for an office that doesn't exist (Context7
  `/websites/weather_gov` and one live `curl`). If it's a 200 with an empty list rather than a
  404, the NWS half of this task changes
- Clients get structured errors: an `NwsError` subclass or attribute for "this office doesn't
  exist", and a `TelegramError` subclass for chat-level refusals (400 "chat not found", 403 "bot
  was kicked" / "not a member" / "not enough rights"), modelled on `_PhotoRejectedError`. Each
  client still has one public error type (`backend/client-errors`)
- Add a new fixed count, `misconfigured`: ERROR `"Office misconfigured"` with `reason`. It doesn't
  raise `ProcessingError`, and the office stops for that run. It lands in the `RUN#` item through
  the counts. `counts()` in the tests is updated
- `infra/monitoring.tf`: a metric filter plus one shared `misconfigured` alarm. Its description is
  a runbook (decommissioned office, bot removed from the channel, missing rights), it fires on any
  data point in 1h with `notBreaching`, and it goes in `local.alarm_names` (the bootstrap list
  already has it). This is a log contract (`testing/log-contracts`)
- Standards: `backend/run-outcomes` (the new row and how to choose it), `infra/alarms`

### Gate 4: misconfigured fires, errors doesn't
Deploy staging, then invoke it by hand twice:
- with an event for a nonexistent office (e.g. `ZZZ`), for the NWS path
- with an office staging doesn't run (e.g. GRB, while it has active stories) and a bogus
  `chat_id`, for the Telegram path. Every story is new to that office, so it tries to post

Each run counts `misconfigured`, with no Lambda error, and the alarm fires and then resolves.
Then deploy production through the pipeline. Rollback: revert.

## Stage 5: The new offices

### Task 8: Add-an-office check script and checklist
- `scripts/check_office.py`, read-only, with no `--apply` because it never writes. It lists the
  office's stories (catching the not-found case), then calls Telegram `getMe`, `getChat`, and
  `getChatMember` for the bot, which confirms it is an admin with post and delete rights. The token
  comes from the env's SSM parameter, through the injected boto3 client. Read-only methods are
  added to `TelegramClient`, with offline tests and a launch.json entry
- The README's "Adding an office" becomes the checklist:
  1. Create the channel and avatar, from the MKX SVG in `assets/telegram/`
  2. Add the bot as an admin with post and delete rights
  3. Run the check script
  4. Add a tfvars entry with `timezone`, and refresh the `*_TFVARS` secret
  5. Trigger a deploy
  6. Run `mise run start`

  Decide here how step 5 triggers a deploy when only the secret changed (a commit, such as the
  office's avatar, or a `workflow_dispatch` on `main`). Gate 5 is exactly that case.
- Verify the Wisconsin county coverage of MKX, GRB, ARX, DLH (far northwest) and MPX (some
  west-central counties). Confirm every Wisconsin county falls to one of the five, and record the
  result in the README

### Gate 5: five offices live
1. Create the GRB, ARX, DLH and MPX channels, add the bot to each, and run the check script for
   each office.
2. Add all five offices to `PRODUCTION_TFVARS`, then merge Task 8's PR, which is the deploy
   trigger, since production is pipeline-only.
3. Start the new schedules and watch the first runs: each new office posts all its active stories
   once.

### Task 9: Phase 2.2 done
- Mark the roadmap entry done, fold remaining notes into the standards, update tech-stack's office
  line, and refresh the README's cost paragraph from `cost.md`
- Remove the exact `weather-story-bot` schedule name from `infra/bootstrap/locals.tf`. Once
  Gate 5's watch has passed, no rollback needs it. This takes one more `bootstrap-plan` /
  `bootstrap-deploy`, which you run

## Verification (end to end)
- `mise run lint ::: test ::: tftest ::: scan` is green after every task
- Each gate is checked against real AWS with `--profile readonly`. Check `RUN#` and `EVENT#`
  items per office, schedules (names, state, input, cron), alarm states and actions, and Logs
  Insights `stats count() by office` over `"Run complete"`
- `uv run weather-story-bot --dry-run --office MPX` prints decisions for a non-MKX office
