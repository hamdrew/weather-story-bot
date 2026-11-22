# Feature Specification: Log Alarms on Event Names

**Feature Branch**: `002-log-alarm-events`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Log Analytics alarms should be updated to make use of the new JSON formatted logs."

## Context

This is the log-filter part of unit U4 (sturdy alarms) of the observability effort. U2 gave the bot's important log
lines a stable `event` name and moved the function to Lambda's JSON log format. The alarms have not caught up: two
log filters still match the wording of a message, so rewording a sentence would silently blind an alarm.

| Log filter | Matches today | Should match | Alarms it feeds |
|------------|---------------|--------------|-----------------|
| stories posted | message "Telegram message sent" | event `telegram.message_sent` | `quiet`, `repost-loop` |
| NWS ambiguous | message "Ambiguous stories from NWS" | event `nws.ambiguous_stories` | `nws-ambiguous` |

The `errors` and `missed-runs` alarms read Lambda's own metrics, not the logs, so this feature leaves them alone.

**Live state (checked read-only on 2026-11-21)**:

- Production and staging both use the JSON log format, deployed on the evening of 2026-11-20 America/Chicago.
- Each environment has logged one real post since that deploy, and that line carries `event` = `telegram.message_sent`.
- No line with `nws.ambiguous_stories` has been logged yet, and no ambiguous-stories message appeared in the last 14
  days. This filter must be proven against a sample line (FR-006).
- Across the 1,344 production runs in the last 14 days, the average run took about 3.8 seconds and the slowest 14.8
  seconds. No run came near the 60-second slow-run threshold.

## Clarifications

### Session 2026-11-21

- Q: Should the slow-run alarm that U2 moved to U4 be part of this feature, even though it reads a Lambda metric rather than the logs? → A: Yes. It replaces the `run.slow` warning U2 removed (decision D5 in `docs/logging-review.md`).
- Q: Should the slow-run trigger use CloudWatch anomaly detection or a fixed threshold, and at what value? → A: A fixed threshold of 60 seconds, about four times the slowest recent run. This replaces the 150 seconds in D5, so the owner hears about a slowdown well before the 300-second limit. Anomaly detection was rejected because it would adapt to a gradual slowdown, has too little staging data to train on, and costs three alarm metrics instead of one.
- Q: Should the new slow-run alarm appear on the health dashboard, or only send email? → A: The dashboard shows the run-duration metric as one chart with the alarm's 60-second threshold. The alarm itself stays out of the dashboard's signal list, alarm lists and verdict, because that list feeds the verdict.
- Q: When and where should the proof that each log filter matches its sample lines be run? → A: Once, by hand, before merge, using CloudWatch's filter test, with the results recorded in the pull request. One run covers both environments because they share the same patterns.

## User Scenarios & Testing *(mandatory)*

The "user" is the owner, who learns about problems from alarm emails.

### User Story 1 - Alarms survive a change of wording (Priority: P1)

The owner or a future change can reword a log message without affecting any alarm, because the alarms count the
line's stable event name.

**Why this priority**: this is the purpose of the feature. A blind `quiet` or `nws-ambiguous` alarm fails silently,
which is the failure the bot's alerting exists to prevent.

**Independent Test**: check offline that each log filter matches its event and does not refer to message text. Then
test each filter against sample lines whose message has been reworded.

**Acceptance Scenarios**:

1. **Given** a line with event `telegram.message_sent` and reworded message text, **When** the stories-posted filter evaluates it, **Then** it counts one post.
2. **Given** a line with event `nws.ambiguous_stories` and reworded message text, **When** the NWS-ambiguous filter evaluates it, **Then** it counts one rejection.
3. **Given** a line whose message reads "Telegram message sent" or "Ambiguous stories from NWS" but has no matching event, **When** the filters evaluate it, **Then** neither counts it.
4. **Given** a line with any other event, or a runtime line with no event, **When** the filters evaluate it, **Then** neither counts it.

---

### User Story 2 - Alarm history and behavior carry on (Priority: P1)

Moving the filters changes what they match on and nothing the owner relies on. The alarms keep their names,
thresholds, schedules, recovery emails, charted history and paused or running state.

**Why this priority**: the `quiet` alarm treats missing data as a problem, so a broken cutover could send a false
alert or hide a real one in production.

**Independent Test**: review the infrastructure plan for the change, then compare the post count with the matching
log lines after the first production post.

**Acceptance Scenarios**:

