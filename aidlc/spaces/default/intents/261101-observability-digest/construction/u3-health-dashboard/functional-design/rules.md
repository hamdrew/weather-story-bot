# Rules: u3-health-dashboard

## Sources

- `requirements.md`: FR1.1, FR1.2, FR1.3, FR1.5 to FR1.8, FR5.3, NFR1 to NFR3 [FR1.1]
- `decisions.md`: ADR-004 (monitoring stays in `infra/`), ADR-006 (the verdict is two composite alarms)
- `infra/monitoring.tf`: the four alarms and their thresholds, which this unit reads and does not change
- `functional-design-questions.md`: Q1 A (browser time zone), Q2 A (an idle environment reads UNKNOWN)
- CloudWatch documentation: composite alarm rules (`ALARM(...)`, `INSUFFICIENT_DATA(...)`, `OR`); the alarm-status widget (`alarms`, `states`, `sortBy`); the metric widget (`singleValue`, `sparkline`, `annotations.alarms`, `timezone` as a fixed UTC offset)

```yaml
rules:
  - id: BR1.1
    statement: The verdict is two composite alarms per environment, named local.name-unknown and local.name-not-healthy, and neither has an action.
    category: constraint
    applies_to: VerdictAlarm
    trigger: the composite alarms are created or changed
    logic: IF a VerdictAlarm is defined THEN it has no alarm, OK or insufficient-data action, so the verdict sends no email and the alerts topic is untouched.
    violation: the Terraform test fails on a composite with an action.
    source: FR1.1, ADR-006
  - id: BR1.2
    statement: The unknown alarm is in ALARM when the bot should have run and gave no data.
    category: calculation
    applies_to: VerdictAlarm unknown
    trigger: any of the four health alarms changes state
    logic: IF the missed-runs alarm is in ALARM, OR any of missed-runs, errors, quiet or repost-loop is in INSUFFICIENT_DATA, THEN the unknown alarm is in ALARM; otherwise it is OK.
    violation: the Terraform test fails when the rule names a different set of alarms or states.
    source: FR1.1
  - id: BR1.3
    statement: The not-healthy alarm is in ALARM when a signal other than missed-runs is off.
    category: calculation
    applies_to: VerdictAlarm not-healthy
    trigger: any of errors, quiet or repost-loop changes state
    logic: IF the errors, quiet or repost-loop alarm is in ALARM THEN the not-healthy alarm is in ALARM; otherwise it is OK. missed-runs is not in this rule: its ALARM reads UNKNOWN (BR1.2).
    violation: the Terraform test fails when the rule names a different set of alarms.
    source: FR1.1, FR1.3
  - id: BR1.4
    statement: The verdict is read from the two alarm states with one fixed order, which the dashboard prints in words.
    category: policy
    applies_to: Dashboard title-key text, VerdictAlarm
    trigger: someone reads the verdict
    logic: IF the unknown alarm is not OK THEN the verdict is UNKNOWN, whatever the other alarm says; ELSE IF the not-healthy alarm is not OK THEN it is NOT HEALTHY; ELSE it is HEALTHY. Warnings never change it. A dashboard cannot compute one word from alarm states (ADR-006), so the page shows the two alarm states and this key.
    violation: the key text and these rules disagree; the Terraform test compares the key text with the rule order.
    source: FR1.1, ADR-006
  - id: BR1.5
    statement: Warnings and the nws-ambiguous alarm do not change the verdict in this unit.
    category: constraint
    applies_to: VerdictAlarm
    trigger: a warning is logged or the nws-ambiguous alarm goes into ALARM
    logic: IF only warnings, or only the nws-ambiguous alarm, are active THEN the verdict stays HEALTHY. After U5, an ambiguous listing is logged at ERROR and the error-log alarm carries it into NOT HEALTHY.
    violation: the Terraform test fails when a rule names the nws-ambiguous alarm.
    source: FR1.1, FR4.2
  - id: BR1.6
    statement: Each rule is built from the alarm resources, never from typed names, and from one list per rule that U5 can extend.
    category: constraint
    applies_to: VerdictAlarm rules, Widget alarms
    trigger: an alarm is renamed, added or removed
    logic: IF a rule or a widget refers to an alarm THEN it refers to the alarm resource's name or ARN. The not-healthy rule is built from one local list, so U5 adds its error-log alarm by appending to that list and changing nothing else.
    violation: the Terraform test fails when a rule term or a widget alarm is not an existing alarm.
    source: FR1.1, FR5.1, FR5.3
  - id: BR1.7
    statement: This unit changes none of the five existing alarms, and the verdict alarms stay out of alarm_names.
    category: constraint
    applies_to: monitoring.tf alarms, alarm_names
    trigger: this unit is built
    logic: IF this unit is built THEN the thresholds, periods, evaluation periods, missing-data settings and actions of errors, missed-runs, quiet, repost-loop and nws-ambiguous are unchanged, and alarm_names does not list the verdict alarms, because start and pause toggle actions and the verdict alarms have none.
    violation: the plan shows a change to an existing alarm, or the Terraform test finds a verdict alarm in alarm_names.
    source: FR5.3, FR1.3
  - id: BR2.1
    statement: There is one tile per health signal, in a fixed order, showing the signal's value now and its trend.
    category: constraint
    applies_to: Widget tile-*
    trigger: the dashboard is rendered
    logic: IF the dashboard is built THEN it has four single-value tiles in the order missed-runs, errors, quiet, repost-loop; each shows the sum of its metric over the alarm's own period with a sparkline, and shows 0 rather than a blank when nothing was counted (a count with no events is zero, and the verdict carries any doubt about whether the bot ran).
    violation: a tile is missing, out of order, or draws a different metric from its alarm; the Terraform test fails.
    source: FR1.3
  - id: BR2.2
    statement: The signals that are off are listed in the verdict area, and the state of every signal sits beside its tile.
    category: constraint
    applies_to: Widget signals-off, signals-state
    trigger: a health alarm changes state
    logic: IF a health alarm is in ALARM or INSUFFICIENT_DATA THEN it appears in the signals-off list, an alarm-status widget over the four health alarms filtered to those two states. A second alarm-status widget over the same four, unfiltered and with ALARM first, sits directly under the tiles so each signal's state is read next to its value.
    violation: the filter is missing or lists a different set; the Terraform test fails.
    source: FR1.2, FR1.3
  - id: BR2.3
    statement: A tile's title names the signal and the unit in words.
    category: validation
    applies_to: Widget tile-*
    trigger: a tile is defined
    logic: IF a tile is defined THEN its title reads like "Runs on schedule: runs per hour", "No failed runs: failed runs per 15 minutes", "A story posted recently: posts per day" and "No repost loop: posts per 3 hours".
    violation: a tile title is empty or has no unit.
    source: FR1.3
  - id: BR3.1
    statement: Each detail chart draws its alarm's own metric with the alarm's threshold.
    category: constraint
    applies_to: Widget chart-*
    trigger: the dashboard is rendered
    logic: IF the dashboard is built THEN each of the four charts is a time-series widget that refers to its health alarm (an alarm annotation, with no separate metric list), so the metric, statistic, period and threshold are the alarm's own and cannot drift from it, and the chart covers the dashboard's time range.
    violation: a chart lists its own metrics instead of the alarm, or refers to a different alarm; the Terraform test fails.
    source: FR1.5, FR5.2
  - id: BR4.1
    statement: The widgets sit on the 24-column grid in one fixed top-to-bottom order that also reads in one column on a phone.
    category: constraint
    applies_to: Dashboard widgets
    trigger: the dashboard is built
    logic: IF the dashboard is built THEN the order by y, then x, is title-key, verdict, signals-off, the four tiles, signals-state, detail-heading, then the four charts two by two; every widget has x + width <= 24; and the four tiles are the same height and share one row.
    violation: a widget overflows the grid or the order differs; the Terraform test fails.
    source: FR1.6
  - id: BR4.2
    statement: The verdict area is short enough that the verdict is on the first screen at both sizes, with room kept for U5's totals.
    category: constraint
    applies_to: Widget title-key, verdict, signals-off
    trigger: the layout is set or U5 adds the totals
    logic: IF the verdict area is built THEN title-key, verdict and signals-off together are at most 11 grid units tall, which leaves room for U5's totals row of up to 3 units above the tiles, so the verdict and the totals fit in the first screen at 1440 x 900 and at 390 px wide.
    violation: NFR2 is checked by opening the deployed staging dashboard at both sizes; a verdict below the fold fails it.
    source: NFR2, FR1.6
  - id: BR4.3
    statement: The dashboard opens on the last 7 days and every widget keeps its own period.
    category: policy
    applies_to: Dashboard default_range, period_override
    trigger: the dashboard is opened
    logic: IF the dashboard is built THEN its default range is the last 7 days (-P7D), which is within the 30-day log retention, and its period override is inherit so a chart uses its alarm's period.
    violation: the Terraform test fails on a different range or override.
    source: FR1.4, FR1.5
  - id: BR4.4
    statement: No widget sets a time zone; times follow the browser's time zone.
    category: policy
    applies_to: Widget timezone
    trigger: a widget is defined
    logic: IF a widget is defined THEN it has no timezone property, because the property takes only a fixed UTC offset and cannot follow daylight saving time. The detail heading tells the owner to set the dashboard's time zone control to Local, which shows Chicago time in Chicago all year.
    violation: the Terraform test fails when any widget carries a timezone.
    source: NFR3
  - id: BR4.5
    statement: The dashboard is named local.name and no text on it names the environment.
    category: constraint
    applies_to: Dashboard name, Widget text
    trigger: the dashboard is built
    logic: IF the dashboard is built THEN its name is local.name (weather-story-bot or weather-story-bot-staging) and no text widget contains an environment label. The alarm-status widgets print the alarm names as CloudWatch holds them, which carry the -staging suffix in staging; the page adds nothing.
    violation: the Terraform test finds an environment word in a text widget.
    source: FR1.8
  - id: BR5.1
    statement: Every area says in words what empty or no data means.
    category: policy
    applies_to: Widget title-key, tile-*, detail-heading
    trigger: an area has nothing to show
    logic: IF the signals-off list is empty THEN the key says it is empty when all four signals are fine; IF the verdict is UNKNOWN THEN the key says the tiles below may show 0 because the bot did not report; the detail heading says a chart with no line has no data in the range.
    violation: the key or heading lacks the sentence; the Terraform test checks for it.
    source: FR1.7
  - id: BR6.1
    statement: This unit adds two composite alarms and one dashboard per environment, and nothing else that is billed.
    category: constraint
    applies_to: Terraform resources of this unit
    trigger: the unit is built
    logic: IF the unit is built THEN it creates two composite alarms and one dashboard in each environment and no metric filter, standard alarm, log query or custom metric. The cost is about $0.50 per composite alarm per month, about $2 for both environments together, and the dashboards fall inside the free allowance (ADR-006); NFR Requirements confirms both against the price list.
    violation: the plan shows any other billed resource.
    source: NFR1
  - id: BR6.2
    statement: The resources live in a new file beside monitoring.tf, which this unit does not edit.
    category: constraint
    applies_to: infra/
    trigger: the unit is built
    logic: IF the unit is built THEN the composite alarms and the dashboard are in a new file (infra/dashboard.tf), and monitoring.tf is unchanged, so U4 and U5 edit it without a conflict.
    violation: the diff shows an edit to monitoring.tf.
    source: ADR-004
```

| Rule | In one line |
|------|-------------|
| BR1.1 to BR1.7 | Two action-free composite alarms; UNKNOWN is missed-runs in ALARM or any signal without data; NOT HEALTHY is errors, quiet or repost-loop in ALARM; the page prints the reading order; built from the alarm resources; existing alarms untouched |
| BR2.1 to BR2.3 | Four tiles with a trend and zero instead of blank; a filtered list of what is off and an unfiltered list of states; titles with units |
| BR3.1 | Four charts drawn from the alarms themselves |
| BR4.1 to BR4.5 | Fixed order on a 24-column grid; short verdict area; 7-day range; no time zone set; named local.name with no environment label |
| BR5.1 | Words for every empty or no-data case |
| BR6.1, BR6.2 | Only two composites and a dashboard per environment, in a new file |
