# Initiative Brief: Seeing the bot's health, its warnings and its errors

Sources: `ideation/intent-capture/intent-statement.md`, `ideation/intent-capture/stakeholder-map.md`,
`ideation/scope-definition/scope-document.md`, `ideation/scope-definition/intent-backlog.md`,
`ideation/rough-mockups/wireframes.md` (with `user-flow.md`). No market research, feasibility assessment or team
plan was run for this work.

## Intent and Problem

The weather-story bot's owner can't see how the bot is doing without digging through logs. Warnings happen
that never trip an alarm, and some alarms depend on the exact wording of a log message, so rewording one can
silently break the alarm. The owner also wants to learn observability on AWS on a real project.

## Who It Is For

The owner alone: the only reader and the only decision-maker.

## Success Metrics

- Warnings and errors of the named kinds all appear on the dashboard: none missed.
- The owner can tell whether the bot is healthy in under a minute, from one place.
- Zero alarms left without their signal by a reworded log message, checked by an automated test.
- Zero warnings of the named kinds without the warning alarm emailing the owner.

## Market Validation

Not applicable: a single-owner project with no market.

## Feasibility and Risk Highlights

No feasibility stage was run. Risks the owner accepted going into requirements:

- The logging review is open-ended: a full review plus a broader tidy-up are both must-haves and could outgrow the dashboard work.
- The cost cap of about $5 a month is untested; requirements and design check it.
- Making alarms independent of log wording changes what today's alarms watch; the sturdy-alarms test covers it.
- A stale or broken dashboard is not yet detected beyond the warning alarm and the "unknown" verdict; requirements decide whether more is needed.

The earlier risk that "none missed" depended on the owner looking was reduced by adding the warning alarm.

## Scope Boundary

In, all must-haves, in delivery order: Health view; Warnings and errors view; Warning alarm (emails on any
warning); Sturdy alarms; a full Logging review; a broader Logging tidy-up. One dashboard per environment.

Out: dashboards for offices the bot doesn't cover; any change to Telegram posting; third-party or paid
monitoring outside AWS; a weekly digest; any new notification other than the warning alarm email.

Constraints: added cost up to about $5 a month; existing alert emails stay as they are unless a later stage
changes them; times in America/Chicago. Done when it runs in production with real warnings, errors and
health signals on the dashboard. No hard deadlines.

## Concept Visuals

One CloudWatch dashboard page per environment, top to bottom:

1. A verdict box: healthy, not healthy or unknown (unknown wins when data is missing), every signal that is off, error kinds that caused not healthy, and the total error and warning counts.
2. Signal tiles behind the verdict.
3. Errors and warnings: counts by kind and a recent list over the same window.
4. Detail charts.

## Team Plan

The owner builds it, with AI-DLC agents; no team formation was needed.

## Go / No-Go Recommendation

**Go into Inception.** The owner held only to add the warning alarm, which is now written in. Requirements
start with the open items: the named warning and error kinds, the health signals, the visibility window,
stale-view detection, and whether uncovered errors also need an alarm.
