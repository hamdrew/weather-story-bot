# Performance Requirements: u3-health-dashboard

## Sources

- `functional-design/functional-spec.md` (layout table) and `rules.md` (BR2.1, BR4.1 to BR4.4, BR5.1) [FR1.6]
- `inception/requirements-analysis/requirements.md`: NFR1, NFR2, NFR3 [FR1.6]
- AWS pricing and CloudWatch documentation checked for the cost lines (see `tech-stack-decisions.md`)

The dashboard is a page the owner opens by hand, a few times a week; nothing runs on a schedule and nothing is
served at volume. "Performance" here is how quickly the owner can read the answer (NFR2) and what a page view
costs (NFR1). There is no throughput or latency target for the bot: the unit does not touch the Lambda.

## Requirements

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR2.1 | The verdict is readable without scrolling in a 1440 x 900 browser window: title-key, verdict and signals-off together are at most 11 grid units tall (BR4.2), which leaves room for U5's totals row of 3. | Open the deployed staging dashboard at 1440 x 900; the verdict widget is fully on screen. | NFR2, FR1.6 |
| NFR2.2 | The same at 390 px wide, where CloudWatch reflows widgets into one column in order of y then x. The verdict (the two composite alarm states) must be on the first screen. The key text is the tallest widget in that column, so if it pushes the verdict down, NFR Design shortens the key or Code Generation moves the verdict above it, and records the change as a deviation from the frozen layout. | Open the deployed staging dashboard in a 390 px wide window or phone browser. | NFR2, FR1.6 |
| NFR2.3 | The owner can state the verdict from the page in under a minute, using only the page: the key says how to read the two alarm states. | The owner reads the staging page cold at the first checkpoint. | NFR2 |
| NFR2.4 | A tile shows 0, not a blank, when its metric has no events in the period (BR2.1). The mechanism is metric math `FILL(m1, 0)`; the tile's alarm state, not its number, carries any doubt about whether the bot ran. | Staging page: the `repost-loop` and `errors` tiles show 0 on a quiet day. | FR1.3, NFR2 |
| NFR2.5 | The page opens on the last 7 days and each chart keeps its alarm's own period (`periodOverride: inherit`), so a chart is never coarser or finer than the alarm it explains. | Terraform test on the dashboard body (BR4.3). | FR1.4, NFR2 |

## Resource limits

The page has 13 widgets and reads 8 metrics (four tiles and four charts, one metric each) plus the state of
4 health alarms and 2 composite alarms. That is far inside CloudWatch's per-dashboard limits (up to 50 metrics
for the free allowance, NFR1.3). No Logs Insights widget is in this unit, so a page view scans no log bytes.
U5 adds those queries and carries their cost and speed requirements.

## Not applicable

Response-time and throughput targets for the bot: the Lambda is unchanged (NFR5).
