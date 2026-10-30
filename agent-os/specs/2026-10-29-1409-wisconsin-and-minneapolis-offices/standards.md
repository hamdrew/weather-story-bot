# Standards for Wisconsin and Minneapolis Offices

The following standards apply to this work, copied as they stood when shaping ended on 2026-10-29
(`infra/budget` and `global/principles` include the amendment Task 1 made). Each standard's own
headings are demoted one level. Tasks that change a standard edit the file under
`agent-os/standards/`, not this copy.

---

## global/principles

The four rules the other standards are specific cases of. When a standard and a principle seem to
disagree, the principle is what the standard was trying to say.

### Local tools are read-only

Anything that writes — Telegram, AWS, anything outside stdout and stderr — runs in a deployed
environment or a `scripts/` tool whose name says so. The dev CLI previews and never acts.

- A preview that could act is a preview you stop trusting, and a flag away from posting to a live
  channel from a laptop
- A `scripts/` tool that writes is dry-run by default and needs `--apply` (`backend/dynamodb-schema`)
- To watch real behaviour, use staging (`infra/environments`), not a local flag
- Adding a write mode to a local tool needs a spec that changes `backend/cli` first

### Decide purely, then act

Choosing what to do is a pure function of its inputs: the listing, the images, `now`, and the
stored records. Side effects happen afterwards, in a thin apply step with a fixed order
(`backend/side-effect-order`).

- The planner returns data. It does no I/O, reads no clock of its own, and **does not log** —
  log lines are a side effect, and some of them are alarm contracts (`testing/log-contracts`)
- The Lambda and the CLI call the same planner, so a preview cannot drift from what runs
- Decision edge cases get table-driven tests with no moto and no respx
- A decision that needs a new input takes it as an argument, never by reaching for it

### Sources of truth vs derived data

The S3 archive (raw NWS) and the ledger (what we did) are sources of truth: protected, kept
forever, never rewritten. Everything else — analytics tables, indexes, reports, labels — is
derived: rebuildable, unprotected, deletable.

- Never add derived fields to a source of truth. Derived fields belong in the derived dataset
- Analytics reads the derived dataset, never the live archive or the state table
- Losing derived data costs a rebuild. Losing a source of truth costs the data forever, and NWS
  lists only *active* stories, so nothing can be re-fetched
- Retention is a deliberate decision per dataset, not a default

### The office is the unit of isolation

Concurrency, failure, configuration, and onboarding are all per office.

- One office's failure never affects another's posts
- `story_key` alone is not a global identity; `(office_id, story_key)` is
- Checks that compare stories to each other stay inside one office's listing — neighbouring
  offices can legitimately share a regional graphic (`backend/untrusted-nws-data`)
- Per-office *visibility* comes from queries and reports by default. A per-office alarm or custom
  metric, whose fixed cost grows with the office count, needs a reason a query can't meet and an
  approved estimate (`infra/budget`)

---

## global/launch-configs

Every executable Python script has an entry in `.vscode/launch.json`, so it can be stepped through
in a real debugger (`F5`) as easily as it runs from the shell.

"Executable" means a `scripts/*.py` file with an `if __name__ == "__main__":` block, plus the
package entry point (`weather_story_bot`, the dev CLI). Add the entry in the same change that adds
the script.

- Name it `<Script Name>: <What It Does>`, as in `Migrate Table Keys: Dry Run`
- Use `"type": "debugpy"`, `"request": "launch"`, `"cwd": "${workspaceFolder}"` and
  `"console": "integratedTerminal"`. Use `"program"` for a script and `"module"` for the package
- **The entry is safe to launch without thinking.** It never passes `--apply`, and a tool that
  would otherwise touch AWS sets `"env": {"AWS_PROFILE": "readonly"}` so it can't write even if
  someone adds `--apply` later (`global/principles`). A tool that can only run with the MFA profile
  gets no entry; document why in its docstring
- Give it `args` that work on a clean checkout. When a script reads something a mise task produces
  (`build/package`), say so in a `//` comment on the entry
- Write output to a scratch path (`build/debug.zip`), never to a file another step consumes
  (`build/lambda.zip`). A debug session must not change what `mise run plan` hashes or `mise run deploy` applies
- A script with subcommands gets one entry per subcommand worth stepping through

---

## backend/env-config

The Lambda reads all its config from env vars through `Settings.from_env`, which raises `ConfigError` if anything is missing or invalid.

```python
@classmethod
def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings: ...
```

- Tests pass a dict instead of patching `os.environ`
- `require()` strips whitespace, and a blank value counts as missing
- Structured values are JSON (`OFFICES_JSON`), checked item by item with a message that names the problem
- Secrets: env holds the SSM parameter **name** (`TELEGRAM_TOKEN_PARAM`), never the value

### Adding a setting

In one change:

1. `Settings` field + `from_env` (`config.py`)
2. `environment.variables` in `infra/lambda.tf`
3. `infra/variables.tf` (with `validation` if constrained) + `infra/envs/*.tfvars.example`
4. A test in `tests/test_config.py`, plus the `ENV` dict in the `lambda_handler` end-to-end test

### Office ids

Validated as `^[A-Z]{3}$` in **both** `config.py` and `variables.tf`. Keep the two in sync.

- Terraform catches typos at plan time
- Python still checks, because office ids end up in NWS URLs and S3 paths (`../X` must fail), and the Lambda's env can be changed outside Terraform
- The local CLI's `--office` is only uppercased, not validated. It hits NWS only

---

## backend/run-outcomes

`handler.run` returns one set of counts per office. The keys are fixed: `posted`, `updated`, `skipped`, `rejected`, `failed`.

| Count | Meaning | Run result |
|---|---|---|
| `posted` / `updated` | new post / repost of a changed story | success |
| `skipped` | unchanged, or expired (no action at all); `1` for the office when another run holds its lease | success + INFO `"Office run already in progress"` |
| `rejected` | ambiguous NWS data we refuse (`backend/untrusted-nws-data`) | success + ERROR log + `nws-ambiguous` alarm |
| `failed` | exception taking the office lease, or on list, download, reading posted stories (fails the whole office) or process; any other exception after the listing fails the rest of the office (`"Failed to process office"`), which still records its run | `ProcessingError` -> Lambda Errors -> `errors` alarm |

