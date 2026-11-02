# Scope Document: Seeing the bot's health, its warnings and its errors

## Scope Summary

Source: the approved intent statement (`ideation/intent-capture/intent-statement.md`).

Give the owner one dashboard per environment that shows whether the weather-story bot is healthy and what warnings and errors have happened, make the bot's alarms independent of log message wording, and review the bot's logging as a whole. The owner is the only reader. Warnings and errors are reviewed on the dashboard; in addition, any warning trips an alarm that emails the owner. There is no weekly digest.

## In Scope

| Capability | What it is | Priority |
|------------|------------|----------|
| Health view | One place to tell in under a minute whether the bot is healthy, against a short list of signals fixed in requirements | Must-have, delivered first |
| Warnings and errors view | Warnings and errors of named lists of kinds, fixed in requirements, shown on the dashboard the owner reviews regularly | Must-have, delivered second |
| Sturdy alarms | Alarms keep their signal when a log message is reworded, proven by an automated test that fails if a change would leave an alarm without its signal | Must-have |
| Warning alarm | Any warning of the named kinds trips an alarm that emails the owner, like the current alerts | Must-have |
| Logging review | A full review of all the bot's logging, as its own deliverable | Must-have |
| Broader logging tidy-up | Consistent levels and fields, beyond what the three capabilities above need | Must-have |

## Out of Scope

- Dashboard views for offices the bot does not cover yet.
- Any change to what the bot posts to Telegram, or how.
- Third-party or paid monitoring services outside AWS.
- A weekly digest.
- Any new notification other than the warning alarm email (errors get none of their own beyond the existing alerts).

## Constraints

- Added AWS cost stays at or under about $5 a month.
- The existing alert emails are open to change if the work needs it; they stay as they are unless a later stage changes them.
- Times shown to the owner are in America/Chicago.

## Success Criteria

- Warnings and errors of the named kinds appear on the dashboard: none missed. The named lists and how long each stays visible are fixed in requirements.
- The owner can tell whether the bot is healthy in under a minute, from one place.
- No alarm is left without its signal because a log message was reworded or refactored, checked by an automated test.
- No warning of the named kinds happens without the warning alarm emailing the owner.

## Sequencing and Timing

Health view first, then the Warnings and errors view; the Warning alarm, Sturdy alarms and the logging work are placed by what each depends on. There are no hard deadlines.

## Definition of Done

The work is running in production, with the dashboard showing real warnings and health signals.

## Open Items for Requirements

- The named lists of warning and error kinds, and how long each stays visible on the dashboard.
- The short list of signals that together mean healthy.
- Whether and how to detect a stale or broken warning view, beyond the warning alarm.
- Whether errors that no existing alarm covers should also trip an alarm (the owner asked for warnings only).
- How the logging review's findings are delivered.
