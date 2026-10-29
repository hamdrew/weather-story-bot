# References for Wisconsin and Minneapolis Offices

## Similar Implementations

### Phase 1.2 spec (the gate model)

- **Location:** `agent-os/specs/2026-09-20-1428-decide-act-and-record/plan.md`
- **Relevance:** Stages that each end in a deployable, revertible gate, with the riskiest change
  (here, the atomic write) isolated in a stage of its own and manual work confined to one gate.
- **Key patterns:** each gate has pass criteria checked against real AWS with `readonly`, a watch
  window and a one-line rollback.

### Schedule and function

- **Location:** `infra/scheduler.tf`, `infra/lambda.tf`, `infra/iam.tf`
- **Relevance:** The one schedule becomes one per office. `OFFICES_JSON` leaves the function's
  environment.
- **Key patterns:** `state = "DISABLED"` with `ignore_changes = [state]`, `retry_policy` at 0, and
  the scheduler policy built from `local.name` rather than the function ARN (so code deploys don't
  defer it). `reserved_concurrent_executions` is a spend ceiling, not mutual exclusion.

### Bootstrap name patterns

- **Location:** `infra/bootstrap/locals.tf` (`names`, `arns`), `infra/bootstrap/apply.tf`
  (boundary), `infra/bootstrap/tests/`
- **Relevance:** Production's schedule and alarm names are exact. Both change before the main
  stack can create per-office schedules or the `misconfigured` alarm.

### State and history

- **Location:** `src/weather_story_bot/state.py` (`PostedStore.record_posted`, key builders),
  `src/weather_story_bot/history.py` (`record_event`, `_put_event`)
- **Relevance:** The current-story write and the posted/updated event become one
  `TransactWriteItems`.
- **Key patterns:** keys come only from `state.py`'s builders, events never overwrite
  (`attribute_not_exists(PK)`), and microsecond `utc_timestamp`s go in sort keys.

### Handler

- **Location:** `src/weather_story_bot/handler.py`
- **Relevance:** `run` loops over offices today. It becomes one office from the event, and
  `_apply_post_or_update` stops writing the posted event itself.
- **Key patterns:** the office and request-id `ContextVar`s plus the log record factory, the
  lease around `_run_office`, the run record after release, and `"Run complete"` logged before
  `ProcessingError`.

### Clients

- **Location:** `src/weather_story_bot/nws.py` (`NwsError`, `_get`),
  `src/weather_story_bot/telegram.py` (`TelegramError`, `_PhotoRejectedError`,
  `_MessageNotFoundError`, `_call`)
- **Relevance:** The private-subclass pattern in `telegram.py` is the model for structured
  "misconfigured" errors. The check script's read-only `getMe`/`getChat`/`getChatMember` go on
  `TelegramClient`.

### Run-state script

- **Location:** `scripts/set_run_state.py`, `tests/test_set_run_state.py`, `mise-tasks/start`,
  `mise-tasks/pause`
- **Relevance:** It reads `terraform output -json`, so it moves from `schedule_name` to
  `schedule_names`. It is also the pattern for a script that uses the MFA profile and injected
  boto3 clients.

### Alarms

- **Location:** `infra/monitoring.tf`
- **Relevance:** The `misconfigured` filter and alarm copy the `nws_ambiguous` pair. The
  `missed_runs` and `repost_loop` thresholds scale with `length(var.offices)`.

### Test data

- **Location:** `tests/conftest.py` (`make_story`, `mkx_payload`),
  `tests/fixtures/mkx_weatherstories.json`
- **Relevance:** Generalized to any office, with a captured MPX listing.

### Cost estimates

- **Location:** `scripts/infracost_usage.py`, `infracost.yml`, and the previous spec's `cost.md`
- **Relevance:** Task 6 produces this spec's `cost.md` at 1, 6 and 122 offices, which the user
  approves at Gate 3.
