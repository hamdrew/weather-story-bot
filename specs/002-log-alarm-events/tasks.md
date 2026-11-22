---

description: "Task list for Log Alarms on Event Names"
---

# Tasks: Log Alarms on Event Names

**Input**: Design documents from `specs/002-log-alarm-events/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/alarm-signals.md](contracts/alarm-signals.md), [quickstart.md](quickstart.md)

**Tests**: Required. FR-007, FR-008, FR-017 and FR-018 each name an offline test, and constitution Principle IV requires
tests that fail without the change. Write each test task first and confirm it fails where the task says so.

**Organization**: Tasks are grouped by user story, in priority order: US1 and US2 (P1), US3 and US5 (P2), US4 (P3).

**Approval rule**: Tasks marked **OWNER GATE** change Git or AWS. Ask the owner and wait for a yes before each one. Never
run `git commit`, `mise run bootstrap-deploy`, `mise run deploy`, `mise run start` or `mise run pause` without it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task belongs to
- Line numbers refer to the files as they were when this list was generated. Match on the quoted text if they moved.

## Phase 1: Setup

**Purpose**: Confirm a clean starting point. No project setup is needed.

- [X] T001 Run `mise run lint ::: test ::: tftest ::: scan` from the repository root on branch `002-log-alarm-events` and confirm all pass before any edit to `infra/`, `src/`, `tests/` or `docs/`; if one fails, stop and report it

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Let production's CI role write the new alarm (research R5). Without this, the production apply is denied
`PutMetricAlarm`.

**⚠️ CRITICAL**: This must be in the branch before any production deploy. The bootstrap apply itself is T024.

- [X] T002 Update the alarm assertions in `infra/bootstrap/tests/apply_roles.tftest.hcl`, then run `mise run tftest` and confirm they fail: (a) in `the_production_role_uses_no_prefix_pattern` (L47), allow a resource when `r == "arn:aws:cloudwatch:us-east-2:123456789012:alarm:weather-story-bot-*"` OR the existing condition holds, and update the comment and error message to say alarms are the one accepted exception; (b) rename `each_environment_creates_its_own_misconfigured_alarm` (L363) to `each_role_reaches_the_alarm_names_it_should`, test the names `weather-story-bot-errors`, `weather-story-bot-misconfigured`, `weather-story-bot-slow-runs`, `weather-story-bot-staging-errors`, `weather-story-bot-staging-misconfigured`, `weather-story-bot-staging-slow-runs`, expect staging to reach only the three `-staging-` names and production to reach all six, and reword the error message; (c) in `the_verdict_composite_alarms_are_inside_each_roles_alarm_names` (L404), expect production to reach all four listed names and staging its two; (d) replace the assert at L423 with `jsonencode(local.names["production"].alarm) == jsonencode(["weather-story-bot-*"])` and the error message "Production's alarm names are the one accepted prefix pattern (research R5)."; (e) change the comment at L471 to say production's groups measured 4,171, 4,039 and 4,437 before its alarm names became one pattern, which only shrinks them
- [X] T003 In `infra/bootstrap/locals.tf`, replace production's alarm list (L56-58) so the entry reads `alarm = e.prefix ? ["${e.name}*"] : ["${e.name}-*"]`, and rewrite the comment at L10-13 to say production lists exact names for every kind except alarms, whose `weather-story-bot-*` pattern also matches staging's alarm names, an owner-accepted trade-off (research R5), while staging's role still cannot write production's alarms; change no other kind, then run `mise run tftest` and confirm T002's assertions pass

**Checkpoint**: The bootstrap tests pin production's new pattern and staging's isolation.

---

## Phase 3: User Story 1 - Alarms survive a change of wording (Priority: P1) 🎯 MVP

**Goal**: Both log filters count the stable `event` field and nothing else.

**Independent Test**: `mise run tftest` pins both exact patterns. T022 proves them against reworded sample lines.

### Tests for User Story 1

- [X] T004 [US1] In `infra/tests/environments.tftest.hcl`, add one assert to `production_keeps_the_original_metric_namespace` (L140) and one to `staging_has_its_own_metric_namespace` (L157) requiring `aws_cloudwatch_log_metric_filter.stories_posted.pattern == "{ $.event = \"telegram.message_sent\" }"` and `aws_cloudwatch_log_metric_filter.nws_ambiguous.pattern == "{ $.event = \"nws.ambiguous_stories\" }"` (FR-007), then run `mise run tftest` and confirm both fail

### Implementation for User Story 1

- [X] T005 [US1] In `infra/monitoring.tf`, set the `stories_posted` pattern (L36) to `"{ $.event = \"telegram.message_sent\" }"` and the `nws_ambiguous` pattern (L151) to `"{ $.event = \"nws.ambiguous_stories\" }"`; change no filter name, metric name, namespace or value (FR-001 to FR-004); reword the comments at L31-32 and L146-147 to say each filter counts that event and does not depend on message text; run `mise run tftest` and confirm T004 passes
- [X] T006 [P] [US1] Update comments only, leaving every log call as it is (FR-010): in `src/weather_story_bot/handler.py` L221-222 say the `nws-ambiguous` alarm's metric filter counts the event `nws.ambiguous_stories`; in `src/weather_story_bot/telegram.py` L99-101 say the StoriesPosted metric filter counts the event `telegram.message_sent`, so the repost-loop alarm sees every delivered post, even ones never recorded
- [X] T007 [P] [US1] Update comments only: in `tests/test_telegram.py` L210 and `tests/test_handler.py` L471-472 and L542-543, say the StoriesPosted metric filter counts the event `telegram.message_sent` instead of matching message text; leave every assertion as it is

**Checkpoint**: Both filters match on `$.event` alone, and no comment says they match message text.

---

## Phase 4: User Story 2 - Alarm history and behavior carry on (Priority: P1)

**Goal**: The cutover changes only what the filters match, so metric history and alarm behavior continue.

**Independent Test**: `mise run tftest` pins the unchanged settings. T025 reviews the real plan, and T027 compares the
post count after the first production post.

### Tests for User Story 2

- [X] T008 [US2] In `infra/tests/environments.tftest.hcl`, add asserts to `production_keeps_the_original_metric_namespace` and `staging_has_its_own_metric_namespace` pinning each filter's `name` (`<name>-stories-posted`, `<name>-nws-ambiguous`), `metric_transformation[0].name` (`StoriesPosted`, `AmbiguousStories`) and `metric_transformation[0].value` (`"1"`) (FR-004); these guard existing behavior, so they pass immediately; leave the existing alarm-settings run `the_five_existing_alarms_are_unchanged` in `infra/tests/dashboard.tftest.hcl` as the FR-005 pin

**Checkpoint**: A change to a filter's identity or an existing alarm's settings fails offline.

---

## Phase 5: User Story 3 - The contract cannot drift unnoticed (Priority: P2)

**Goal**: A one-sided rename of a signal event fails the project's checks and names the event.

**Independent Test**: T011 renames each event on one side and runs `mise run test`.

### Tests for User Story 3

- [X] T009 [US3] In `tests/test_logging_review.py`, add `MONITORING = ROOT / "infra" / "monitoring.tf"`, a pure helper `_filter_events(source: str) -> dict[str, str | None]` that maps each `resource "aws_cloudwatch_log_metric_filter" "<name>"` to the event in its pattern, or `None` unless the pattern fully matches `{ $.event = \"<event>\" }` as written in HCL, and these tests: every filter in `infra/monitoring.tf` has an event; the filters' events equal exactly `{"telegram.message_sent", "nws.ambiguous_stories"}`; each is emitted as a constant event in `_src_calls()` and listed in `_inventory()`, with a failure message naming the missing event and the side that lacks it (FR-008); and `_filter_events` returns `None` for a `$.message` sample and the event for a `$.event` sample

### Implementation for User Story 3

- [X] T010 [US3] In `tests/test_logging_review.py`, key the sent-line rule on its event (research R3): replace `_SENT` (L27) with `_SENT_EVENT = "telegram.message_sent"`; in `_problems` (L110-115) require an event only for `_MUST_HAVE_EVENT` levels and report "an event on a call that should have none" only when an INFO-level call's event is not `_SENT_EVENT`; in `test_warnings_and_errors_have_events_and_only_the_sent_line_among_info_does` (L175) allow an INFO row's event only when it equals `_SENT_EVENT`; remove the two parametrized `_SENT` no-event cases (L226-229, L263-266), because T009 now catches a missing sent event; add a test that `logger.info("Reworded", extra={"event": "telegram.message_sent"})` reports no problem; run `mise run test`
- [X] T011 [US3] Prove the drift check per `specs/002-log-alarm-events/quickstart.md` step 2: rename `telegram.message_sent` only in `src/weather_story_bot/telegram.py`, run `mise run test` and confirm a failure names the event, undo it; repeat with only `infra/monitoring.tf`; repeat both for `nws.ambiguous_stories` using `src/weather_story_bot/handler.py`; confirm `git diff` shows none of the renames remain (SC-005)

**Checkpoint**: Rewording a message no longer trips the sent-line rule, and renaming an event on one side fails.

---

## Phase 6: User Story 5 - The owner hears about runs that are getting slow (Priority: P2)

**Goal**: One slow-run alarm per environment, switched by start and pause, plus one dashboard chart outside the verdict.

**Independent Test**: `mise run tftest` pins the alarm and chart. T026 proves the alert and recovery emails on staging.

### Tests for User Story 5

- [X] T012 [P] [US5] In `infra/tests/environments.tftest.hcl`, add runs `production_has_the_slow_run_alarm` and `staging_has_its_own_slow_run_alarm` (staging uses the same three variable overrides as `staging_is_suffixed_everywhere`) asserting (FR-013, FR-014, FR-016, FR-017): `alarm_name` is `<name>-slow-runs`; `namespace == "AWS/Lambda"`; `metric_name == "Duration"`; `dimensions.FunctionName` is the function's name; `statistic == "Maximum"`; `period == 900`; `evaluation_periods == 2`; `datapoints_to_alarm == 2`; `comparison_operator == "GreaterThanThreshold"`; `threshold == 60000`; `treat_missing_data == "notBreaching"`; `actions_enabled == true`; the description contains `60 seconds`, `300 seconds` and `record.metrics.durationMs`; the alarm's name is in `output.alarm_names`
- [X] T013 [P] [US5] In `infra/tests/dashboard.tftest.hcl` (FR-017, FR-018): append `"weather-story-bot-slow-runs"` to the expected `alarm_names` at L241 and say six alarms in its error message; assert the new alarm emails `aws_sns_topic.alerts.arn` on ALARM and OK; rename `the_thirteen_widgets_sit_on_the_grid_in_reading_order` to `the_fourteen_widgets_sit_on_the_grid_in_reading_order`, update the comment at L246, append `[0, 33, 12, 6]` to the expected grid and `"metric"` to the expected types, and add "the duration chart" to the order message; change "Eight metrics today" at L537 to "Nine metrics today"; add a run `the_duration_chart_reads_the_alarm_and_stays_out_of_the_verdict` asserting widget 13 has `view == "timeSeries"`, `metrics[0][0].expression == "m1/1000"`, a last element in `metrics[1]` with `id == "m1"`, `visible == false`, `stat` and `period` equal to the alarm's, the metric and function from the alarm, one horizontal annotation with `value == aws_cloudwatch_metric_alarm.slow_runs.threshold / 1000` (60) and `fill == "above"`, and asserting the slow-run alarm name appears in neither composite rule nor `local.not_healthy_alarms`, and its ARN in neither alarm-list widget (indexes 2 and 7); run `mise run tftest` and confirm the new asserts fail

### Implementation for User Story 5

- [X] T014 [US5] In `infra/monitoring.tf`, append `aws_cloudwatch_metric_alarm.slow_runs.alarm_name` to `local.alarm_names` (L3-9) and add resource `aws_cloudwatch_metric_alarm.slow_runs` after `nws_ambiguous`: `alarm_name = "${local.name}-slow-runs"`; `namespace = "AWS/Lambda"`; `metric_name = "Duration"`; `dimensions = { FunctionName = aws_lambda_function.bot.function_name }`; `statistic = "Maximum"`; `period = 900`; `evaluation_periods = 2`; `datapoints_to_alarm = 2`; `comparison_operator = "GreaterThanThreshold"`; `threshold = 60000` with a comment that `Duration` is in milliseconds; `treat_missing_data = "notBreaching"`; `actions_enabled = true`; `alarm_actions` and `ok_actions` set to `[aws_sns_topic.alerts.arn]`; `lifecycle { ignore_changes = [actions_enabled] }`; `alarm_description = "The slowest run took more than 60 seconds in 2 consecutive 15-minute periods. The function's time limit is ${aws_lambda_function.bot.timeout} seconds, so runs are slowing down before they start to fail. Read each run's duration in the record.metrics.durationMs field of platform.report lines in the logs: ${local.logs_console_url}"`; confirm T012 passes
- [X] T015 [US5] In `infra/dashboard.tf`, add `local.duration_chart`, a `metric` widget with `view = "timeSeries"`, `region = var.region`, `title = "Slowest run: seconds per 15 minutes"`, `metrics = [[{ expression = "m1/1000", label = "Slowest run (seconds)", id = "e1" }], [alarm.namespace, alarm.metric_name, "FunctionName", alarm.dimensions["FunctionName"], { stat = alarm.statistic, period = alarm.period, id = "m1", visible = false }]]`, `annotations.horizontal = [{ label = "Alarm threshold", value = alarm.threshold / 1000, fill = "above" }]` and `yAxis = { left = { min = 0 } }`, where `alarm` is `aws_cloudwatch_metric_alarm.slow_runs`; add a third list to the `concat` in `local.dashboard_rows` (L144-158): `[{ height = 6, widgets = [{ width = 12, widget = local.duration_chart }] }]`; append " The slowest-run chart is for information and never changes the verdict." to the last line of `local.detail_markdown` (L110); do not add the alarm to `health_signals` or `not_healthy_alarms`; run `mise run tftest` and confirm T013 passes

**Checkpoint**: Each environment has the alarm and chart, and the verdict rules are byte-for-byte unchanged.

---

## Phase 7: User Story 4 - Alarm emails point at the right lines (Priority: P3)

**Goal**: The `repost-loop` and `nws-ambiguous` emails name the event to search for.

**Independent Test**: `mise run tftest` checks the descriptions.

### Tests for User Story 4

- [X] T016 [US4] In `infra/tests/environments.tftest.hcl`, add a run `alarm_emails_name_the_event_to_search_for` asserting the `repost_loop` description contains `telegram.message_sent` and `Story posted`, the `nws_ambiguous` description contains `nws.ambiguous_stories`, neither contains `Telegram message sent` or `Ambiguous stories from NWS`, both contain `local.logs_console_url`, and the `quiet` description still contains `Run complete` (FR-009); run `mise run tftest` and confirm it fails

### Implementation for User Story 4

- [X] T017 [US4] In `infra/monitoring.tf`, edit two descriptions and nothing else on those alarms: in `repost_loop` (L126) replace `the logs for \"Telegram message sent\" lines with repeated image_filename values` with `the logs for lines with event telegram.message_sent and repeated image_filename values`; in `nws_ambiguous` (L162) replace `fields of \"Ambiguous stories from NWS\" lines in the logs` with `fields of lines with event nws.ambiguous_stories in the logs`; leave `quiet` as it is; run `mise run tftest` and confirm T016 passes

**Checkpoint**: All user stories pass offline.

---

## Phase 8: Polish, Proof and Delivery

**Purpose**: Move the written contract, pass the gates, prove the filters and deliver in the planned order.

### Written contract

- [X] T018 [P] In `.specify/memory/constitution.md` (FR-011, research R9): in Principle IV change "any log message an alarm depends on" to "any log event an alarm depends on" and the rationale's "an alarm string" to "an alarm's event name"; replace Principle V's contract bullet (L59-60) with "Log events that feed metric filters (`nws.ambiguous_stories`, `telegram.message_sent`) are contracts: they change only in the same change as `infra/monitoring.tf`."; in Governance (L110) change "alarm-contract strings" to "alarm-contract event names"; set the last line to `**Version**: 1.1.0 | **Ratified**: 2026-11-09 | **Last Amended**: 2026-11-21`
- [X] T019 [P] In `docs/logging-review.md` (FR-011, FR-012, FR-018): reword BR1.5 (L32) to say the text did not change while events were added and the alarm filters now match the event; change BR4.1 (L40) to the alarm above 60 seconds, carried out; set D5's status (L92) from `moved` to `done` and its text to 60 s; rewrite "The slow-run check" (L108-112) to say the alarm fires when the maximum `Duration` is above 60 seconds in 2 consecutive 15-minute periods, under the unchanged 300-second limit, and that each run's duration is at `record.metrics.durationMs` on `platform.report` lines; update L134-135 to say U4 has done this; change L141-142 to 60 s; add a "Rollback" section saying a rollback to code from before U2 also requires reverting this change, because otherwise `quiet` raises a false alert while `repost-loop` and `nws-ambiguous` go blind; keep table 1's messages and events unchanged and confirm `grep -n '150' docs/logging-review.md` prints nothing
- [X] T020 [P] In `README.md`: change "all five alarms" (L236) and "the same five alarms" (L294) to six; in the alert table, make the `repost-loop` row (L288) search for `telegram.message_sent` lines and the `nws-ambiguous` row (L289) for `nws.ambiguous_stories` lines; add a `weather-story-bot-slow-runs` row after L289 ("The slowest run took more than 60 seconds in 2 consecutive 15-minute periods." / "Each run's `record.metrics.durationMs` on `platform.report` log lines, against the function's 300-second limit."); rewrite L296 so `quiet` and `repost-loop` count the event `telegram.message_sent` and `nws-ambiguous` counts `nws.ambiguous_stories`, say message text may change but event names may not change without `infra/monitoring.tf`, and keep the sentences about failed DynamoDB writes, "Updated" reposts and `INSUFFICIENT_DATA`

### Gates and proof

- [X] T021 Run `mise run format`, then `mise run lint ::: test ::: tftest ::: scan` from the repository root; fix any failure at its cause, and confirm with `git diff` that no log message text, level, event name or Telegram output changed in `src/weather_story_bot/` (FR-010)
- [X] T022 Run the FR-006 proof per `specs/002-log-alarm-events/quickstart.md` step 3: with the `readonly` AWS profile in `us-east-2`, call CloudWatch Logs `TestMetricFilter` once for each of the two patterns against the seven sample lines in `specs/002-log-alarm-events/contracts/alarm-signals.md`, using the real JSON line shape (`timestamp`, `level`, `message`, `logger`, `requestId`, plus `event` where the sample has one); compare all 14 results with the contract's table and keep the expected-versus-actual table for the pull request (SC-004); report a denied call to the owner rather than switching profile

### Delivery (each step needs the owner's go-ahead)

- [ ] T023 **OWNER GATE** Ask the owner to approve the commit, then open one pull request from `002-log-alarm-events` that includes T022's table, the rollback note from `docs/logging-review.md`, the constitution bump to 1.1.0 and a checklist item "bootstrap applied before merge"; confirm the `checks` job passes
- [ ] T024 **OWNER GATE** The owner runs `mise run bootstrap-plan` and `mise run bootstrap-deploy` from the branch with the MFA profile, before merge; expected plan per `specs/002-log-alarm-events/quickstart.md` step 4: production's 8 exact alarm names become `weather-story-bot-*` and nothing else changes
- [ ] T025 **OWNER GATE** Review each environment's plan per `specs/002-log-alarm-events/quickstart.md` step 5 (2 filters and 2 descriptions updated in place, dashboard updated in place, 1 alarm added, nothing replaced or deleted; SC-006), then the owner merges; read the pipeline's job states with `gh run view <id> --json jobs`, never `gh run watch`
- [ ] T026 **OWNER GATE** On staging, per `specs/002-log-alarm-events/quickstart.md` step 6, while the new alarm's actions are on: the owner sets `weather-story-bot-staging-slow-runs` to `ALARM` and confirms one alert email, sets it to `OK` and confirms one recovery email, then runs `mise run pause staging` and confirms only that alarm's actions change and the schedule stays disabled
- [ ] T027 **OWNER GATE** The owner approves production; then per `specs/002-log-alarm-events/quickstart.md` step 7 check with the `readonly` profile: one OK email from the new alarm and no other alarm email for 24 hours (SC-003); after the first post, `StoriesPosted` equals the count of `telegram.message_sent` lines over the same period (SC-002); posts charts are continuous, the duration chart is far below 60 seconds and the verdict is unchanged; report times in America/Chicago
- [ ] T028 Seven days after the production deploy, confirm with the `readonly` profile that `weather-story-bot-slow-runs` never entered `ALARM` (SC-008, per `specs/002-log-alarm-events/quickstart.md` step 7) and report the result to the owner

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: starts immediately.
- **Foundational (Phase 2)**: depends on Setup. It must be in the branch before production deploys, and T024 must be
  applied before merge.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on US1, since it pins the same filter resources in the same test file.
- **US3 (Phase 5)**: depends on US1, because its check reads the `$.event` patterns.
- **US5 (Phase 6)**: depends on Foundational. It shares `infra/monitoring.tf` and test files with US1, so run it after
  US1 and US2 rather than alongside them.
- **US4 (Phase 7)**: depends on Foundational. It edits `infra/monitoring.tf`, so run it after US5.
- **Polish and Delivery (Phase 8)**: depends on every story. T023 to T028 run strictly in order.

### Within Each User Story

- Write the test task first and confirm the failure it names.
- Change `infra/monitoring.tf` before `infra/dashboard.tf`, because the chart reads the alarm (T014 before T015).

### Parallel Opportunities

- T006 and T007 touch different files.
- T012 and T013 touch different test files.
- T018, T019 and T020 touch different documents.

---

## Parallel Example: User Story 5

```bash
# Write both test tasks together:
Task: "T012 Pin the slow-run alarm in infra/tests/environments.tftest.hcl"
Task: "T013 Pin the chart and verdict in infra/tests/dashboard.tftest.hcl"

# Then implement in order:
Task: "T014 Add the alarm in infra/monitoring.tf"
Task: "T015 Add the chart in infra/dashboard.tf"
```

---

## Implementation Strategy

### MVP First

1. Complete Phases 1 and 2.
2. Complete US1 and US2, the two P1 stories. Together they make the cutover safe.
3. **Stop and validate** with `mise run tftest` and `mise run test`.

The MVP is not deployed alone: the plan delivers this feature as one pull request.

### Incremental Build

1. Add US3 so the event contract is protected.
2. Add US5 to restore slow-run visibility.
3. Add US4 for clearer alarm emails.
4. Finish Phase 8, then deliver in the order T023 to T028.

---

## Notes

- Do not edit the shipped `specs/001-u2-log-events/`, `docs/handoff/` or the roadmap's history (research R9).
- The only runtime-file changes are comments in `handler.py` and `telegram.py`.
- The dashboard body must not contain "telegram" or "timezone", because existing tests reject them.
- CloudWatch limits an alarm description to 1,024 characters. Keep the edited descriptions short.
