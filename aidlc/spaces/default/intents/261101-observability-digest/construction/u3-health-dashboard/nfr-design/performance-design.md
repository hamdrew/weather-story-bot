# Performance Design: u3-health-dashboard

## Sources

- `nfr-requirements/performance-requirements.md` (NFR2.1 to NFR2.5, NFR1.3) and `observability-requirements.md` (NFR2.6, NFR2.7)
- `functional-design/functional-spec.md` (layout table) and `rules.md` (BR2.1, BR4.1 to BR4.3, BR5.1)
- `infra/monitoring.tf`: the four health alarms' metrics, statistics, periods and thresholds
- Terraform AWS provider 6.71.0 documentation: `aws_cloudwatch_dashboard` takes `dashboard_name` and `dashboard_body` only

The page is a console feature used by hand, so performance is how fast the owner reads it and what a view costs.
There is nothing to cache or pool. The design is the shape of the dashboard body and how it is built.

## Design decisions

| ID | Decision | Satisfies |
|----|----------|-----------|
| D-P1 | **One ordered list of signals drives every tile and chart.** `local.health_signals` holds, in tile order (missed-runs, errors, quiet, repost-loop), the alarm resource, the tile title and a `fill` flag. A tile and its chart are built from the same entry, so they cannot disagree and cannot drift from the alarm: every metric field is read from the alarm resource's own attributes (`namespace`, `metric_name`, `dimensions`, `statistic`, `period`, `threshold`), never typed again. | NFR2.5, NFR2.10 (as amended in D-P4), BR2.1 |
| D-P2 | **Tile = single value with a sparkline, over metric math `FILL(m1, 0)`.** `m1` is the alarm's metric (hidden, the alarm's statistic and period); the visible series is the filled expression, so a period with no events reads 0. `fill = false` on a signal switches that one tile to the plain metric (the fallback if the first staging page shows "no data" under FILL, for example for a log-filter metric with no datapoints at all). The tile's alarm state is never inferred from its number: the unfiltered alarm list under the tiles carries it (BR2.2). | NFR2.4, NFR2.9 |
| D-P3 | **Layout is computed, not typed.** The body is built from an ordered list of rows; each row has a height and a list of widgets with widths. A widget's `x` is the sum of the widths before it in its row; its `y` is the sum of the heights of the rows above. A row whose widths exceed 24 fails a Terraform validation. U5 inserts its totals row and its area by adding rows, and everything below moves down. | NFR2.1, NFR2.2, NFR6.7, BR4.1 |
| D-P4 | **Detail charts list their own metric, built from the alarm's attributes, with a horizontal threshold annotation from the alarm's `threshold`.** This replaces the frozen rule's alarm-annotation-only chart (BR3.1, NFR2.10), which no documentation checked here shows drawing a line. The drift the annotation form avoided is avoided here by reference, not by retyping: if the alarm's period or threshold changes, the chart changes with it. The fill side comes from the alarm's comparison operator (`Less...` fills below, `Greater...` above). A deviation from the functional design, recorded in the diary; the Terraform test checks the chart's metric equals the alarm's. | NFR2.7, NFR2.10, FR1.5 |
| D-P5 | **Verdict first on the first screen.** The verdict area is title-key 5 + verdict 3 + signals-off 3 = 11 grid units, at most. The key text is written so its first lines are the three-step reading order, and the empty and no-data sentences (BR5.1) follow. At 390 px the key widget keeps its height and scrolls, so the reading order is what shows first, and the verdict sits below a fixed 5-unit widget. | NFR2.1, NFR2.2, NFR2.6 |
| D-P6 | **No Logs Insights widget in this unit.** A page view reads 8 metrics, 4 alarm states in two lists and 2 composite states, so it scans no log bytes and adds no per-view charge. | NFR1.3 |
| D-P7 | **The body opens on the last 7 days with `periodOverride` set to inherit** (`start = "-P7D"`), so each chart keeps its alarm's period and the tiles show the last period. | NFR2.5, BR4.3 |

## Tile and chart shape (interface level)

```hcl
# Tile for one signal; a chart is the same metric list without the expression.
metrics = s.fill ? [
  [{ expression = "FILL(m1, 0)", label = s.tile, id = "e1" }],
  concat(local.alarm_metric[s.key], [{ id = "m1", visible = false }]),
] : [local.alarm_metric[s.key]]
# local.alarm_metric[k] = [namespace, metric_name, <dimension pairs>, { stat, period }] read from the alarm.
```

## Budgets

| Item | Budget |
|------|--------|
| Widgets | 13 (BR4.1), at most 30 so U5's area fits |
| Metrics on the page | 8, at most 50 (free allowance, NFR1.4) |
| Verdict area height | at most 11 grid units; U5's totals row at most 3 |
| Dashboard body | far under CloudWatch's size limit; checked as the encoded length in the Terraform test |

## Not applicable

Caching, connection pooling, async processing and pagination: nothing is served or computed by this unit.