- Choosing a count: if the next run may fix it (our side or a transient error), it's `failed`. Upstream data we refuse on purpose gets its own count, an ERROR log line and a metric-filter alarm, and the run still succeeds
- `lambda_handler` logs `"Run complete"` with the summary **before** raising `ProcessingError`, so runs with failed stories still leave a summary. Errors before `run()` (`ConfigError`, SSM or boto3 failures in `_build_services`) raise with no summary. Look for the Lambda traceback instead
- The office lease (`state.OfficeLease`): losing it to another run is `skipped`, not a failure. Scheduler's at-least-once delivery makes overlaps expected, and they must not trip the `errors` alarm. A DynamoDB error *taking* it is `failed`, never "proceed anyway": without the lease the run can't know it's alone. A failed *release* is a WARNING only; the lease expires before the next run
- A new count needs `counts()` in `tests/test_handler.py` updated, plus an alarm or dashboard decision

### Cold-start cache

`_services` (HTTP pool, boto3 clients, Telegram token from SSM) is built once per container.

- A token rotated in SSM isn't picked up until new containers start. After rotating, apply a real function config change through Terraform to force them. Until then, runs may fail with the old token
- Tests reset it with `monkeypatch.setattr(handler, "_services", None)`

---

## backend/side-effect-order

`handler._apply_post_or_update` runs its side effects (S3 writes, Telegram posts and deletes, DynamoDB writes) in a fixed order, behind a read-only gate that now sits upstream in `planner.decide` (`global/principles.md`: decide purely, then act). `run` reads `store.find_story` for every downloaded story before deciding; `decide` is what turns "fingerprint unchanged" into an `unchanged` `Decision` that `_apply_decisions` skips before any side effect runs. Each side effect below can still fail and leave the channel and archive safe for the next run.

0. `lease.take` (`state.OfficeLease`), before anything else for the office, released in a `finally` after step 5. If another run holds it, the office is `skipped` with no NWS call and no write; if DynamoDB errors, it's `failed` (`backend/run-outcomes`). This is what keeps two overlapping runs from both posting the same story
1. `store.find_story`, read by `run` before `decide`: if the fingerprint is unchanged, `decide` returns `unchanged` and nothing below runs
2. `archive.save`: if S3 fails, nothing is posted. Every image that reaches the channel is archived. A leftover pair from a failed send is harmless (same revision, same keys)
3. `telegram.send_photo`
4. `store.record_posted`, only after Telegram accepts. If this fails, the next run reposts, and the old message is **not** deleted
5. `telegram.delete_message` for the replaced message, last

- Never delete before the new post is recorded. A crash at any step leaves the old message, or both, never zero
- A failed delete (Telegram refuses after 48h) logs `"Telegram delete failed, old message kept"` as a WARNING. It doesn't count as failed, doesn't raise and doesn't repost
- A new side effect (another channel, a notification and so on) needs its place in this order and a test that fails at that step (`testing/handler-tests`)

### History writes, outside the chain

`history.StoryHistory`'s three writes are best effort (`backend/dynamodb-schema`): each failure logs WARNING `"History write failed"`, never blocks a post and never counts as `failed`. They sit around the chain, never between its steps, so a history outage can't change what reaches the channel:

- **Rejected events**: after the `"Ambiguous stories from NWS"` line, before any post
- **`last_seen_at`**: on each `unchanged` decision, in place of steps 2–5. Never on a post or update: `record_posted` has just replaced the item
- **Posted/updated event, then the deleted/delete-failed event**: after the old message's delete, timed at the send and at the delete. The delete event is about the replaced revision only (`history.record_deletion`)
- **Run record**: after the lease is released, only for a run that held it. A lost or failed lease leaves no `RUN#` item

Phase 2.2 deliberately reverses this for the ledger: the posted/updated event becomes part of `record_posted`'s write, atomic with the record, so a recorded post always has its event. Until then an event can be missing; the record and the archive never are.

---

## backend/dynamodb-schema

### Keys (`aws_dynamodb_table.state`)

One table, generic key names, every item under its office's partition:

| Item | `PK` | `SK` |
|---|---|---|
| Current story | `OFFICE#<id>` | `STORY#<start_utc_iso>#<story_key>` |
| Ledger event | `OFFICE#<id>` | `EVENT#<start_utc_iso>#<story_key>#<at_utc_iso>` |
| Run record | `OFFICE#<id>` | `RUN#<at_utc_iso>` |
| Office lease | `OFFICE#<id>` | `LEASE` |

- Key attributes are named `PK` and `SK`, never after what they hold, so new item types need no schema change
- Sort-key values sort usefully: UTC ISO timestamps, so a `begins_with`/`BETWEEN` Query answers date ranges within one office
- Every item carries `schema_version` (a number). Bump it when an item type's attributes change shape
- Build keys and `schema_version` with `state.py`'s `office_pk`, `story_sk` and `SCHEMA_VERSION`, never by hand, so migration scripts write exactly what the Lambda reads
- Current-story items also carry `office_id` and `story_key` as ordinary attributes, so an S3 export reads them without parsing keys
- Mark each item type with its uppercase sort-key prefix. Any read that isn't an exact key (a Query on `PK`) filters on the prefix
- Global identity is `(office_id, story_key)` (`backend/story-identity`). `story_key` alone never appears as a key without its office
- Keys serve the bot's own access patterns only. Analytics never queries the table: it reads a native export to S3 (`ExportTableToPointInTime`, which uses the PITR already on) and runs downstream (`global/principles`)
- No secondary indexes today. Never add an LSI: it can only be created with the table and caps each partition at 10 GB for good. A GSI can be added any time and backfills every item that already has its key attributes, so no attribute is written "for a future index"
- Timestamp attributes carry item-specific names (`event_at` on events, `posted_at`, `last_seen_at`, `expires_at`), never a generic `at`, so an index on one of them stays sparse
- **No TTL.** Records are permanent and the ledger is a source of truth (`global/principles`). The lease expires through a conditional write on an ordinary `expires_at` attribute, not TTL
- Use the low-level client with typed attributes (`{"S": ...}`) and `ConsistentRead=True` on dedupe lookups
- Timestamps written by new code use `state.utc_timestamp` (fixed-width UTC, microseconds), so they compare and sort as strings. `STORY#` start times keep their existing format; they're in live keys

### History items (`history.py`)

Best-effort and append-only, outside the safety chain: a failed write logs WARNING `"History write failed"` and never blocks a post. `state.py` is the safety chain; `history.py` is not.

- **`EVENT#`**: one immutable item per action (`posted`, `updated`, `rejected`, `deleted`, `delete_failed`), written with `attribute_not_exists(PK)` so a key collision fails rather than overwrites. The event time is part of the key, so read the clock per event. It holds only the revision it's about: no `previous_*` fields or `changes`. What an update changed is derived from consecutive events at analysis time. The archive prefix isn't stored either; `archive_prefix(story, fingerprint)` rebuilds it
  - `deleted` / `delete_failed` (`record_deletion`) describe the **replaced** revision only: its `image_id`, `fingerprint` and `telegram_message_id` from its record, plus the shared identity (`title`, `start_time`, `story_key`). No `end_time` or `update_time`: the record doesn't keep the old revision's, and the listing's belong to the new one. Join to the earlier `posted`/`updated` event with that message id for the rest
  - `rejected` carries `reasons` and the rejected revision's `fingerprint`, and no message id. Stories rejected as `duplicate_title_and_start` share a `story_key`, so their events differ only by `event_at`
