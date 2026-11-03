# Observability Requirements: u3-health-dashboard

## Sources

- `functional-design/functional-spec.md` and `rules.md` (BR1.4, BR2.2, BR3.1, BR4.4, BR4.5, BR5.1)
- `inception/requirements-analysis/requirements.md`: NFR2, NFR3, NFR6, FR1.7, FR1.8
- `aidlc/spaces/default/memory/project.md`: report times to the owner in America/Chicago
- `aidlc/spaces/default/memory/team.md`: each pull request names what to watch after merge, with a window and the rollback

This unit is the observability: the verdict, the signal tiles and the detail charts. Its own requirements are about
reading it correctly and about how its first deploy is proved.

## Requirements

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR3.1 | No widget sets a time zone; chart and alarm times follow the browser's time zone (Q1 A, BR4.4). The widget `timezone` property takes only a fixed UTC offset and cannot follow daylight saving, so fixing -06:00 would be an hour wrong half the year. The detail heading tells the owner to set the console's time zone control to Local, which is Chicago time in Chicago all year. | Terraform test: no widget carries `timezone`; the heading text names the control. | NFR3 |
| NFR3.2 | No text on the page states a clock time or a date. | Terraform test scans the text widgets. | NFR3 |
| NFR3.3 | The time zone requirement holds only while the owner's browser is in America/Chicago. The owner accepted this (Q1 A); the heading says "Local" rather than "Chicago" so it is never wrong when travelling. | Q1 answer on record. | NFR3 |
| NFR2.6 | Every area says in words what empty or no data means (BR5.1): the key says an empty off-list means all four signals are fine and that the tiles may show 0 when the verdict is UNKNOWN; the detail heading says a chart with no line has no data in the range; the quiet tile says its alarm needs several quiet days (`quiet_alarm_days`) before it goes off. | Terraform test checks each sentence is in its widget. | FR1.7, NFR2 |
| NFR2.7 | Each detail chart draws its alarm's metric with the alarm's threshold, by referring to the alarm (BR3.1). First staging deploy is the gate: if an annotation-only chart draws nothing, Code Generation falls back to the alarm's own metric and statistic plus a horizontal annotation built from the alarm's threshold variable, and records the change as a deviation. | Open the staging page; each of the four charts shows a line (or the no-data wording) and a threshold. | FR1.5 |
| NFR2.8 | The environment is named only where CloudWatch prints it: the dashboard is named `local.name` and no text widget carries an environment label (BR4.5). The alarm lists print alarm names as CloudWatch holds them, so staging's lists end in `-staging`. | Terraform test; the owner confirms at the first checkpoint that this meets FR1.8. | FR1.8 |

## After the deploy

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR6.11 | The pull request names what to watch after merge: the staging pipeline run green; the staging page at 1440 x 900 and 390 px (NFR2.1, NFR2.2); the verdict reading what the key says it should for staging's real state; no email sent by the composites. After the owner approves production, the production page reads HEALTHY while the bot runs on schedule. Window: 24 hours on the production verdict, with the rollback (revert and redeploy). | The pull request body; the owner's check. | NFR6 |
| NFR6.12 | The verdict mirrors the alarms right now whatever range the page shows (FR1.1): a composite changes state within CloudWatch's normal alarm evaluation delay of an alarm changing. The page adds no refresh interval or custom auto-refresh. | None beyond reading the page after a known alarm change. | FR1.1 |

## Service-level view

No new SLO. The page reports on the bot's existing alarms, which keep their thresholds (FR5.3). Alerting is
unchanged: the composites send nothing, and the existing five alarms keep emailing the alerts topic.

## Not applicable

Logging standards (U1 and U2), distributed tracing (the bot is one Lambda) and new alert thresholds (U5).
