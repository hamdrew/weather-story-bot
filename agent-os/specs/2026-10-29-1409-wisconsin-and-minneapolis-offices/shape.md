# Wisconsin and Minneapolis Offices — Shaping Notes

Shaped 2026-10-29. Roadmap Phase 2.2.

## Scope

The bot grows from MKX alone to five offices: MKX, GRB, ARX and DLH (all of Wisconsin between
them) and MPX (Twin Cities), each with its own Telegram channel, its own schedule and its own
Lambda invocation. This spec covers the whole roadmap entry:

- the five offices (the roadmap's four, plus DLH, added while shaping)
- one invocation per office
- a time zone per office
- recording a post atomically with its ledger event
- a `misconfigured` outcome
- alarm thresholds that scale with the office count
- an add-an-office checklist and check script
- generalized test fixtures

Out of scope: the Public Release side effort (added to the roadmap during shaping), the daily
health digest (Phase 4), and anything Year in Review reads the time zone for.

## Decisions

### Shaped with the user

- **The whole roadmap entry, in deploy-gated stages**, so the risky changes (the atomic write,
  the cutover to per-office schedules) each get a gate of their own.
- **Office config comes in the schedule's event payload:** `{office_id, chat_id, name,
  timezone}`. `OFFICES_JSON` and the 4 KB env limit go away, and there's no extra read or IAM
  grant. The SSM map and the env map that picks an office were both declined.
- **Time zone is a config field only.** Each office gets an IANA `timezone`, validated, and
  nothing reads it until Year in Review. Captions don't change, since they show no time today.
  Deferring it to Phase 3 and adding a local time to captions were both declined.
- **Staging runs MKX and MPX.** MPX is outside Wisconsin, and family can check its posts. The
  assumption is that MPX shares the existing private staging channel, so no new staging channel
  is made.
- **The check script reads the bot token from SSM with the MFA profile** (under `!` with
  `aws configure export-credentials`). Its Telegram calls are read-only (`getMe`, `getChat`,
  `getChatMember`). A token in `.env` was declined, since Phase 1.2 took exactly that off the
  laptop.
- **Cost informs the design, it doesn't veto it.** The user, on per-office schedules versus
  `infra/budget`: "Permit additional costs per office, but we must estimate and approve before
  deploying. I don't want design being too adversely affected by overly strict budget. With the
  addition of offices, this tool starts moving towards a public service." `infra/budget` was
  amended in Task 1 to match.
- **Public Release goes on the roadmap as a side effort**, parallel to Year in Review rather than
  a sequential phase: README links, trusted Telegram directories, weather forums, pinned messages
  describing each office, and how to interact with the bot. It takes over Phase 4's promotion
  items for the offices already running.

- **DLH (Duluth) joins as a fifth office.** The roadmap's four leave about eight far-northwest
  counties (Douglas, Bayfield, Ashland, Iron, Burnett, Washburn, Sawyer, Price) uncovered; the user
  wants all of Wisconsin. That list is from memory and gets verified in Task 8. DLH goes live at
  Gate 5 with the others. It is production only; staging stays MKX and MPX.

### Found while shaping

- **Production's apply role allows exactly one schedule name (`weather-story-bot`) and exactly
  five alarm names** (`infra/bootstrap/locals.tf`). Per-office schedules and a `misconfigured`
  alarm both need a bootstrap change first, applied by hand. The proposed production schedule
  pattern is `weather-story-bot-???`: IAM's `?` is a single character, so it can't match
  staging's `weather-story-bot-staging-*` names. Staging already uses a prefix pattern.
- **`NwsError` and `TelegramError` have no status attribute.** "Misconfigured" (an NWS 404 on the
  office, or a Telegram chat-level refusal) has to be told apart from a transient failure, so the
  clients need structured errors, still one public type per client (`backend/client-errors`).
- **The cutover deletes the old schedule and creates the per-office ones DISABLED**
  (`infra/environments`). That leaves the environment idle until `mise run start`, which in turn
  needs `scripts/set_run_state.py` to handle a list of schedules. An old-schedule invocation
  landing on the new code mid-apply raises `ConfigError` once, below the `errors` alarm's
  two-in-a-row.
- **`TransactWriteItems` has no IAM action of its own.** It is authorized per item action
  (`PutItem` here), so the atomic write needs no boundary change. Confirm this in Task 2.
- **Offices live in the `STAGING_TFVARS` / `PRODUCTION_TFVARS` GitHub secrets**, and the pipeline
  runs only on pull requests and pushes to `main`. An offices-only change therefore deploys
  nothing until a commit lands. The checklist has to say how a deploy gets triggered.
- **The README's "Adding an office" still says `mise run deploy production`**, which became
  pipeline-only in Phase 2.1.
- **`var.offices` is `sensitive`** (its chat ids would print in public plan logs). Terraform
  refuses it in `for_each`, and `length()` of it is sensitive too, so the schedules iterate over
  `nonsensitive(toset(keys(...)))`. Office ids are public.
- **Per-office invocation moved ahead of `misconfigured`** after the Task 1 review. Until the
  office arrives in the event, testing `misconfigured` needs bad config deployed to staging; once
  it does, a hand invocation is enough. The reorder also gets `cost.md`, which prices the new
  alarm, approved before that alarm ships.
- **`missed-runs` counts invocations per hour against `< 1`.** With N offices that misses a whole
  office going silent, so its threshold scales to fire once one office's worth of runs is missing,
  and stays `< 1` at N = 1.

## Context

- **Visuals:** None. New channel avatars are derived from the MKX SVG in `assets/telegram/`.
- **References:** see `references.md`.
- **Product alignment:** a personal tool that is starting to serve others. NWS data stays
  untrusted, and an office's failure is isolated to that office (`global/principles`). Fixed
  cost is a design input that the user approves, not a hard ceiling.

## Standards Applied

- global/principles: the office is the unit of isolation, local tools are read-only (the check
  script), decide purely then act
- global/launch-configs: the check script and the changed `set_run_state.py` get launch.json
  entries
- backend/env-config: office config moves from `OFFICES_JSON` to the event payload
- backend/run-outcomes: the new `misconfigured` count
- backend/side-effect-order: the posted/updated event joins the record's write
- backend/dynamodb-schema: the transaction, and history that is no longer entirely best effort
- backend/client-errors: structured "misconfigured" errors, one public type per client
- backend/structured-logging: `"Office misconfigured"`, and `"Run complete"` per office
- infra/alarms: the new alarm, and the scaled thresholds and runbooks
- infra/budget: the amendment, and `cost.md` at 1, 6 and 122 offices
- infra/environments: per-office schedules created DISABLED, and the staging/production office
  sets
- infra/iam: per-office schedule names and the bootstrap patterns
- infra/pipeline: bootstrap first, tfvars secrets, triggering a deploy
- testing/handler-tests, log-contracts, test-data, terraform-tests: how each change is tested