- **`last_seen_at`** on the `STORY#` item: rewritten only when the value read with the record is an hour stale, decided before any request, since a failed conditional write still bills. The condition `attribute_exists(PK)` keeps it from creating an item. `record_posted` replaces the item and clears it, so each repost starts unseen. A story pulled early shows `last_seen_at` well before `end_time`
- **`RUN#`**: one immutable item per office per run, written like events: `run_at`, `nws_failed`, `stories_seen`, the run's outcome counts (`backend/run-outcomes`) and `aws_request_id`. Raw runs, never daily totals: outages, days and per-office baselines are derived at analysis time, so the record doesn't depend on the schedule's cadence. A duplicate run is its own item. Written only by a run that held the lease, so no item means no run: a lost or failed lease, or an invocation that never happened

### Office lease (`state.OfficeLease`)

In the safety chain (step 0 of `backend/side-effect-order`), so it lives in `state.py`. One `LEASE` item per office: `office_id`, `holder` (a random token per take), `taken_at`, `expires_at`.

- **Take**: conditional `PutItem` on `attribute_not_exists(PK) OR expires_at < :now`. A condition failure means another run holds it; any other error raises
- **Release**: `DeleteItem` in a `finally`, conditional on `holder`, so a run whose lease expired can't delete the next run's
- `expires_at` is `taken_at + LEASE_DURATION` (360s: the 300s Lambda timeout plus a margin), shorter than the 900s schedule, so a crashed run's lease is gone before the next run. Raising the Lambda timeout means raising `LEASE_DURATION` with it

The MVP table `aws_dynamodb_table.posted` (`office_id` / `image_id = story#<story_key>`) was
copied here by `scripts/migrate_table_keys.py` in Phase 1.2's Stage 3. The Lambda no longer reads
or writes it. It stays untouched as the rollback and is removed deliberately after the new keys
have soaked.

### Migrations

Follow `scripts/migrate_story_keys.py`:

- Module docstring: date, before and after, steps, runbook (pause the schedule, dry run, `--apply`, deploy)
- Dry run by default, writes only with `--apply`, and every step idempotent
- Old data is deleted only after the new Lambda works. PITR and S3 versioning cover 35 days
  - Within one table or bucket: a separate flag (`--delete-old`), as `migrate_story_keys.py` does
  - To a new table (`scripts/migrate_table_keys.py`): no delete step. Drop the old table whole through Terraform in two applies, `deletion_protection_enabled = false` and then the resource. A table deleted with PITR on keeps a free 35-day SYSTEM backup
- Raise a `MigrationError` before any write if the data doesn't look as expected
- Test against moto with seeded old-shape data. Keep the script and tests in `scripts/` after running
- Run with admin creds, not the Lambda role (`infra/iam`)

---

## backend/client-errors

Each client raises exactly one public error type. It wraps transport errors, bad HTTP statuses and malformed payloads.

```python
class NwsError(Exception):
    """The NWS API could not be reached or returned an unusable response."""


try:
    stories = [Story.from_api(i) for i in response.json()["stories"]]
except (ValueError, KeyError, TypeError) as exc:
    raise NwsError(f"Unexpected response for {office_id}: {exc}") from exc
```

- Callers catch only client error types: `except (NwsError, TelegramError)`
- Why: callers don't need httpx internals, and the client controls the message (see secrets-in-errors)
- Internal control flow uses private subclasses (`_PhotoRejectedError`)
- Only exception: `handler.run` catches `Exception` per office and per story so one failure can't block the rest. It must `logger.exception` and count `failed`, which makes `lambda_handler` raise `ProcessingError`

---

## backend/structured-logging

Log a fixed message and put the data in `extra`. `JsonFormatter` turns each `extra` key into a JSON field, so metric filters and Logs Insights can match `$.message` exactly and filter on fields.

```python
logger.warning(
    "Telegram delete failed, old message kept",
    extra={"telegram_message_id": replaced.telegram_message_id},
)
```

- Never use f-strings or `%` args in the message. Every line becomes unique and the data is buried in text
- `extra` keys can't be reserved `LogRecord` attributes (`filename`, `name`, `message`, `module` and so on). They raise `KeyError`, so use a prefixed name like `image_filename`
- Use `image_id` as a join field whenever you know it; `office` is supplied for you (below)
- Put errors in as `str(exc)` or `repr(exc)`, never a URL containing the token (`backend/secrets-in-errors`)
- Loggers: `logging.getLogger(__name__)` in modules. `handler` uses `"weather_story_bot"`, the parent, and tests capture that logger
- `configure_logging` keeps `httpx` and `httpcore` at WARNING because they log request URLs

### `office` and `aws_request_id`

Every log record created during a run gets `office` and `aws_request_id` from `handler._record_with_request_context`, a `logging` record factory installed once, at import time — not passed by each caller. That includes child loggers (`weather_story_bot.telegram`, `.nws`, `.archive`, `.history`) and third-party ones (botocore, httpx), so every line of an office's run can be joined on either field.

