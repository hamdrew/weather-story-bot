# Implementation Plan: Log Alarms on Event Names

**Branch**: `002-log-alarm-events` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-log-alarm-events/spec.md`

## Summary

Point the two log metric filters at the stable `event` field instead of message text, and pin that contract with
offline tests on both sides. Add one slow-run alarm per environment on Lambda's `Duration` metric (maximum above 60
seconds in 2 consecutive 15-minute periods), switched by start and pause, and one dashboard chart that stays out of the
verdict. Production's CI role lists alarm names exactly, so the bootstrap stack moves it to `weather-story-bot-*` and
must be applied by hand **before merge**. The design decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Terraform for `infra/`; Python 3.13 for the drift test. No runtime code changes

**Primary Dependencies**: AWS provider resources already in use (`aws_cloudwatch_log_metric_filter`,
`aws_cloudwatch_metric_alarm`, `aws_cloudwatch_dashboard`); standard-library `re` and `ast` in the tests

**Storage**: none

**Testing**: `terraform test` with the mock AWS provider (main and bootstrap stacks); pytest; one manual
`TestMetricFilter` run before merge (FR-006)

**Target Platform**: CloudWatch and Lambda in `us-east-2`, production and staging

**Project Type**: single project, a scheduled Lambda with Terraform infrastructure

**Performance Goals**: none. Runs average about 3.8 seconds and peaked at 14.8 seconds over the last 14 days

**Constraints**: no change to log text, levels, event names or Telegram output (FR-010); filter names, metric names,
namespaces and values stay the same (FR-004); existing alarm settings stay the same (FR-005); tests stay offline

**Scale/Scope**: 2 filters, 2 alarm descriptions, 1 new alarm per environment, 1 dashboard chart, 1 bootstrap pattern

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan meets it | Before | After |
|-----------|------------------------|--------|-------|
| I. Distrust Upstream Data | No change to parsing, identity or rejection. The ambiguous alarm keeps counting the same line. | Pass | Pass |
| II. A Repost Beats a Missed Story | No change to post-then-record. The send line still counts before the database write. | Pass | Pass |
| III. Decide Purely, Act Thinly | No planner, handler or CLI change. | Pass | Pass |
| IV. Offline, Contract-Pinned Tests | Filters, the new alarm and the event contract are pinned offline. This principle's wording moves from "log message" to "log event" in this change (v1.1.0). | Pass | Pass |
| V. Out-of-Band Observability | The new alarm emails the existing topic, needs 2 periods and sends a recovery notice. This principle's contract bullet moves to event names in this change. | Pass | Pass |
| VI. Personal Scope, Minimal Surface | No new dependency. Cost rises by $0.20 a month, to about $2.22, inside the $5 budget (research R8). | Pass | Pass |
| Security & Infrastructure | The bootstrap change widens production's alarm names to `weather-story-bot-*`, which the owner accepted (research R5). It is applied by hand with MFA, never from the pipeline. | Pass | Pass |
| Workflow & Quality Gates | One pull request, staging first, then production after approval. `mise run lint ::: test ::: tftest ::: scan` before review. No commit, bootstrap apply, start or pause without the owner's go-ahead. | Pass | Pass |

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-log-alarm-events/
├── spec.md              # the feature spec
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1 to R9
├── data-model.md        # Phase 1: filters, alarm, chart and state changes
├── quickstart.md        # Phase 1: offline gates, filter proof and rollout checks
├── contracts/
│   └── alarm-signals.md # Phase 1: the event-to-filter-to-alarm contract
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
infra/
├── monitoring.tf        # two filter patterns; repost-loop and nws-ambiguous descriptions; slow_runs alarm;
│                        #   alarm_names gains it; comments move from message text to events
├── dashboard.tf         # one seconds chart in its own row, outside health_signals; detail text
├── tests/
│   ├── environments.tftest.hcl  # exact patterns (FR-007); slow-run settings per environment (FR-017)
│   └── dashboard.tftest.hcl     # six alarm_names, 14 widgets, chart reads the alarm, verdict unchanged (FR-018)
└── bootstrap/
    ├── locals.tf        # production's alarm names become weather-story-bot-*; comment records why
    └── tests/apply_roles.tftest.hcl  # production's pattern; staging still cannot write production's alarms

tests/
├── test_logging_review.py  # filter events must be emitted and in table 1 (FR-008); sent-line rule keys on event
└── test_handler.py         # comments that describe the filter as matching message text

src/weather_story_bot/
├── handler.py           # comment only
└── telegram.py          # comment only

.specify/memory/constitution.md  # Principles IV and V, version 1.1.0 (FR-011)
docs/logging-review.md   # BR1.5, BR4.1, D5 done, 150 s becomes 60 s, rollback note (FR-011, FR-012, FR-018)
README.md                # alert table, six alarms, event names replace "don't change that message text"
```

**Structure Decision**: single project, existing layout. No new module or test file.

## Implementation Approach

New code goes in with its tests in the same change.

1. **Bootstrap**: change production's alarm names to `weather-story-bot-*` and update the role tests (R5).
2. **Filters**: change both patterns and pin them (R1, R2).
3. **Drift check**: read filter events from `infra/monitoring.tf`, and key the sent-line rule on its event (R3).
4. **Descriptions**: update `repost-loop` and `nws-ambiguous`; `quiet` is already accurate (R4).
5. **Slow-run alarm**: add it, add it to `alarm_names`, and pin it (R6).
6. **Dashboard**: add the chart in its own row and update the widget-position tests (R7).
7. **Contract and docs**: constitution, logging review, README and comments (R9).
8. **Gates**: `mise run format`, then `mise run lint ::: test ::: tftest ::: scan`.
9. **Pull request**: record the filter test results and the rollback note.

### Delivery order

Each step that changes AWS or Git needs the owner's go-ahead.

1. Open the pull request and pass `checks`. Record the FR-006 results in it.
2. **The owner applies the bootstrap stack from the branch** (`mise run bootstrap-plan`, `mise run bootstrap-deploy`).
   If this is skipped, the production apply fails with an access error on `PutMetricAlarm`.
3. Merge. The pipeline deploys staging and stops at the production approval.
4. On staging, while the new alarm's actions are still on, prove the alarm and recovery emails, then run
   `mise run pause staging` to turn that one alarm's actions off (R6).
5. Approve production, then run the post-deploy checks in [quickstart.md](quickstart.md).

## Risks

| Risk | Mitigation |
|------|------------|
| The bootstrap stack is not applied before merge, so the production deploy fails. | Delivery step 2 and a pull-request checklist item. The failure is loud and leaves the existing alarms in place. |
| Production's CI role can overwrite, retag or (after retagging) delete a staging alarm, because its pattern also matches staging's names. | Accepted by the owner: this is a personal project and staging can take some erroneous data. |
| The new alarm's first move from no data to OK sends one OK email per environment. | Expected and documented in the quickstart. It is not a false alert, so SC-003 holds (R6). |
| Paused staging has one alarm with actions on after deploy. | Delivery step 4 pauses it again. Staging has no runs, so it cannot fire in the meantime. |
| A rollback to pre-U2 code blinds the filters. | FR-012: the rollback note in `docs/logging-review.md` and the pull request says to revert this change too. |
| A dashboard edit pulls the new alarm into the verdict. | The chart is outside `health_signals`, and the exact-rule tests fail if a rule changes. |

## Complexity Tracking

No constitution violations. Nothing to justify.
