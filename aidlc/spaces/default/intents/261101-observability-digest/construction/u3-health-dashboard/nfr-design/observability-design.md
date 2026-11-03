# Observability Design: u3-health-dashboard

## Sources

- `nfr-requirements/observability-requirements.md` (NFR3.1 to NFR3.3, NFR2.6 to NFR2.8, NFR6.11, NFR6.12) and `performance-requirements.md`
- `functional-design/functional-spec.md` and `rules.md` (BR1.4, BR2.2, BR3.1, BR4.4, BR4.5, BR5.1)
- `aidlc/spaces/default/memory/project.md`: report times to the owner in America/Chicago
- `aidlc/spaces/default/memory/team.md`: each pull request names what to watch after merge, with a window and the rollback

This unit is the observability: the verdict, the tiles and the charts. The design below is how the page reads and
how its first deploy is proved. It adds no metric, log, trace or alarm other than the two verdict composites.

## Design decisions

| ID | Decision | Satisfies |
|----|----------|-----------|
| D-O1 | **Time zone: none set.** No widget carries `timezone`; the page follows the browser, and the detail heading tells the owner to set the console's time zone control to Local (Chicago in Chicago, daylight saving included). The heading says "Local", not "Chicago", so it stays true while travelling. No text widget states a clock time or a date. Tests scan the decoded body for `timezone` and for date or time patterns. | NFR3.1, NFR3.2, NFR3.3 |
| D-O2 | **The key text is written in this order:** (1) the three-step reading order (unknown alarm not OK means UNKNOWN; else not-healthy alarm not OK means NOT HEALTHY; else HEALTHY); (2) what an empty "signals off" list means; (3) that tiles may show 0 when the verdict is UNKNOWN; (4) that the quiet signal needs `quiet_alarm_days` quiet days before it goes off. The first block is short enough to read in the 5-unit widget on a phone; the rest scrolls. A test checks each sentence is in the widget and that the reading order comes first. | NFR2.6, NFR2.2, BR1.4, BR5.1 |
| D-O3 | **Detail heading** says a chart with no line has no data in the range, and carries the time zone instruction. | NFR2.6, NFR3.1 |
| D-O4 | **No environment label.** The dashboard is named `local.name`; no text widget has an environment word. The alarm lists print alarm names as CloudWatch holds them, which end in `-staging` in staging; the owner confirms at the first checkpoint that this meets FR1.8. A test scans the text widgets for the environment value. | NFR2.8 |
| D-O5 | **Chart form (amended).** Each chart lists its alarm's metric, built from the alarm's attributes, with a horizontal threshold annotation from the alarm's `threshold`, in place of the alarm-annotation-only form (see `performance-design.md` D-P4). The first staging page is still checked, but a missing line there is now a plain bug and not an open question about a mechanism. | NFR2.7 |
| D-O6 | **Staging proof, in order.** (1) The staging pipeline run is green (`gh run view <id> --json jobs`, not `gh run watch`). (2) The page opens at 1440 x 900 and at 390 px with the verdict on the first screen. (3) The verdict matches staging's real state, and the key explains it (a paused staging reads UNKNOWN). (4) The four tiles show numbers or 0 and each chart shows a line or its no-data wording with a threshold. (5) The composites sent no email. Optional, by the owner under the MFA profile: set staging's `errors` alarm to ALARM with `aws cloudwatch set-alarm-state` and read the composite change; that alarm emails the owner, as it does today, and returns to its real state at its next evaluation. | NFR6.11, NFR6.12, NFR2.1, NFR2.2 |
| D-O7 | **Production watch, 24 hours** after the owner approves: the production page reads HEALTHY while the schedule runs; the run records' failed counts are unchanged; no new email. Rollback: revert the commit and let the pipeline redeploy. | NFR6.11 |
| D-O8 | **The verdict follows the alarms right now**, whatever range the page shows; no refresh interval is set. A composite changes state when CloudWatch next evaluates it after an alarm changes. | NFR6.12 |

## Alerting and service levels

No new threshold and no new SLO. The composites send nothing; the five existing alarms keep their settings and keep
emailing the alerts topic. U5 adds the warning and error-log alarms and moves the error-log alarm into the
not-healthy rule through the list in `scalability-design.md` D-C1.

## Not applicable

Structured logging (U1, U2), tracing (one Lambda) and correlation ids.
