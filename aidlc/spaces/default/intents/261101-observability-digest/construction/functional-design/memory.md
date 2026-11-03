<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] FR1.8 read as "the page adds no environment label"; the alarm-status widget prints alarm names, which end in -staging in staging. Recorded in the spec's edge cases.
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] FR1.3's "alarm state on each tile" is met by an unfiltered alarm list directly under the tiles, because a single-value widget cannot show alarm state and an alarm annotation cannot be combined with a metric list.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] No frontend-components.md: the dashboard is Terraform JSON, not a UI component tree; the widget table in functional-spec.md covers its layout.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] Detail charts use an alarm annotation rather than their own metric list, so the metric and threshold cannot drift from the alarm (FR5.2 by construction); the cost is that the chart takes the alarm's period (a day for quiet).
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] Chart time zone: the widget timezone property is a fixed UTC offset and cannot follow daylight saving, so the owner chose the browser's local time (Q1 A) over -0600.

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] Grid unit height (about 30 px), the phone single-column order and the empty states of alarm lists are assumptions (A1 to A3) that only the deployed staging page can settle.
- 2026-11-02T17:05:00Z — [unit u3-health-dashboard] Advisory review READY, with points to settle in the next stages (the design is frozen after the verdict): (1) BR2.1 "0 not blank" needs a named mechanism, metric math FILL(m1, 0), or the claim is dropped; (2) BR3.1 annotation-only charts are unverified, so decide a fallback (own metrics plus a horizontal threshold annotation from the alarm's variables) and make the first staging deploy the gate; (3) the example "errors has no data reads UNKNOWN" is wrong, since errors and repost-loop treat missing data as notBreaching and missed-runs and quiet as breaching: UNKNOWN in practice is missed-runs in ALARM and the INSUFFICIENT_DATA terms are a safety net; (4) widgets take alarm ARNs, composite rules take names, and the sortBy value for "ALARM first" is stateUpdatedTimestamp; (5) the key text is long for a 5-unit widget at 390 px; (6) y values should be computed from an ordered list so U5 can insert an area, and U5 edits dashboard.tf; (7) traceability should mark FR1.1, FR1.2, FR1.6 and FR1.7 as shared with U5; (8) the -staging suffix in alarm lists needs the owner's word for FR1.8, and the quiet tile should say the alarm needs several quiet days; (9) assumptions to add: the Local time zone control, periodOverride inherit, the free dashboard allowance.
- 2026-11-02T17:01:05Z — [unit u3-health-dashboard] Composite alarm price ($0.50) and the free-dashboard allowance come from ADR-006 and were not re-checked here; NFR Requirements should confirm them.