- **Never pass `office` or `aws_request_id` in `extra`.** Once the factory has set them, `Logger.makeRecord` refuses to overwrite an existing record attribute and raises `KeyError`, which turns a log call into a crash. (`history._log_failure` used to pass `office` by hand; it can't any more)
- Why a record factory, not a `logging.Filter`: a logger's filters only run for records created on that logger, never for records propagating up from its children, so a filter on `weather_story_bot` missed every line from `nws.py`, `telegram.py`, `archive.py` and `history.py`. A filter on the root *handler* would see them all, but only after `configure_logging()`, so tests calling `run()` directly would lose the fields
- The factory wraps whichever factory is in place when `handler` is imported instead of replacing it. Anything that calls `logging.setLogRecordFactory` later, without chaining, would drop both fields; `test_handler` would catch that
- Backed by two module-level `contextvars.ContextVar`s (`_aws_request_id`, `_office`), not plain mutable attributes. `ContextVar.set` returns a token; `_invocation_context` and `_office_context` `.reset(token)` it in a `finally`, so cleanup is exact even on an exception — a plain attribute that someone forgets to clear back to `None` leaks into whatever logs next, which is exactly how this leaked once during review before the `ContextVar` swap
- `_invocation_context`, entered once per invocation in `lambda_handler` from `context.aws_request_id`, sets `aws_request_id` for everything inside it — including a later, unrelated `run()` call must **not** still see it once that `with` block has exited
- `_office_context` sets `office` once per office, wrapped around each office's iteration of `run`'s loop, reset after — so `"Run complete"`, which spans every office, carries no office at all
- Code outside a run (unit tests calling `StoryHistory` or `TelegramClient` directly, `scripts/`) gets neither field; assert them in `tests/test_handler.py`, where the context exists
- A new caller-supplied field always still goes through `extra` as usual; only `office`/`aws_request_id` are factory-supplied
- Treat `aws_request_id` as unique but not random. Scheduled invocations get structured IDs: hex digits 3–10 are the scheduled time (seconds, offset by `0x60000000`), and the prefix and tail stay fixed until the schedule is re-activated, e.g. `e16ab440-4453-4ddb-b52a-f9af386f1184`. Code deploys don't change them. Only a direct `aws lambda invoke` gets a random UUID. That structure is observed behaviour (936 invocations, 2026-09-13 to 09-23, no duplicates), not documented. Fine as a correlation key; never sample or shard on its leading characters

| Level | Use when |
|---|---|
| `exception` | counted as `failed`, so the Lambda errors |
| `error` | needs attention, but the run succeeds (alarmed by a metric filter) |
| `warning` | tolerated or retried, no action needed |
| `info` | normal outcomes and contract lines (`testing/log-contracts`) |

---

## infra/alarms

The alert email is the only context you get when an alarm fires. It must say what went wrong and where to look, without opening the repo.

Every `aws_cloudwatch_metric_alarm` has:

- `alarm_description` covering what happened (in plain words), the likely causes, what to check (log message names, schedule and field names) and `${local.logs_console_url}`
- `alarm_actions` and `ok_actions` set to `aws_sns_topic.alerts.arn`. The OK email tells you it resolved
- A `treat_missing_data` setting with a comment on what missing data means. For log-filter metrics, a quiet period has no data points, not zeros
- Tunable thresholds and windows as `variables.tf` entries with defaults and validation, listed in `infra/envs/production.tfvars.example`

```hcl
# Nothing posted means no data points, not zeros.
treat_missing_data = "breaching"
```

- `actions_enabled = true` with `lifecycle { ignore_changes = [actions_enabled] }`: alarms are created on, so a new environment is loud until it is running, and `mise run pause` / `mise run start` toggle the actions with the schedule. An alarm that treats missing data as breaching because of the schedule (`missed-runs`, `quiet`) sits in ALARM without emailing while paused. Add the alarm to `local.alarm_names` (the `alarm_names` output), or the toggle won't reach it
- Custom metrics use `local.metric_namespace`, which is per environment, and the alarm references the filter's `metric_transformation[0].name`
- A log metric filter matches an exact message, so see `testing/log-contracts`

---

## infra/budget

What the project costs is a design input, not something found on the bill. The shape that matters:
a small fixed monthly cost, and everything else paid per use. Cost informs the design; it doesn't
veto it. Once there's more than one office this starts to be a public service, and a design that
serves it better may cost more.

- **Shared by default.** Alarms, the SNS topic and the budget are shared by every office, so adding
  an office normally adds usage cost only. See `global/principles` (the office is the unit of
  isolation) for what is per office instead
- **Per-office cost is allowed, if it's estimated and approved first** (2026-10-29, Phase 2.2). A
  resource per office (a schedule, an alarm, a custom metric) needs its cost at each scale in the
  spec's `cost.md`, and the user approves that estimate before it's deployed. A per-office
  resource that costs nothing while idle (an EventBridge schedule, billed per invocation) still
  goes in `cost.md`, as zero fixed cost
- **Per-office visibility comes from queries and reports** by default. Logs Insights, the ledger
  and the archive already hold the per-office facts, so a per-office alarm or metric needs a
  reason a query can't meet
- **Prefer pay-per-use with no idle cost.** Lambda, on-demand DynamoDB, S3 and the scheduler cost
  nothing while idle. A resource that bills by the hour (a NAT gateway, a provisioned table, an
  always-on endpoint) needs a reason in the spec
- **Every spec carries a `cost.md`**, produced by `mise run cost`, with the figures at the scales that
  spec cares about, what is fixed and what scales, and what Infracost doesn't price. Record the
  date and the Infracost version. When a spec changes nothing, say so and show the unchanged total
- **Retention is a cost decision.** The archive and state table are kept forever
  (`infra/data-retention`), so storage grows every month. State what a new store keeps and for how
  long before adding it
- **The estimate is list price**, with no free tier subtracted. It is the worst case. Say so, then
  say what the account's free allowances do to it (the CloudWatch free alarms are the one that
  matters here)
- **The account budget (`monthly_budget_usd`) rises deliberately**, in the spec that raises
  expected spend, with the new figure in that spec's `cost.md`. It never rises to silence an alert
- A new environment is a new `Scenario` in `scripts/infracost_usage.py` and a project in
  `infracost.yml`, so its cost is estimated before anything is created

---

## infra/environments

One `infra/` deploys every environment. `var.environment` (`production` or `staging`, no default)
selects everything that differs, so the environments can't drift apart through forked files. The
locals it drives (`production`, `name`) live in `infra/locals.tf`.

### Environment-specific values

- **What Terraform creates is derived** from `var.environment` by one rule: names, tags, the metric
  namespace, production-only `count`s. Environments can't disagree about a convention
- **What exists outside Terraform is a required variable** with no default, set in that
  environment's tfvars: the Telegram token parameter, chat ids, the alert email. Never hard-code
  one environment's value in a local, a default or a conditional
- A variable whose value would print in a public log (`offices`, `alert_email`, `nws_user_agent`)
  is `sensitive = true`. The repo is public, and a plan prints variable values
- Validate such a variable against the environment where you can (the token parameter must sit
  under `/${local.name}/`), so one environment's value can't be pasted into another's tfvars

### Names

Production keeps the unsuffixed names it was created with (`weather-story-bot`). Every other
environment is `weather-story-bot-<env>`.

- Renaming the table or the bucket is a replace, which `infra/data-retention` forbids, so
  production never takes a suffix
- Everything named from `local.name` follows automatically: function, table, bucket, roles, topic,
  alarms, schedule, and the `Project` tag Cost Explorer splits on

```hcl
name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"
```

### Tags

- Every resource carries `Environment = var.environment` and `Project = local.name` through the
  provider's `default_tags` (`infra/providers.tf`). Never set either per resource
