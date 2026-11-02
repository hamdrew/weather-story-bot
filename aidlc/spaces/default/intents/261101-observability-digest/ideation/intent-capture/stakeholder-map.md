# Stakeholder Map

## Key Stakeholders and Interests

| Stakeholder | Interest | Source |
|-------------|----------|--------|
| Owner (sole reader of the dashboard) | See warnings and errors that never trip an alarm today; see the bot's health at a glance; trust that alarms keep working when log messages change | [Q1] [Q2] [Q3] [Q16] |
| Owner (as learner) | Learn observability on AWS on a real project | [Q4] |

## Decision-Makers and Influencers

The answers name the owner as the only reader of this work's results, and name no other person. [Q2]

## Communication Requirements

| Requirement | Detail | Source |
|-------------|--------|--------|
| Warnings and errors | Shown on the dashboard, which the owner reviews on a regular basis; no digest | [Q15] [Q16] |
| Warning alarm | Any warning trips an alarm that emails the owner, like the current alerts | [Q17] |
| Times shown to the owner | Reported in America/Chicago | [memory:M1] |

## Assumptions & Open Questions

- The owner, as the only reader, is also the one who decides scope and priority, and nobody else influences those decisions. This was not asked directly. [assumption]
