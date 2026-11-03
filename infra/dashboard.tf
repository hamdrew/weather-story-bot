# The health dashboard and its verdict: two composite alarms that carry HEALTHY / NOT HEALTHY /
# UNKNOWN, and one dashboard that shows them above a tile and a chart for each health signal.
#
# Everything here is read from the alarms in monitoring.tf, which this file never edits: a rule term
# or a widget refers to an alarm resource, and a tile or chart takes its metric, statistic, period
# and threshold from the alarm's own attributes, so neither can drift from what the alarm does.
#
# Extension points for the observability digest's later units (change nothing else):
#   - local.not_healthy_alarms: append an alarm whose ALARM state means NOT HEALTHY.
#   - local.dashboard_rows: add a row (a height and widgets with widths); x and y are computed, so
#     every row below moves down.
#   - local.health_signals: a new signal joins both rules and gets a tile and a chart.

locals {
  # One entry per health signal, in tile order. "fill" turns the tile's value into 0 for a period
  # with no events (FILL(m1, 0)); set it false for one signal if a tile shows "no data" under it.
  health_signals = [
    { key = "missed-runs", alarm = aws_cloudwatch_metric_alarm.missed_runs, tile = "Runs on schedule: runs per hour", fill = true },
    { key = "errors", alarm = aws_cloudwatch_metric_alarm.errors, tile = "No failed runs: failed runs per 15 minutes", fill = true },
    { key = "quiet", alarm = aws_cloudwatch_metric_alarm.quiet, tile = "A story posted recently: posts per day", fill = true },
    { key = "repost-loop", alarm = aws_cloudwatch_metric_alarm.repost_loop, tile = "No repost loop: posts per 3 hours", fill = true },
  ]

  # Signals whose ALARM state means NOT HEALTHY. missed-runs is not here: its ALARM reads UNKNOWN.
  not_healthy_alarms = [
    aws_cloudwatch_metric_alarm.errors.alarm_name,
    aws_cloudwatch_metric_alarm.quiet.alarm_name,
    aws_cloudwatch_metric_alarm.repost_loop.alarm_name,
  ]

  # How one alarm is written in a composite rule. The documented form quotes the name; whether
  # CloudWatch accepts it is only known at the first apply, and if it is rejected the one-line
  # fallback is the unquoted form: "%s(%s)".
  rule_term_format = "%s(\"%s\")"

  unknown_terms = concat(
    [format(local.rule_term_format, "ALARM", aws_cloudwatch_metric_alarm.missed_runs.alarm_name)],
    [for s in local.health_signals : format(local.rule_term_format, "INSUFFICIENT_DATA", s.alarm.alarm_name)],
  )
  not_healthy_terms = [for n in local.not_healthy_alarms : format(local.rule_term_format, "ALARM", n)]

  unknown_rule     = join(" OR ", local.unknown_terms)
  not_healthy_rule = join(" OR ", local.not_healthy_terms)

  # The metric array of each alarm: namespace, metric name, then the dimension pairs. quiet and
  # repost-loop have no dimensions (the metric filters set none), so null reads as none.
  alarm_metric = { for s in local.health_signals : s.key => concat(
    [s.alarm.namespace, s.alarm.metric_name],
    flatten([for d, v in(s.alarm.dimensions == null ? {} : s.alarm.dimensions) : [d, v]]),
  ) }

  # A tile shows the signal's value now and its trend. Each metric row carries a use flag and the
  # options object is merged from for-expressions, so both settings of "fill" build the same shape:
  # a conditional between two differently shaped tuples would not type-check.
  tile_widgets = { for s in local.health_signals : s.key => {
    type = "metric"
    properties = {
      view      = "singleValue"
      sparkline = true
      region    = var.region
      title     = s.tile
      period    = s.alarm.period
      stat      = s.alarm.statistic
      metrics = [for r in [
        { use = s.fill, row = [{ expression = "FILL(m1, 0)", label = s.tile, id = "e1" }] },
        {
          use = true
          row = concat(local.alarm_metric[s.key], [merge(
            { stat = s.alarm.statistic, period = s.alarm.period },
            { for k, v in { id = "m1", visible = false } : k => v if s.fill },
          )])
        },
      ] : r.row if r.use]
    }
  } }

  # A chart is the alarm's own metric with a horizontal line at the alarm's threshold, shaded on the
  # side that breaches.
  chart_widgets = { for s in local.health_signals : s.key => {
    type = "metric"
    properties = {
      view    = "timeSeries"
      region  = var.region
      title   = s.tile
      metrics = [concat(local.alarm_metric[s.key], [{ stat = s.alarm.statistic, period = s.alarm.period }])]
      annotations = {
        horizontal = [{
          label = "Alarm threshold"
          value = s.alarm.threshold
          fill  = startswith(s.alarm.comparison_operator, "Less") ? "below" : "above"
        }]
      }
      yAxis = { left = { min = 0 } }
    }
  } }

  # The words on the page. CloudWatch cannot compute one word from alarm states, so the page shows
  # the two verdict alarms and this key. No date, clock time or environment name appears in any text.
  key_markdown = join("\n", [
    "# Weather Story Bot",
    "**Reading the verdict.** UNKNOWN if the `unknown` row is not OK (it wins). Otherwise NOT HEALTHY if the `not-healthy` row is not OK. Otherwise HEALTHY. Warnings never change it.",
    "",
    "**Signals that are off** is empty when all four signals are fine.",
    "",
    "If the verdict is UNKNOWN, the tiles below may show 0 because the bot did not report.",
    "",
    "A story posted recently goes off only after ${var.quiet_alarm_days} day(s) with no post.",
  ])

  detail_markdown = join("\n", [
    "## Detail",
    "Each chart is its alarm's own metric with the alarm's threshold. A chart with no line has no data in this range. Set the time zone control at the top of this page to Local to read times in Chicago time.",
  ])

  # Alarm lists. The verdict list is unfiltered. "Signals that are off" shows only what is not fine.
  # Sorted by the time of the last state change, so a recent change is first.
  verdict_widget = {
    type = "alarm"
    properties = {
      title  = "Verdict alarms"
      alarms = [aws_cloudwatch_composite_alarm.unknown.arn, aws_cloudwatch_composite_alarm.not_healthy.arn]
      sortBy = "stateUpdatedTimestamp"
    }
  }
  signals_off_widget = {
    type = "alarm"
    properties = {
      title  = "Signals that are off"
      alarms = [for s in local.health_signals : s.alarm.arn]
      states = ["ALARM", "INSUFFICIENT_DATA"]
      sortBy = "stateUpdatedTimestamp"
    }
  }
  signals_state_widget = {
    type = "alarm"
    properties = {
      title  = "State of each signal"
      alarms = [for s in local.health_signals : s.alarm.arn]
      sortBy = "stateUpdatedTimestamp"
    }
  }

  # Rows top to bottom. A row has a height in grid units and widgets with widths on a 24-column
  # grid. The verdict area (the first three rows) is 11 units tall so the verdict is on the first
  # screen, and later units add up to 3 more units of totals under it.
  dashboard_rows = concat(
    [
      { height = 5, widgets = [{ width = 24, widget = { type = "text", properties = { markdown = local.key_markdown } } }] },
      { height = 3, widgets = [{ width = 24, widget = local.verdict_widget }] },
      { height = 3, widgets = [{ width = 24, widget = local.signals_off_widget }] },
      { height = 4, widgets = [for s in local.health_signals : { width = 6, widget = local.tile_widgets[s.key] }] },
      { height = 3, widgets = [{ width = 24, widget = local.signals_state_widget }] },
      { height = 3, widgets = [{ width = 24, widget = { type = "text", properties = { markdown = local.detail_markdown } } }] },
    ],
    # Two charts to a row, in signal order.
    [for i in range(0, length(local.health_signals), 2) : {
      height  = 6
      widgets = [for s in slice(local.health_signals, i, min(i + 2, length(local.health_signals))) : { width = 12, widget = local.chart_widgets[s.key] }]
    }],
  )

  # x is the width of what sits to its left in the row, y the height of the rows above.
  dashboard_widgets = flatten([
    for i, r in local.dashboard_rows : [
      for j, c in r.widgets : merge(c.widget, {
        x      = sum(concat([0], [for q in slice(r.widgets, 0, j) : q.width]))
        y      = sum(concat([0], [for p in slice(local.dashboard_rows, 0, i) : p.height]))
        width  = c.width
        height = r.height
      })
    ]
  ])
}

