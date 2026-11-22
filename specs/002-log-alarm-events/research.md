# Research: Log Alarms on Event Names

Live checks ran read-only on 2026-11-21 with the `readonly` profile. No NEEDS CLARIFICATION items remain.

## R1. Filter pattern

- **Decision**: use `{ $.event = "telegram.message_sent" }` and `{ $.event = "nws.ambiguous_stories" }`.
- **Rationale**: a JSON property filter on the one stable field meets FR-001 to FR-003. A trial `TestMetricFilter` run
  on synthetic lines matched only the line with the right event. It did not match reworded text with another event, the
  old messages with no event, a near-miss event with a different character in place of the dot, or a non-JSON line.
  The period is in the value, so the bracket notation CloudWatch needs for a period in a *key* does not apply.
- **Alternatives considered**: matching event or message during a transition keeps the dependency this feature removes.
  Adding `$.level` breaks FR-003.

## R2. In-place update keeps history

- **Decision**: change only `pattern` on the two existing filter resources.
- **Rationale**: the filter name, metric name, namespace and value stay the same, so the metric series continues and the
  plan shows an in-place update (FR-004, SC-006).
- **Alternatives considered**: new filters or metrics would split the charted history and risk a `quiet` false alert.

## R3. Drift check

- **Decision**: extend `tests/test_logging_review.py`. Read each `aws_cloudwatch_log_metric_filter` pattern from
  `infra/monitoring.tf`, fail if a filter has no `$.event` pattern, and require each event to be in both `src/` and
  table 1. Also change the "message-sent" rule to key on its event instead of the `_SENT` message text.
- **Rationale**: this catches a rename on either side (FR-008, SC-005). Without the `_SENT` change, rewording the line
  would still fail the checks even though no alarm depends on the text.
- **Alternatives considered**: a Terraform-only test cannot see `src/`. Importing event constants from `src/` would let
  a rename move both sides silently.

## R4. Alarm descriptions

- **Decision**: name `telegram.message_sent` in `repost-loop` and `nws.ambiguous_stories` in `nws-ambiguous`, keeping the
  log links. Leave `quiet` as it is.
- **Rationale**: `quiet` points at "Run complete" summaries and does not describe the filter, so it stays accurate
  (FR-009). A description change is an in-place update.

## R5. Production's CI role must allow the new alarm

- **Decision**: replace production's exact alarm list in `infra/bootstrap/locals.tf` with `weather-story-bot-*`, with no
  deny statement, and apply the bootstrap stack by hand before merge. This covers alarms only. Other resource kinds keep
  their exact production names.
- **Rationale**: without a change, the production apply is denied `PutMetricAlarm`. The wildcard also means later
  production alarms need no bootstrap apply.
- **Accepted trade-off (owner, 2026-11-21)**: the pattern also matches staging's alarm names, and the role's create
  permission checks only the tag in the request, so production's CI role could overwrite a staging alarm. It could also
  retag a staging alarm as `Environment=production` and then delete it, and a retagged alarm denies staging's own later
  updates. This is a personal project and staging can take some erroneous data. Staging's role still cannot write
  production's alarms.
- **Alternatives considered**:
  - Adding one more exact name needs a bootstrap apply for every future alarm.
  - Adding a deny for staging's names protects staging, which the owner decided is unnecessary.
  - Renaming production's alarms to a distinct prefix replaces seven live alarms and contradicts FR-005 and SC-006.

## R6. Slow-run alarm

- **Decision**: resource `slow_runs`, named `<name>-slow-runs`: `AWS/Lambda` `Duration`, `Maximum`, period 900, 2 of 2
  periods, `GreaterThanThreshold`, threshold `60000`, `notBreaching`, alarm and OK actions on the alerts topic,
  `actions_enabled = true` with `ignore_changes`, and appended to `local.alarm_names`.
- **Rationale**:
  - `Duration` is in **milliseconds**, so 60 seconds is `60000`. `GreaterThanThreshold` leaves a run of exactly 60
    seconds not slow.
  - AWS documents that `Duration` excludes cold-start time, so a slow init alone does not trip the alarm.
  - Keeping the existing "actions on at creation" pattern means production is protected as soon as it deploys.
- **Rollout consequences**:
  - The alarm's first move from `INSUFFICIENT_DATA` to `OK` is expected to send one OK email per environment.
  - Staging is paused today (schedule disabled, all alarm actions off), so the new alarm is the only one with actions on
    until `mise run pause staging` runs. That window is used to prove the alarm and recovery emails.
- **Alternatives considered**: creating it with actions off would avoid the OK email, but production would stay silent
  until someone remembered to run `mise run start production`.
- **Email content (FR-016)**: state the 60-second threshold, the function's limit from `aws_lambda_function.bot.timeout`,
  and where to read durations. Under the JSON format these are `platform.report` lines, at `record.metrics.durationMs`
  (confirmed on a live line), not plain-text `REPORT` lines.

## R7. Dashboard chart

- **Decision**: add one 12-wide, 6-tall `timeSeries` widget in a new last row of `local.dashboard_rows`. It plots the
  alarm's metric as hidden `m1` with the visible expression `m1/1000`, and draws a line at `alarm.threshold / 1000`.
- **Rationale**: both values come from the alarm (FR-018) and the owner reads seconds. Staying out of `health_signals`
  keeps it out of both rules, both alarm lists and the tiles. Appending last leaves every existing widget index in place.
- **Alternatives considered**: adding it to `health_signals` would change the verdict. Plotting raw milliseconds would
  be harder to read against "60 seconds".

## R8. Cost

- **Decision**: accept about $0.20 a month.
- **Rationale**: the account has exactly 10 metric alarms, the size of CloudWatch's free allowance, so both new alarms
  are billable at the Ohio list price of $0.10 each. The 4 composite alarms already cost $2.00 a month at $0.50 each.
  The expected total is about $2.22 a month with October's other spend of $0.02, below the budget's $4 actual-spend
  alert (80% of $5).

## R9. Written contract

- **Decision**: bump the constitution to **1.1.0** (materially changed guidance, no principle removed). Update
  Principles IV and V, `docs/logging-review.md` (BR1.5, BR4.1, D5, the slow-run section, the U4 notes and assumptions)
  and `README.md`. Leave the shipped `specs/001-u2-log-events/`, `docs/handoff/` and the roadmap's history as records.
- **Rationale**: FR-011 and FR-018 require the contract to move in the same change. The README is not named there, but
  it tells readers not to change the message text, which would become wrong.