1. **Given** the change is planned for an environment, **When** the owner reviews the plan, **Then** the only changes to alarms and filters are in-place updates, and nothing is replaced or deleted.
2. **Given** the change is deployed, **When** the bot posts a story, **Then** the existing posts metric counts it, in the environment's own namespace.
3. **Given** the dashboard charts these alarms, **When** the change is deployed, **Then** the charts show earlier and later data as one continuous series.

---

### User Story 3 - The contract cannot drift unnoticed (Priority: P2)

If someone renames a signal event in the code or in a filter without changing the other, the project's checks fail
before the change can merge.

**Why this priority**: the event names are now what the alarms depend on, so they need the protection the message
text had.

**Independent Test**: rename a signal event on one side only and run the offline checks.

**Acceptance Scenarios**:

1. **Given** a filter names an event the code does not emit, **When** the checks run, **Then** they fail and name the event.
2. **Given** the code renames a signal event, **When** the checks run, **Then** they fail.

---

### User Story 4 - Alarm emails point at the right lines (Priority: P3)

When an alarm that depends on the logs fires, its email tells the owner which event to look for.

**Why this priority**: it shortens diagnosis, but the alarms work without it.

**Independent Test**: read the alarm descriptions in the infrastructure configuration.

**Acceptance Scenarios**:

1. **Given** the `nws-ambiguous` or `repost-loop` alarm fires, **When** the owner reads the email, **Then** it names the event to search for and still links to the logs.

---

### User Story 5 - The owner hears about runs that are getting slow (Priority: P2)

When runs keep taking more than 60 seconds, the owner gets an email well before runs reach the function's 300-second
limit, and another when run times recover.

**Why this priority**: U2 removed the slow-run warning on the understanding that this alarm would replace it, so slow
runs are currently invisible until they fail.

**Independent Test**: check the alarm's settings offline, then set the staging alarm's state by hand or evaluate it
against sample durations to confirm the email and the recovery email.

**Acceptance Scenarios**:

1. **Given** the slowest run exceeds 60 seconds in two consecutive 15-minute periods, **When** the alarm evaluates, **Then** the owner gets one email by the out-of-band alert path.
2. **Given** one slow run followed by a normal period, **When** the alarm evaluates, **Then** no email is sent.
3. **Given** the alarm has fired, **When** a period passes with run times back under the threshold, **Then** the owner gets a recovery email.
4. **Given** an environment is paused or has no runs, **When** the alarm evaluates, **Then** it does not fire, and `mise run pause` and `mise run start` switch its actions with the other alarms.
5. **Given** the owner opens the dashboard, **When** runs are slow or the slow-run alarm has no data, **Then** the duration chart shows the run times against the 60-second line and the verdict does not change.

### Edge Cases

- **A run exactly at 60 seconds** does not count as slow. Only a longer run does.
- **Runs that time out** count as slow and also as errors, so repeated timeouts can send both the slow-run and `errors` emails. This is accepted, since each says something true.

