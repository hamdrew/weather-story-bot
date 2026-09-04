# Alerting Simplification Requirements Amendment Questions

## Purpose

This amendment reduces operational complexity for the personal one-owner project while preserving
the requested dedicated private Telegram alert channel and one-way SNS/email fallback. The current
U-01 Infrastructure Design work is paused until these choices are resolved and the affected
requirements, stories, units, and construction artifacts are reconciled and reapproved.

## Question 1: Alert Trigger Model

How should application-originated failures reach the dedicated Telegram alert channel?

**Recommendation: A.** Emit safe bounded CloudWatch metrics and alert only through CloudWatch alarm
state transitions. This removes a custom application alert-event pipeline while preserving the
dedicated Telegram channel through the alarm-triggered dispatcher.

A) **Recommended** — Emit safe application metrics; use CloudWatch alarms/composites and their
state-transition actions as the only alert trigger into the Telegram dispatcher

B) Keep direct application events to the Telegram dispatcher in addition to CloudWatch alarms

C) Keep the current direct application alert-event path and CloudWatch trigger behavior unchanged

X) Other (please describe after the `[Answer]:` tag below)

## Question 2: Cooldown and Deduplication

What should replace the custom four-hour application fingerprint/cooldown state?

**Recommendation: A.** Use CloudWatch's native state-transition behavior, M-of-N evaluation, and
optional composite-alarm suppression. This is simpler but deduplicates at alarm-condition level,
not arbitrary application-event level.

A) **Recommended** — Remove `ALERT#` fingerprint/cooldown/aggregation state and rely on CloudWatch
alarm state transitions, evaluation windows, missing-data settings, and composites where justified

B) Retain DynamoDB fingerprint/cooldown state only for application-originated alert events

C) Retain the existing full fingerprint/cooldown/aggregation design

X) Other (please describe after the `[Answer]:` tag below)

## Question 3: Dedicated Telegram and Fallback Path

How should the retained dedicated Telegram channel and SNS/email fallback operate?

**Recommendation: A.** A small alarm-notification Lambda can format bounded safe alarm context for
the private Telegram channel and invoke the separate fallback SNS topic exactly once only after a
definitive Telegram failure; no path returns to the trigger topic.

A) **Recommended** — CloudWatch alarm action → dedicated SNS trigger topic → alert-notification
Lambda → private Telegram alert; definitive Telegram failure → one separate SNS/email fallback

B) CloudWatch alarm action → SNS email and Telegram in parallel, with no dispatcher

C) CloudWatch alarm action → Telegram dispatcher only, with no SNS/email fallback

X) Other (please describe after the `[Answer]:` tag below)

## Question 4: Alert State and Evidence

Where should alert history and delivery evidence reside after simplification?

**Recommendation: A.** CloudWatch alarm history, bounded CloudWatch logs/metrics, SNS delivery
records, and existing run/reconciliation facts are enough for a single owner; this removes a custom
durable alert-state model without reducing secret/private-ID protection.

A) **Recommended** — Do not persist alert fingerprint, cooldown, aggregation, or delivery state in
DynamoDB; retain only bounded CloudWatch/SNS evidence and existing safe operational records

B) Persist a minimal DynamoDB record for every Telegram alert delivery outcome

C) Keep the current alert fingerprint and delivery state model

X) Other (please describe after the `[Answer]:` tag below)

## Question 5: Alert Scope

Which conditions should receive a private Telegram alert?

**Recommendation: A.** Alert only on actionable service/control failures; keep lower-signal details
in dashboards and logs. This minimizes operator noise while retaining the matters that need action.

A) **Recommended** — Alarm on failed scheduled runs, unresolved ambiguous publication, repeated
publisher/office-information failures, alert-dispatch/fallback failures, and deployment/security
control failures; use dashboards/logs for warnings and routine deferrals

B) Alert on every warning, deferral, and individual malformed source item

C) Alert only when Lambda execution itself fails

X) Other (please describe after the `[Answer]:` tag below)

## Question 6: Migration Scope

How should this amendment treat the already drafted U-01 Construction artifacts?

**Recommendation: A.** Supersede and regenerate the affected U-01 Functional Design, NFR
Requirements, NFR Design, and Infrastructure Design artifacts after requirements approval, keeping
their history in Git/audit but never mixing incompatible alert models.

A) **Recommended** — Reconcile and regenerate all affected U-01 artifacts; update story/unit/work
traceability before resuming Construction

B) Keep existing U-01 artifacts and apply only minor wording edits later

C) Leave U-01 unchanged and create an additional alert-simplification unit

X) Other (please describe after the `[Answer]:` tag below)

## Preserved Constraints

- Weather Story publication remains separate from private operational alerts.
- Dev Telegram operations remain mock-only; staging and production destinations stay isolated.
- A private Telegram alert can contain only bounded redacted context; no tokens, token-bearing URLs,
  private chat/message IDs, invite links, raw bodies, or raw exceptions may be logged or retained.
- Fallback remains one-way and loop-free. Production/sensitive deployment gates and all remote-action
  authorization rules remain unchanged.
