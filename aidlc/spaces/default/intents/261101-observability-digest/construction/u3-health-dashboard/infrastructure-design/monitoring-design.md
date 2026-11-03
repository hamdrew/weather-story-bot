# Monitoring Design: u3-health-dashboard

## Sources

- `nfr-design/observability-design.md` (D-O1 to D-O8), `performance-design.md` (D-P1 to D-P7), `reliability-design.md`
- `functional-design/functional-spec.md` and `rules.md` (BR1.2 to BR1.4, BR2.1 to BR2.3, BR4.1, BR5.1)
- `infra/monitoring.tf`: thresholds, periods and missing-data settings of the four health alarms

This unit adds no metric, filter or standard alarm. Its monitoring is the page itself and the two verdict composites.

## Metrics & KPIs

Every tile and chart reads its alarm's own metric; thresholds are the alarm's, read from the resource.

| Metric | Source | Threshold | Why it matters |
|--------|--------|-----------|----------------|
| Lambda `Invocations`, sum per 3,600 s (tile "Runs on schedule") | `missed_runs` alarm | ALARM below 1 per period; missing data counts as breaching | The bot did not run when it should have: the cause of UNKNOWN |
| Lambda `Errors`, sum per 900 s (tile "No failed runs") | `errors` alarm | ALARM at 1 or more in 2 of 2 periods; missing data not breaching | A run failed twice in a row: NOT HEALTHY |
| `StoriesPosted`, sum per 86,400 s (tile "A story posted recently") | `quiet` alarm | ALARM below 1 for `quiet_alarm_days` periods; missing data breaching | Nothing posted for several days: NOT HEALTHY |
| `StoriesPosted`, sum per 10,800 s (tile "No repost loop") | `repost_loop` alarm | ALARM above `repost_alarm_max_posts` in one period; missing data not breaching | A repost storm: NOT HEALTHY |

## Alerts

| Alert | Condition | Severity | Routes to |
|-------|-----------|----------|-----------|
| `<name>-unknown` (composite) | `missed-runs` in ALARM, or any of the four health alarms in INSUFFICIENT_DATA | Display only | Nothing: no action (BR1.1) |
| `<name>-not-healthy` (composite) | `errors`, `quiet` or `repost-loop` in ALARM | Display only | Nothing: no action (BR1.1) |
| Five existing alarms | Unchanged (FR5.3) | As today | The alerts topic, as today |

Reading order printed on the page (BR1.4): the unknown alarm not OK means UNKNOWN; else the not-healthy alarm not OK means NOT HEALTHY; else HEALTHY. Warnings and the `nws-ambiguous` alarm do not change the verdict until U5 (BR1.5).

## SLIs / SLOs

| SLI | SLO target | Measurement window |
|-----|------------|--------------------|
| None added | None added | n/a: the page reports the existing alarms' conditions and sets no new objective |

## Logs & Tracing

No log group, metric filter, log query or trace is added. No Logs Insights widget in this unit (U5 adds them with their cost). The page reads 8 metrics and the state of 4 health alarms and 2 composites.

## Dashboard specification

Rows top to bottom; x and y are computed from row heights and widget widths (D-P3), not typed. Height is in grid units; the grid is 24 columns wide.

| Row | Height | Widgets (width) | Content |
|-----|--------|-----------------|---------|
| 1 | 5 | key text (24) | Reading order first, then the empty-list sentence, the zero-when-UNKNOWN sentence and the quiet-signal sentence (D-O2) |
| 2 | 3 | verdict alarm list (24) | The two composites, unfiltered, ALARM first (`sortBy` `stateUpdatedTimestamp`) |
| 3 | 3 | signals-off alarm list (24) | The four health alarms, filtered to ALARM and INSUFFICIENT_DATA |
| (U5) | up to 3 | totals row | Inserted by U5 above the tiles |
| 4 | 4 | four tiles (6 each) | Single value with sparkline, `FILL(m1, 0)`, titles with units (BR2.3) |
| 5 | 3 | signals-state alarm list (24) | The four health alarms, unfiltered, ALARM first |
| 6 | 3 | detail heading (24) | Chart with no line = no data in the range; set the time zone control to Local |
| 7 | 6 | two charts (12 each) | missed-runs and errors, each with its threshold line |
| 8 | 6 | two charts (12 each) | quiet and repost-loop, each with its threshold line |

Verdict area = rows 1 to 3 = 11 grid units (D-P5). The dashboard is named `local.name`; no text names the environment (D-O4); no widget sets a time zone (D-O1).

## First staging checklist (NFR6.11, NFR6.12)

| # | Check | Pass |
|---|-------|------|
| 1 | Staging pipeline run read with `gh run view <id> --json jobs` | Green; production job waiting for approval or skipped as no-change |
| 2 | Page at 1440 x 900 and 390 px wide | Verdict rows on the first screen; reading order visible |
| 3 | Verdict against staging's real state | A paused staging reads UNKNOWN and the key explains it |
| 4 | Tiles | A number or 0 under each title |
| 5 | Charts | A line or the no-data wording, plus a threshold line |
| 6 | Email | None from the composites |
| 7 | (optional, owner, MFA profile) | `aws cloudwatch set-alarm-state` on staging's `errors` alarm, read the composite change; that alarm emails the owner as it does today |
