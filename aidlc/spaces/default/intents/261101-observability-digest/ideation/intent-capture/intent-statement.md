# Intent Statement: Seeing the bot's health, its warnings and its errors

## Problem Statement

The request, in the owner's words, started as a CloudWatch dashboard and a weekly digest of any warnings that occur. [desc]

The owner then removed the digest: warnings are to be part of the dashboard, which the owner reviews on a regular basis and which never notifies them. [Q15]

Later the owner added one exception: any warning trips an alarm that emails them, like the current alerts. [Q17]

The dashboard is the owner's starting framing, not a settled solution; how the problems below get solved is decided in later stages. [desc]

Three problems sit behind that request: [Q1]

- Warnings happen that never trip an alarm, so the owner never hears about them. [Q1]
- There is no at-a-glance view of how the bot is doing; finding out means digging through logs. [Q1]
- Some alarms depend on the exact wording of a log message, so rewording or refactoring that message can silently stop the alarm from working. [Q1]

A "warning" here means anything unusual, including patterns that nothing records as a warning today. [Q6]

Errors are shown on the dashboard the same way as warnings: a named list of error kinds, fixed when the requirements are written, with the same "none missed" target. [Q16]

## Target Customer

The only reader of the result is the owner. [Q2]

The owner benefits by seeing warnings that are invisible today, by seeing the bot's health quickly from one place, and by being able to trust that the alarms still work after the code changes. [Q1] [Q3]

The owner reviews warnings and errors on the dashboard on a regular basis. [Q15] [Q16] Any warning also trips an alarm that emails the owner. [Q17]

## Success Metrics

| Metric | Target | How it is checked | Source |
|--------|--------|-------------------|--------|
| Warnings and errors of the named kinds that appear on the dashboard | 100%: none missed | Against the named lists of warning and error kinds, and how long each stays visible, all fixed when the requirements are written | [Q3] [Q10] [Q15] [Q16] |
| Time for the owner to tell whether the bot is healthy, from one place | Under 1 minute | Against a short list of health signals, fixed when the requirements are written | [Q3] [Q12] |
| Alarms left without their signal because a log message was reworded or refactored | Zero | An automated test fails whenever a change would leave an alarm without its signal | [Q1] [Q3] [Q13] |
| Warnings of the named kinds that happen without the warning alarm emailing the owner | Zero | Against the named list of warning kinds, fixed when the requirements are written | [Q10] [Q17] |

## Initiative Trigger

The owner wants to learn observability on AWS, and this bot is a real project to practise on. [Q4]

## Constraints

- There is no weekly digest. [Q15]
- Any warning trips an alarm that emails the owner, like the current alerts. [Q17]
- Errors are shown on the dashboard, with no new notification of their own. [Q15] [Q16]
- The existing alarm emails stay as they are unless a later stage changes them. [Q14]
- Added AWS cost stays at or under about $5 a month. [Q9]

## Initial Scope Signal

- Workflow-selected plan: `classic`, tailored for this work. [scope]
- User-confirmed product boundary for the first version: [Q5] [Q14]
  - What the bot posts to Telegram, and how it posts, does not change. [Q5]
  - No third-party or paid monitoring services outside AWS. [Q5]
  - The existing alert emails are open to change if the work needs it. [Q14]

## Assumptions & Open Questions

Open item for requirements: the owner sets their own review cadence for the dashboard, and nothing yet tells them if the warning view has gone stale or broken (the old digest-failure concern, Q11, no longer applies). Requirements decide whether and how to detect that. [Q15]