- **Rolling back to code from before U2**: those lines have no event, so the filters would count nothing. `quiet` would raise a false alert while `repost-loop` and `nws-ambiguous` went blind. A rollback must also revert this change.
- **Lines logged before the deploy**: log filters only evaluate new lines, so past data stays as it is and is not counted twice.
- **Non-JSON lines**: a filter ignores them and counts nothing.
- **An update repost**: it logs the same event as a new post and still counts as one post, as it does today.
- **A post whose database record then fails**: the send line is logged first, so it still counts, which is what lets `repost-loop` catch that failure.
- **Staging is paused**: the filters update, and its alarm actions stay off.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The stories-posted filter MUST count exactly the log lines whose `event` is `telegram.message_sent`.
- **FR-002**: The NWS-ambiguous filter MUST count exactly the log lines whose `event` is `nws.ambiguous_stories`.
- **FR-003**: The filters MUST NOT depend on message text, level, logger or any other field.
- **FR-004**: The change MUST keep each filter's name, metric name, namespace and counted value, so metric history continues and staging stays separate from production.
- **FR-005**: The change MUST NOT alter any existing alarm's name, threshold, period, missing-data treatment, notification targets or enabled state, and MUST NOT change the `errors` or `missed-runs` alarms.
- **FR-006**: Before merge, each filter pattern MUST be shown, by one manual run of CloudWatch's filter test with the results recorded in the pull request, to match a real-format JSON sample line carrying its event and not to match a line with the old message and no event. The ambiguous filter MUST be proven this way because no real line exists yet.
- **FR-007**: An offline infrastructure test MUST pin both filters to their exact event names.
- **FR-008**: An offline check MUST fail when an event named by a filter is not emitted by the bot or is not listed in `docs/logging-review.md` table 1.
- **FR-009**: The descriptions of the `nws-ambiguous` and `repost-loop` alarms MUST name the event to search for. The `quiet` description MUST stay accurate.
- **FR-010**: Log message text, levels and event names MUST NOT change in this feature, and what is posted to Telegram MUST NOT change.
- **FR-011**: The project's written contract MUST move from message text to event names in the same change: constitution Principles IV and V (with a version bump), `docs/logging-review.md`, and code and test comments that describe the filters as matching message text.
- **FR-012**: The change's documentation MUST state that rolling back to code from before U2 also requires reverting this change.
- **FR-013**: Each environment MUST have a slow-run alarm that fires when the function's maximum run duration is above 60 seconds in 2 consecutive 15-minute periods.
- **FR-014**: The slow-run alarm MUST treat periods with no runs as not breaching, and MUST email both the alarm and the recovery to the environment's existing alert topic.
- **FR-015**: The slow-run alarm MUST be switched by `mise run start` and `mise run pause` along with the other alarms.
- **FR-016**: The slow-run alarm's email MUST say what the threshold is, what the function's time limit is, and where to read each run's duration in the logs.
- **FR-017**: An offline infrastructure test MUST pin the slow-run alarm's metric, statistic, threshold, periods and missing-data treatment, and its inclusion in the alarms that start and pause control.
- **FR-018**: The health dashboard MUST show one chart of the function's maximum run duration per 15 minutes, with a line at the slow-run alarm's threshold, both read from the alarm's own settings. The slow-run alarm MUST NOT join the dashboard's health signals, alarm lists or verdict, and an offline infrastructure test MUST pin this. `docs/logging-review.md` MUST record decision D5 as carried out and replace its 150-second figure with 60 seconds wherever it appears.

### Key Entities

- **Signal event**: a stable event name that an alarm counts. There are two: `telegram.message_sent` and `nws.ambiguous_stories`.
- **Log filter**: the rule that turns matching log lines into a metric data point.
- **Log-based alarm**: an alarm fed by a log filter: `quiet`, `repost-loop` and `nws-ambiguous`.
- **Slow-run alarm**: a new alarm per environment on the function's run duration, with a fixed threshold of 60 seconds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Rewording either signal line's message changes 0 alarm counts.
- **SC-002**: After the first post following the production deploy, the posts counted equal the "Telegram message sent" lines logged in the same period, with a difference of 0.
- **SC-003**: The cutover sends 0 false alarm emails in either environment during the 24 hours after deploy.
- **SC-004**: 100% of the sample-line cases in FR-006 give the expected result before merge, and the pull request records them.
- **SC-005**: A one-sided rename of either signal event is caught by the project's checks in 100% of cases, before merge.
- **SC-006**: The deployment plan shows 0 replaced or deleted alarms, filters or metrics, and exactly one new alarm per environment.
- **SC-007**: Two consecutive slow periods produce 1 alert and, after recovery, 1 recovery notice. A single slow period produces 0 alerts.
- **SC-008**: At today's run times, the slow-run alarm sends 0 emails during its first 7 days in production.

## Assumptions

- **"Log Analytics alarms" means the CloudWatch alarms fed by log filters.** These are `quiet`, `repost-loop` and `nws-ambiguous`.
- **The filters match on the event alone.** Matching event or message during a transition would keep the dependency this feature removes, and every deployed line already carries the event.
- **One new alarm per environment.** The slow-run alarm is the only addition. Two more standard alarms are expected to cost roughly $0.20 a month in total, which the plan confirms against the $5 budget.
- **Two consecutive periods, not one.** U2's note named only a threshold. The constitution forbids alarming on a single flaky run, so this alarm uses the same two 15-minute periods as `errors`.
- **A slow run is not "not healthy".** The alarm emails the owner and the dashboard charts run duration, but neither affects the verdict, because a slow run still completed its work.
- **The 60-second threshold reflects today's run times and the 300-second limit.** If either changes substantially, the threshold is revisited.
- **The warnings-and-errors digest (U5) is out of scope.**
- **U2 stays deployed.** Both environments run it today, and a rollback follows FR-012.
- **Delivery follows the project's normal path**: one pull request, staging first, then production after the owner's approval. Nothing is committed or deployed without the owner's go-ahead.
