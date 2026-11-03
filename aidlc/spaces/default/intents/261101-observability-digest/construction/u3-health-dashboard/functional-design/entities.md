# Entities: u3-health-dashboard

## Sources

- `inception/units-generation/unit-of-work.md` (U3) and `inception/requirements-analysis/requirements.md` (FR1.1, FR1.2, FR1.3, FR1.5 to FR1.8) [FR1.1]
- `inception/domain-design/components.md` (Monitoring: VerdictAlarm, Dashboard; Signal and Alarm as they stand) and `decisions.md` (ADR-004, ADR-006) [FR1.1]
- `infra/monitoring.tf`: the four alarms this unit reads, left unchanged [FR1.3]
- `functional-design-questions.md` (Q1 A, Q2 A)

This unit builds no stored data. Its entities are the Terraform-managed CloudWatch objects: the health signals it
reads (they already exist), the two verdict alarms and the dashboard with its widgets.

```yaml
entities:
  - name: HealthSignal
    description: One of the four conditions the verdict is made of. It already exists as an alarm in infra/monitoring.tf; this unit only reads it.
    attributes:
      - { name: id, type: enum, required: true, unique: true, allowed: [missed-runs, errors, quiet, repost-loop] }
      - { name: label, type: string, required: true, constraints: "the words on the tile: Runs on schedule, No failed runs, A story posted recently, No repost loop (FR1.3)" }
      - { name: alarm, type: "Alarm name", required: true, unique: true, constraints: "the existing alarm local.name-<id>; this unit never changes its threshold, period or actions (FR5.3)" }
      - { name: metric_namespace, type: string, required: true, constraints: "AWS/Lambda for missed-runs and errors; local.metric_namespace for quiet and repost-loop" }
      - { name: metric_name, type: string, required: true, constraints: "Invocations, Errors, StoriesPosted, StoriesPosted" }
      - { name: tile_stat, type: string, required: true, default: Sum }
      - { name: tile_period_seconds, type: integer, required: true, constraints: "3600 for missed-runs, 900 for errors, 86400 for quiet, 10800 for repost-loop: each the alarm's own period" }
      - { name: off_when, type: string, required: true, constraints: "the alarm is in ALARM (FR1.3)" }
      - { name: unknown_when_no_data, type: boolean, required: true, default: true, constraints: "an INSUFFICIENT_DATA state of the alarm makes the verdict UNKNOWN (FR1.1)" }
    constraints:
      - "Exactly four HealthSignals; nws-ambiguous is not one (BR1.5)"
      - "missed-runs is the only signal that is off in ALARM and reads UNKNOWN rather than NOT HEALTHY (BR1.2, BR1.3)"
    relationships:
      - { to: VerdictAlarm, cardinality: "one HealthSignal to one or two VerdictAlarms", direction: "VerdictAlarm.rule -> HealthSignal" }
      - { to: Widget, cardinality: "one HealthSignal to one tile, one chart and one row in each alarm list", direction: "Widget.signal -> HealthSignal" }

  - name: VerdictAlarm
    description: A composite alarm with no actions whose state, read with its sibling, is the verdict (ADR-006).
    attributes:
      - { name: kind, type: enum, required: true, unique: true, allowed: [unknown, not-healthy] }
      - { name: alarm_name, type: string, required: true, unique: true, constraints: "local.name-unknown or local.name-not-healthy" }
      - { name: rule_terms, type: "list of {state, signal}", required: true, constraints: "state is ALARM or INSUFFICIENT_DATA; the rule is the terms joined by OR (BR1.2, BR1.3)" }
      - { name: actions, type: "list of string", required: true, default: "[]", constraints: "always empty: no email, no SNS (BR1.1)" }
      - { name: in_alarm_names, type: boolean, required: true, default: false, constraints: "false: start and pause toggle actions, and it has none (BR1.7)" }
    constraints:
      - "Exactly two VerdictAlarms per environment"
      - "No VerdictAlarm refers to another VerdictAlarm, so no cycle is possible"
    relationships:
      - { to: HealthSignal, cardinality: "one VerdictAlarm to one or more HealthSignals", direction: "VerdictAlarm -> HealthSignal" }

  - name: Widget
    description: One box on the dashboard grid.
    attributes:
      - { name: id, type: string, required: true, unique: true, allowed: [title-key, verdict, signals-off, tile-missed-runs, tile-errors, tile-quiet, tile-repost-loop, signals-state, detail-heading, chart-missed-runs, chart-errors, chart-quiet, chart-repost-loop] }
      - { name: kind, type: enum, required: true, allowed: [text, alarm-status, single-value, alarm-chart] }
      - { name: x, type: integer, required: true, min: 0, max: 23 }
      - { name: y, type: integer, required: true, min: 0 }
      - { name: width, type: integer, required: true, min: 1, max: 24, constraints: "x + width <= 24" }
      - { name: height, type: integer, required: true, min: 1 }
      - { name: signal, type: "HealthSignal.id", required: false, constraints: "set on the tiles and charts; absent on text and alarm lists" }
      - { name: alarms, type: "list of alarm names", required: false, constraints: "set on alarm-status and alarm-chart widgets, built from the alarm resources (BR1.6)" }
      - { name: states_filter, type: "list of enum", required: false, allowed: [ALARM, INSUFFICIENT_DATA, OK], constraints: "set only on signals-off: [ALARM, INSUFFICIENT_DATA] (BR2.2)" }
      - { name: timezone, type: string, required: true, default: "absent", constraints: "never set; times follow the browser's zone (BR4.4)" }
    constraints:
      - "Exactly 13 widgets: 1 text key, 1 verdict list, 1 off list, 4 tiles, 1 state list, 1 detail heading, 4 charts"
      - "Reading order is y, then x; this is also the single-column order at phone width (BR4.1)"
    relationships:
      - { to: Dashboard, cardinality: "many Widgets to one Dashboard", direction: "Widget -> Dashboard" }

  - name: Dashboard
    description: The one CloudWatch dashboard per environment.
    attributes:
      - { name: name, type: string, required: true, unique: true, constraints: "local.name, so staging's is weather-story-bot-staging and production's weather-story-bot (BR4.5)" }
      - { name: default_range, type: string, required: true, default: "-P7D", constraints: "7 days, within the 30-day log retention (BR4.3)" }
      - { name: period_override, type: enum, required: true, default: inherit, allowed: [inherit, auto] }
      - { name: widgets, type: "ordered list of Widget", required: true }
    constraints:
      - "One Dashboard per environment, with no environment label in any text on it (BR4.5)"
      - "Well under CloudWatch's 500-widget and per-dashboard metric limits"
```

Four entities. HealthSignal is the existing alarm seen as a verdict input, VerdictAlarm is the new composite, Widget
is one box on the page and Dashboard holds the 13 widgets in order. U5 adds a fifth term to the not-healthy rule
and new widgets in the verdict area; it adds no entity this unit has to leave room for beyond the layout budget
in BR4.2.