# The verdict. Neither alarm has an action, so the verdict emails nobody and the alerts topic is
# untouched; they only carry a state for the page. They are left out of local.alarm_names because
# start and pause toggle actions and these have none. The rules name the alarms through the
# resources, so Terraform creates them after the alarms and destroys them first.
resource "aws_cloudwatch_composite_alarm" "unknown" {
  alarm_name        = "${local.name}-unknown"
  alarm_description = "The bot should have run and gave no data: the schedule is off, or a signal has no data. Display only; it sends nothing."
  alarm_rule        = local.unknown_rule
}

resource "aws_cloudwatch_composite_alarm" "not_healthy" {
  alarm_name        = "${local.name}-not-healthy"
  alarm_description = "A signal other than the schedule is off: failed runs, no recent story or a repost loop. Display only; it sends nothing."
  alarm_rule        = local.not_healthy_rule
}

resource "aws_cloudwatch_dashboard" "health" {
  dashboard_name = local.name
  # The last 7 days, well inside the log retention, and each chart keeps its alarm's period.
  dashboard_body = jsonencode({
    start          = "-P7D"
    periodOverride = "inherit"
    widgets        = local.dashboard_widgets
  })

  lifecycle {
    precondition {
      condition     = alltrue([for r in local.dashboard_rows : sum([for w in r.widgets : w.width]) <= 24])
      error_message = "A dashboard row is wider than the 24-column grid."
    }
  }
}