- `Environment` is always the lowercase `production` or `staging`. It's what IAM tag conditions
  (`aws:ResourceTag/Environment`) match, and they compare case-sensitively
- Things created by hand get the same tag by hand: each environment's token parameter is created
  with `--tags Key=Environment,Value=<env>` (README setup)
- Every environment's archive bucket has ABAC enabled (`aws_s3_bucket_abac`). Without it S3
  ignores bucket tags in policy conditions. With it, bucket tags are written through S3 Control
  `TagResource`, so whoever applies Terraform needs `s3:TagResource`, `s3:UntagResource` and
  `s3:ListTagsForResource`, or the provider falls back to `PutBucketTagging` and the tag change
  fails

### Differences are variables or `local.production`

- Express a per-environment difference as a variable or a `local.production` conditional, never
  as a forked `.tf` file or a copy of a resource
- A production-only resource takes `count = local.production ? 1 : 0` with a comment saying why,
  and outputs read it with `one(<resource>[*].<attr>)`
- Adding `count` to an existing resource moves it to `[0]`. The production plan shows
  "has moved to", not a replace, and anything that addresses it (`scripts/infracost_usage.py`)
  uses `[0]`

| Production only | Why |
|---|---|
| `aws_budgets_budget.monthly` | Covers the whole account; a copy per environment sends duplicate emails for the same spend |
| `aws_dynamodb_table.posted` | The MVP table is production's rollback; no other environment ever had MVP data |

### Staging

- **Staging is where real posts get watched.** Production is pipeline-only (`infra/pipeline`):
  `plan` and `deploy` refuse it unless they run in Actions or `BREAK_GLASS=1` is on the command line
- **Every environment's schedule is created `DISABLED` and its alarms are created on.** There is
  no `schedule_enabled` variable, so no environment differs by a flag. `mise run start <env>` and
  `mise run pause <env>` toggle the schedule and the alarm actions through the API
  (`scripts/set_run_state.py`), and `ignore_changes` on `state` and `actions_enabled` keeps an apply
  from undoing them. `lifecycle` can't be conditional, so production is ignored too: its schedule
  and alarms stay as they are, and `mise run pause production` is how you stop it. Terraform
  never will
- Alarms are created on, so a new environment emails (`missed-runs` and `quiet` breach on missing
  data) until it is started. That is deliberate: the first alert proves the alarms and the email
  path work, and an environment you forgot to start can't be silent
- Pausing turns the actions off and keeps the alarms, so the breaching ones sit in ALARM while
  paused, silently. Starting re-enables them, and the first runs bring them back to OK
- A new alarm goes in `local.alarm_names` (`infra/monitoring.tf`), or the toggle misses it

### Telegram

- Each environment has its own Telegram bot, and its token lives in its own SSM parameter under
  that environment's name: `/weather-story-bot/telegram-token` in production,
  `/weather-story-bot-<env>/telegram-token` elsewhere. `var.telegram_token_param_name` is required
  and validated to equal `/${local.name}/telegram-token`, the one name the boundary allows. The prefixes differ in the first path segment,
  so no environment's parameter (or IAM grant) can land inside another's
- A bot is never made an admin in another environment's channels, so a staging bug can't post
  to a public channel even with the wrong chat id

### Metrics

Custom metric namespaces are per environment (`local.metric_namespace`): `WeatherStoryBot` in
production, `WeatherStoryBot/<env>` elsewhere. The log metric filters have no dimensions, so a
shared namespace would merge staging's posts into production's `quiet` and `repost-loop` alarms.
Production keeps its original namespace so its metric history carries on.

### Tasks

The environment argument of the `plan`, `deploy`, `start` and `pause` tasks (`mise run plan <env>`) selects the backend config, the var file, the data dir and the plan file together, so
they can't disagree:

| `<env>` selects | Path (under `infra/`) |
|---|---|
| Backend config | `envs/<env>.backend.hcl` (its own state key) |
| Var file | `envs/<env>.tfvars` |
| Data dir | `.terraform-<env>/` (`TF_DATA_DIR`, relative to `-chdir`) |
| Plan file | `deploy-<env>.tfplan` |

- `plan` and `deploy` refuse `production` unless `GITHUB_ACTIONS=true` or `BREAK_GLASS=1` is set on
  the command line (`infra/pipeline`). `staging` has no such guard
- The environment is a required positional argument with `choices "staging" "production"`, so mise
  refuses anything else, and an exported variable can't stand in for it
- `plan` builds first and passes the zip's hash as `-var lambda_zip_sha256=<base64>`, so a plan is
  made for one exact build. `deploy` rebuilds and refuses to apply when the zip's hash isn't the
  planned one. The zip is reproducible (`scripts/build_zip.py`), so an unchanged build plans as
  No changes
- The Lambda's code comes from S3, never a local file in Terraform: `s3_key` is
  `<env>/lambda/<base64url of the zip's hash, unpadded>.zip` (`local.lambda_s3_key`, also an output).
  After the hash check, `deploy` reads the bucket and key from the saved plan and uploads with
  `If-None-Match: *`. A 412 means those bytes are already there, since the key is the content
- `artifacts_bucket` and `permissions_boundary_arn` are required variables (both created by
  `infra/bootstrap`). The boundary is validated to be this environment's own, and both the Lambda
  and Scheduler roles are created under it
- `environment` is passed as `-var environment=<env>`, never kept in a tfvars file, so it can't
  disagree with the backend
- A data dir per environment, because `.terraform/` remembers the backend it was initialized
  against: with a shared one, a forgotten `-reconfigure` points a staging plan at production's
  state
- Never an `infra/terraform.tfvars`: Terraform auto-loads it, so any variable missing from an
  environment's file would silently take its value (production's chat ids included)

---

## infra/iam

Grant only what the code calls, so a bug or a compromised dependency can't delete the archive or table, read other secrets or touch the rest of the account.

- Write policies as `data "aws_iam_policy_document"` blocks, not inline JSON
- One statement per need, each with a `sid` (`State`, `Archive`, `TelegramToken`)
- List the exact actions the code calls, e.g. `dynamodb:GetItem`, `dynamodb:PutItem`. No `Scan`, `service:*` or wildcard `Delete*`
- The one delete is item-level `dynamodb:DeleteItem` on the state table, for the office lease's release. Never `DeleteTable`, `DeleteObject` or `DeleteBucket`: the table and archive are permanent (`infra/data-retention`)
- Scope resources to the narrowest ARN or key prefix: `"${aws_s3_bucket.archive.arn}/stories/*"`, the one SSM parameter ARN
- The `TelegramToken` statement names that environment's own parameter (`var.telegram_token_param_name`, validated to be exactly `/${local.name}/telegram-token`, the one name the boundary allows), so no environment's role can read another's token (`infra/environments`)
- Use `*` only where the API has no resource-level permissions, and add a comment saying so
- Add a new permission in the same change as the code that calls it
- Scripts and backfills (e.g. `scripts/migrate_story_keys.py`) run with admin creds, never through the Lambda role
- Service trust policies (other than Lambda) add the confused-deputy guard:

```hcl
condition {
  test     = "StringEquals"
  variable = "aws:SourceAccount"
  values   = [data.aws_caller_identity.current.account_id]
}
```

### Tag conditions (ABAC)

The `State`, `TelegramToken` and `Archive` statements add `aws:ResourceTag/Environment` = `[var.environment]`, so a role can only reach resources tagged for its own environment, even if an ARN is wrong.

- Add the condition to the exact ARN, never use it instead of the ARN
- Allow + `StringEquals` only, so a missing tag fails closed. Never an Allow with `StringNotEquals`
- A role constrained by tag conditions never holds tag-write actions (`TagResource`, `ssm:AddTagsToResource` and the like), or it could retag its way into access
- Everything a condition reads (resource tags, bucket ABAC, hand-tagged parameters) goes live at least one deploy before the condition does. The exception is a new environment, which is created with both at once: nothing depends on it yet, and its first run is the proof (staging at Phase 2.0 Gate 2)
- `Logs` has no condition: whether `PutLogEvents` evaluates log-group tags is unverified, and a wrong guess loses logs quietly (and the metric-filter alarms with them)
- Comment each condition with what it reads: DynamoDB needs the account's ABAC setting on (console Settings page only), SSM reads the parameter's own hand-made tags, S3 object actions read the bucket's tags and need bucket ABAC on

### CI roles (`infra/bootstrap/`)

The pipeline's roles live in their own stack, applied by hand with MFA (`mise run bootstrap-plan` /
`bootstrap-deploy`), so the pipeline can never widen its own permissions. The rules above hold, with
these scoped exceptions and additions:

- **Trust:** `StringEquals` on `aud` (`sts.amazonaws.com`) and an exact `sub`, never `StringLike`.
  Subjects are built from the repository's immutable `sub_claim_prefix`
  (`repo:<owner>@<owner id>/<name>@<repository id>`, from
  `gh api repos/<repo>/actions/oidc/customization/sub`), never the name-only form, which this
  repository's tokens don't carry and a recreated repository could match. `ci-pr-plan` is
  `<prefix>:pull_request`, `ci-plan` is `<prefix>:ref:refs/heads/main`, and each `ci-apply-<env>`
  is `<prefix>:environment:<env>`
- **Plan roles may use `Get*`/`List*`/`Describe*` per service**, but only on the project's resource
  ARNs and never on objects, items or parameters: bucket ARNs and never `bucket/*`, no `GetItem`,
  `Query` or `Scan`, nothing in `ssm` or `kms`. `ReadOnlyAccess` would include `ssm:GetParameter`,
  and the `aws/ssm` key lets any principal in the account decrypt the Telegram token
- **Names:** staging matches by prefix (`weather-story-bot-staging*`). Production's names are a
  prefix of staging's, so production uses exact names, never a pattern. Bucket ARNs are exact in
  both: in IAM `*` also matches `/`, so a bucket pattern beside `s3:Get*` would read its objects
- **Tag conditions on apply roles:** `aws:ResourceTag/Environment` on existing resources and
  `aws:RequestTag/Environment` + `aws:TagKeys` on creates, where the action supports them. An apply
  role may hold a tag-write action only on its own environment's names, with `aws:RequestTag`
  pinning `Environment` to its own environment, so it can't retag a resource across environments.
  Never `aws:ResourceTag` on a tag write: creating a tagged resource also authorizes the tag action
  on it, and a resource that doesn't exist yet has no tags. No `Untag*` action: an untag request
  carries no `aws:RequestTag`, so removing a default tag goes through the laptop with MFA
- **`PutMetricAlarm` creates and updates**, so it is allowed both on `aws:RequestTag` (a new
  alarm) and on `aws:ResourceTag` (an existing one, whose update may send no tags)
- **Permissions boundary per environment** (`<env name>-boundary`, exact ARNs, never a pattern).
  `iam:CreateRole`, `PutRolePolicy` and `AttachRolePolicy` require `iam:PermissionsBoundary` to be
  the role's own environment's boundary, and no CI role can create, change or delete a policy or a
  boundary. `iam:PassRole` carries `iam:PassedToService`
- **Explicit Deny** on `dynamodb:DeleteTable`, `s3:DeleteBucket` and `s3:DeleteObject*` for the
  tables, the archive and the artifacts bucket (`infra/data-retention`, now enforced by IAM). A
  role's only delete is its own `.tflock` object. A second Deny covers what would undo it by other
  means: `dynamodb:UpdateContinuousBackups` (PITR), `s3:PutBucketVersioning` and
  `s3:PutLifecycleConfiguration` on the tables and archives. Those change from the laptop with MFA,
  so a new environment's table and archive are created there too. `UpdateTable` stays allowed and
  can turn off deletion protection, but `DeleteTable` is still denied
- **Size:** a role's inline policies total at most 10,240 characters and a managed policy 6,144, so
  an apply role is three managed policies grouped by what they do (`apply_group_of`). A statement
  that grows past a limit moves group; the plan fails on an unassigned statement. Nothing offline
  measures the size (the tests mock the policy JSON), so a statement over the limit fails at apply
- **Gaps (no tag condition keys, so only names scope them):** EventBridge Scheduler schedules,
  AWS Budgets, `sns:Subscribe` / `Unsubscribe` (a subscription carries no tags), and every read
  (`Describe*`, `Get*`, `List*`). The log group, SNS, CloudWatch alarm and S3 bucket conditions are
  unproven until the first pipeline plan and apply run under them (Phase 2.1 Gates 4a and 4b): an
  `AccessDenied` there is fixed in `infra/bootstrap` and applied by hand

---

## infra/pipeline

`.github/workflows/pipeline.yml` checks every change, plans both environments on pull requests, and deploys `main`. The roles it assumes are made in `infra/bootstrap` (`infra/iam`).

| Event | Jobs | Role (OIDC subject) |
|---|---|---|
| Pull request, this repo, not Dependabot | `checks`, then `plan` for each environment | `ci-pr-plan` (`pull_request`) |
| Push to `main` | `checks`, `deploy-staging`, `plan-production`, `deploy-production` | `ci-apply-staging` (environment `staging`), `ci-plan` (`ref:refs/heads/main`), `ci-apply-production` (environment `production`) |

- **Staging before production.** `deploy-staging` plans and applies staging; only then does `plan-production` run. Production waits for your approval in the `production` environment, so what staging did is what you see before approving
- **Production's plan is made on `main` and saved.** `plan-production` writes `plans/production/<run id>-<attempt>.tfplan` to the artifacts bucket (`mise run plan-store`, `If-None-Match: *` like every write there), and passes the key to `deploy-production` as a job output. A saved plan holds the tfvars in plain text and the repository is public, so a plan file is never a GitHub artifact. The bucket is read from the tfvars' `artifacts_bucket`, not kept as a second setting
- **A plan that changes nothing deploys nothing and asks for no approval.** `mise run plan-changes` reads the saved plan (any action but no-op and read, refresh drift, an import, or a changed output counts). Drift counts because applying writes the refreshed state back, so `mise run start`/`pause` (which change the schedule and alarms outside Terraform) cost one approved deploy on the next push. `deploy-staging` skips its Deploy step, `plan-production` saves no plan, and `deploy-production` is skipped: a job's `if` is decided before its environment's reviewer rule, so you are not asked. The check fails closed: `plan-changes --github-output` writes `changed=` only after it has a `true` or `false`, so an error fails the step rather than reading as "no changes" (never write `echo "x=$(cmd)"`, which hides `cmd`'s failure)
- **Every plan job puts its plan on the run's summary page** (`mise run plan-summary`: the counts line, then the full text in a collapsed block, cut at 500,000 characters). It is the text the log already shows, so it exposes nothing new, and the step is `continue-on-error` so a summary glitch can't block a check or a deploy. No third-party action and no PR comment
- **Dependabot gets no plan.** It can't mint OIDC tokens, so a Terraform provider bump is planned for the first time on `main`, where you read it before approving production
- **`id-token: write` only in jobs that run no tests or linters.** `checks` has none. The credentialed jobs install only the locked `terraform` and `uv` (`--locked`, no cache) and still build the zip, since the plan needs its hash. Third-party code never shares a job with AWS credentials beyond that
- **Environment-level rules gate the apply jobs.** Each environment accepts `main` only, and production needs a reviewer. The plan jobs are repository-level because an environment would change the OIDC subject the plan roles trust
- **Deploys run one at a time** (concurrency group `deploy` on the three deploy jobs, never cancelled once running; a run waiting for approval holds it, so approve or reject it before the next deploys). A job still *pending* behind another is replaced by a newer run's, which can cancel a `deploy-production` waiting its turn (the run ends red/cancelled, with no approval asked). That is safe: each deploy applies all of `main`, and Terraform refuses a stale plan
- **Plan roles use `-lock=false`** (`plan --no-lock`); apply roles lock on their own `.tflock` key
- **The tfvars are repository secrets** (`STAGING_TFVARS`, `PRODUCTION_TFVARS`), uploaded from the local files. **A new required Terraform variable means refreshing both secrets** (`gh secret set <NAME> < infra/envs/<env>.tfvars`), or every plan fails on a missing variable (Gate 4a)
- **A new AWS service or action is a bootstrap change, applied first** by hand with MFA (`mise run bootstrap-plan`, `bootstrap-deploy`). The pipeline can't widen its own roles, so a PR that needs a new permission fails with `AccessDenied` until it is applied
- **Rollback is a revert.** The zip's key is its hash, so a reverted commit rebuilds the same bytes at the same key and the Lambda goes back. It flows through the same pipeline, staging first
- **Production is pipeline-only.** `mise run plan production` and `deploy production` refuse unless `GITHUB_ACTIONS=true` or `BREAK_GLASS=1` is on the command line (`mise-tasks/check-break-glass`). The guard is a courtesy against forgetting, not a control: `GITHUB_ACTIONS=true` set by hand or a bare `terraform` bypasses it. IAM and MFA are the control. Break-glass is deliberate, with MFA, and said out loud afterwards. Use it for an emergency, and for what the apply roles can't do:
  - **A new table or archive.** The retention Deny blocks the PITR, versioning and lifecycle settings Terraform applies right after creating one (`infra/iam`, `infra/data-retention`)
  - Removing a default tag, or anything else the roles are denied
- **A laptop deploy of production leaves staging behind.** Bring staging to the same commit through the pipeline afterwards, so the next merge doesn't plan against a surprise
- **The shared setup is a local composite action**, `.github/actions/ci-setup` (locked terraform and uv, backend config and tfvars, OIDC credentials), so a pin or hardening change is made once. The caller checks out first and keeps `id-token: write`
- **Workflows and that action are linted by `mise run lint-actions`** (actionlint, zizmor), which `lint` includes. `mise run lint-actions-auditor` (zizmor's stricter auditor persona) is a separate task, run by hand and not part of `lint`: read it whenever a workflow or action changes, and before a new one that holds apply credentials merges. Accept a finding only with an inline `# zizmor: ignore[<audit>] <reason>`, so a clean run means every one was decided. Never add a token to `mise.toml` or a command line

---

## testing/handler-tests

Deciding and acting are tested separately, matching `planner.py` and `handler.py`.

`tests/test_planner.py` covers `select_active` and `decide`: table-driven, no moto and no respx — `make_story(...)` listings, `PostedRecord` records and a fixed `now` in, `Decision`s out. It proves outcomes (`post`/`update`/`unchanged`/`expired`/`rejected`) and ambiguity reasons, never side effects.

`tests/test_handler.py` runs the real `NwsClient`, `PostedStore`, `StoryArchive` and `TelegramClient` over respx + moto. Don't stub `Services`. Ordering bugs (archive -> post -> record -> delete, see `backend/side-effect-order`), key or fingerprint mismatches and wire-shape bugs only show up when the real pieces run together.

- Use the `services` and `api` fixtures. `api` mocks NWS and Telegram, and message ids count up from 100
- Inject time and waits: `run(services, now=...)`, `sleep=lambda _: None`. Never use the real clock (except the `lambda_handler` end-to-end test, which moves `endTime` to 2999)
- Assert on the whole summary with `counts(...)`. Unlisted counts must be 0:

```python
assert run(services)["MKX"] == counts(updated=1, skipped=1)
```

- Change NWS between runs with `revise(api, mkx_payload, image, **changes)`
- If a test posts, reposts or deletes, run again and assert only skips with no new photo or delete calls. Pure reject or fail tests can skip this
- Check side effects through the real stores (`posted_record`, S3 keys, `deleted_ids`), not internals

---

## testing/log-contracts

Some log messages are an API. CloudWatch metric filters in `infra/monitoring.tf` match `$.message` exactly ("Telegram message sent" -> StoriesPosted, "Ambiguous stories from NWS" -> AmbiguousStories), and runbooks compare "Story posted" against them.

- Pin each one with a test. Add a comment naming the filter, alarm or runbook that depends on it
- Match the whole message and unpack exactly one record:

```python
caplog.set_level(logging.INFO, logger="weather_story_bot")
[rec] = [r for r in caplog.records if r.getMessage() == "Telegram message sent"]
assert vars(rec)["chat_id"] == "-1001"
```

- Check structured fields with `vars(rec)`, not by parsing text
- Also check the message is absent when it shouldn't fire (e.g. a failed send)
- To rename one, change the log call, its test and the `monitoring.tf` pattern or runbook in the same commit
- A test that logs or raises near Telegram asserts `TOKEN not in` the captured text

---

## testing/test-data

Build stories from NWS-shaped data so tests use the same parsing path as production.

- One story: `make_story(**overrides)` from `tests.conftest`. Overrides use the NWS camelCase keys (`startTime`, `updateTime`, `download`), not `Story` attributes
- A real listing: `mkx_payload` (raw JSON) or `mkx_stories` (parsed)
- `mkx_payload` is function-scoped and re-read from disk each test, so mutate it in place (`.reverse()`, `.append()`, `story.update(...)`). Never widen its scope

### Production quirks become cases

When NWS does something unexpected, add a case to the closest parametrized test and date the comment:

```python
@pytest.mark.parametrize(
    "overrides",
    [
        # NWS re-issued "High Swim Risk" on 2026-09-15 under a new UUID, updateTime at the epoch.
        {"download": REISSUED_DOWNLOAD, "updateTime": EPOCH, "altText": ""},
    ],
)
```

- Capture a new file in `tests/fixtures/` only when overrides can't express the quirk

---

## testing/terraform-tests

`terraform test` checks the rules `infra/` is meant to keep, offline. They were `terraform console`
checks by hand in Phase 2.0. Now a pull request and a laptop run them the same way (`mise run tftest`).

### Running

- `mise run tftest` runs `terraform init -backend=false` and `terraform test` in `TF_DATA_DIR=.terraform-test`,
  so it never touches an environment's state or its `.terraform-<env>/` dir
- Tests live in `infra/tests/*.tftest.hcl`: `environments` (names, namespaces, production-only
  `count`s, tags), `variables` (sensitivity and validations) and `iam` (policy conditions)
- The bootstrap stack has its own tests in `infra/bootstrap/tests/` (`trust`, `plan_roles`,
  `apply_roles`, `artifacts`), run by the same `mise run tftest` after the main stack's
- They need no AWS credentials. `mock_provider "aws"` replaces the provider, so the laptop's
  gitignored `override.tf` (`profile = "weather-deploy"`) is never configured

### Writing them

- Every file declares the same `mock_provider "aws"` with `override_data` for
  `aws_caller_identity` (`account_id = "123456789012"`). A mocked resource's ARN is a random
  string that arguments such as `role` and `alarm_actions` reject, so give each resource type
  used that way an ARN under `mock_resource ... defaults`. A mocked `aws_iam_policy_document.json`
  is a placeholder (`"{}"`)
- **Assert on the policy documents' inputs**, not on `.json`:
  `one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"])`, then
  its `resources`, `actions` and `condition`
- Run with `command = apply` (the default) when a value comes from a mocked resource, as a plan
  leaves it unknown. Use `command = plan` for variable rules
- A validation gets one `run` each with `expect_failures = [var.<name>]`. Any other failure still
  fails the run, so put one bad value in each
- Anything a test needs to read, such as the provider's `default_tags`, is a local
  (`local.default_tags`) that the production code uses too. Never add a local only for a test
- **Compare collections with `jsonencode(a) == jsonencode(b)`** (or `toset(a) == toset(b)` for
  unordered lists). Terraform's `==` is false for a list against a tuple or a map against an
  object, and a failed comparison of mocked values can crash the test runner while it prints the
  diff ("value has marks"). A crash like that means an assertion is false, not a Terraform bug:
  bisect it one assert at a time
- Build an ARN a test reads from names (`"arn:aws:s3:::${local.bucket}"`), not from a mocked
  resource's `.arn`, which is a random string
- A new test must be seen to fail: break the rule it guards (a capitalised tag, a wildcard ARN, a
  removed `sensitive`), run `mise run tftest`, and put it back

### What gets a test

- Names and metric namespaces per environment, and the production-only `count`s
- The lowercase `Environment` tag (`local.default_tags`)
- Each variable validation, including the slash-less and other-environment forms
- Every `sensitive` variable (`issensitive`)
- Every IAM statement's exact ARN and its `Environment` tag condition. `Logs` has none, and
  that is asserted too
- Every trust policy, boundary and tag condition gets a test in the task that adds it. The
  bootstrap stack's: each role's `aud` and exact `sub`, the plan roles reading no object, item or
  parameter, each apply role naming only its own environment's ARNs and state key, the Deny, the
  boundary conditions, tag writes pinning the request tag but never the resource tag, the
  retention Deny, and no allowed bucket ARN with a wildcard
- Policy documents built from a `for_each` or a `dynamic` block are asserted per environment the
  same way: collect an environment's statements across its documents, then filter by `sid`

### Security scan (Checkov)

`mise run scan` runs Checkov on `infra/` (which includes `infra/bootstrap/`) from its own uv project,
`tools/checkov/`, the same on a laptop and in CI, so no third-party GitHub Action ever runs beside CI credentials.
It is blocking: any failed check exits non-zero.

- Fix a finding when the fix is free and safe. Otherwise suppress it inside the resource block:
  `#checkov:skip=CKV_AWS_50:<why>`, one line per check
- **The reason is mandatory.** `mise run scan` fails first on any `checkov:skip=<ID>` with no
  `:reason`. Write the actual constraint (cost, a service limit, a decision), and name the
  standard or spec where it is recorded
- A fix that changes infrastructure goes in the plan for the spec's next deploy gate. Do not
  apply it from the scan
- Checkov is a separate project because it pins `boto3` exactly, which the main project's dev tools
  can't share. Its version lives in `tools/checkov/uv.lock`, never in `mise.toml`, and Dependabot proposes
  bumps
- A Checkov bump can add rules. Triage what the new rules find in the same PR that bumps it
- **Checkov scans Terraform only; workflows are `mise run lint-actions`** (actionlint + zizmor).
  Checkov's GitHub Actions framework silently drops any workflow its bundled schema rejects, and
  reports `passed 0, failed 0, resource_count 0` with no error. It did that to `pipeline.yml` over
  `cancel-in-progress: ${{ ... }}` (Checkov 3.3.29), so a clean Checkov result for a workflow means
  nothing. Do not point `scan` at `.github`
