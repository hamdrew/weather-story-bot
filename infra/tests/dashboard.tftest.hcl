# The health dashboard and its two verdict alarms (dashboard.tf): the rules, the order and size of the
# widgets, that every tile and chart comes from its alarm, and that the page names no time zone,
# date, environment or token. Runs offline against a mock provider. These runs apply (against the
# mock) because a widget takes an alarm's ARN, which stays unknown until then; an alarm's mock ARN
# is a generated string, so the asserts compare against the resource's own ARN.
#
# What this cannot check, and the first staging apply and page do: that CloudWatch accepts the
# quoted rule syntax, and how the console draws the page.

mock_provider "aws" {
  # Resources validate the policy JSON they are given, and a mock would generate a random string.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }

  # Other resources take these as ARN arguments and validate their shape.
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:us-east-2:123456789012:mock"
    }
  }

  mock_resource "aws_lambda_function" {
    defaults = {
      arn = "arn:aws:lambda:us-east-2:123456789012:function:mock"
    }
  }

  mock_resource "aws_dynamodb_table" {
    defaults = {
      arn = "arn:aws:dynamodb:us-east-2:123456789012:table/mock"
    }
  }

  mock_resource "aws_s3_bucket" {
    defaults = {
      arn = "arn:aws:s3:::mock"
    }
  }

  mock_resource "aws_cloudwatch_log_group" {
    defaults = {
      arn = "arn:aws:logs:us-east-2:123456789012:log-group:mock"
    }
  }
}

override_data {
  target = data.aws_caller_identity.current
  values = {
    account_id = "123456789012"
  }
}

variables {
  environment               = "production"
  offices                   = { MKX = { chat_id = "-100", name = "Milwaukee/Sullivan" } }
  telegram_token_param_name = "/weather-story-bot/telegram-token"
  nws_user_agent            = "weather-story-bot (test@example.com)"
  alert_email               = "test@example.com"
  lambda_zip_sha256         = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
  artifacts_bucket          = "weather-story-bot-artifacts-123456789012"
  permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-boundary"
}

run "production_has_two_action_free_composites_and_one_dashboard" {
  command = apply

  assert {
    condition     = aws_cloudwatch_composite_alarm.unknown.alarm_name == "weather-story-bot-unknown" && aws_cloudwatch_composite_alarm.not_healthy.alarm_name == "weather-story-bot-not-healthy"
    error_message = "The verdict alarms are named <name>-unknown and <name>-not-healthy."
  }

  assert {
    condition     = aws_cloudwatch_dashboard.health.dashboard_name == "weather-story-bot"
    error_message = "The dashboard is named local.name."
  }

  # A composite with an action would email, and start and pause would have to toggle it.
  assert {
    condition = alltrue([
      for a in [aws_cloudwatch_composite_alarm.unknown, aws_cloudwatch_composite_alarm.not_healthy] :
      try(length(a.alarm_actions), 0) == 0 && try(length(a.ok_actions), 0) == 0 && try(length(a.insufficient_data_actions), 0) == 0
    ])
    error_message = "Neither verdict alarm may have an alarm, OK or insufficient-data action."
  }

  assert {
    condition     = !contains(output.alarm_names, "weather-story-bot-unknown") && !contains(output.alarm_names, "weather-story-bot-not-healthy")
    error_message = "start and pause toggle the alarms in alarm_names, and the verdict alarms have no actions to toggle."
  }
}

run "staging_has_its_own_composites_and_dashboard" {
  command = apply

  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = aws_cloudwatch_composite_alarm.unknown.alarm_name == "weather-story-bot-staging-unknown" && aws_cloudwatch_composite_alarm.not_healthy.alarm_name == "weather-story-bot-staging-not-healthy"
    error_message = "Staging's verdict alarms carry its own name."
  }

  assert {
    condition     = aws_cloudwatch_dashboard.health.dashboard_name == "weather-story-bot-staging"
    error_message = "Staging's dashboard is named local.name."
  }

  assert {
    condition = alltrue([
      for a in [aws_cloudwatch_composite_alarm.unknown, aws_cloudwatch_composite_alarm.not_healthy] :
      try(length(a.alarm_actions), 0) == 0 && try(length(a.ok_actions), 0) == 0 && try(length(a.insufficient_data_actions), 0) == 0
    ])
    error_message = "Neither verdict alarm may have an action."
  }

  assert {
    condition     = !contains(output.alarm_names, "weather-story-bot-staging-unknown") && !contains(output.alarm_names, "weather-story-bot-staging-not-healthy")
    error_message = "The verdict alarms stay out of alarm_names."
  }
}

# UNKNOWN is the schedule being off (ALARM) or any signal having no data; NOT HEALTHY is errors,
# quiet or repost-loop in ALARM. Warnings and nws-ambiguous are not in either rule.
run "production_rules_name_the_right_alarms_and_states" {
  command = apply

  assert {
    condition     = aws_cloudwatch_composite_alarm.unknown.alarm_rule == "ALARM(\"weather-story-bot-missed-runs\") OR INSUFFICIENT_DATA(\"weather-story-bot-missed-runs\") OR INSUFFICIENT_DATA(\"weather-story-bot-errors\") OR INSUFFICIENT_DATA(\"weather-story-bot-quiet\") OR INSUFFICIENT_DATA(\"weather-story-bot-repost-loop\")"
    error_message = "The unknown rule is missed-runs in ALARM, or any of the four signals in INSUFFICIENT_DATA."
  }

  assert {
    condition     = aws_cloudwatch_composite_alarm.not_healthy.alarm_rule == "ALARM(\"weather-story-bot-errors\") OR ALARM(\"weather-story-bot-quiet\") OR ALARM(\"weather-story-bot-repost-loop\")"
    error_message = "The not-healthy rule is errors, quiet or repost-loop in ALARM."
  }

  assert {
    condition = alltrue([
      for r in [aws_cloudwatch_composite_alarm.unknown.alarm_rule, aws_cloudwatch_composite_alarm.not_healthy.alarm_rule] :
      length(r) < 1000 && !strcontains(r, "nws-ambiguous")
    ])
    error_message = "A rule stays under 1,000 characters (the service allows 10,240) and never names the nws-ambiguous alarm."
  }

  # Every term is a real alarm's name, so a rename or removal is a Terraform error and destroy order holds.
  assert {
    condition = alltrue([
      for t in concat(local.unknown_terms, local.not_healthy_terms) :
      contains([
        aws_cloudwatch_metric_alarm.errors.alarm_name,
        aws_cloudwatch_metric_alarm.missed_runs.alarm_name,
        aws_cloudwatch_metric_alarm.quiet.alarm_name,
        aws_cloudwatch_metric_alarm.repost_loop.alarm_name,
      ], regex("\"(.*)\"", t)[0])
    ])
    error_message = "Every rule term must name one of the four health alarms."
  }
}

run "staging_rules_name_staging_alarms" {
  command = apply

  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = aws_cloudwatch_composite_alarm.unknown.alarm_rule == "ALARM(\"weather-story-bot-staging-missed-runs\") OR INSUFFICIENT_DATA(\"weather-story-bot-staging-missed-runs\") OR INSUFFICIENT_DATA(\"weather-story-bot-staging-errors\") OR INSUFFICIENT_DATA(\"weather-story-bot-staging-quiet\") OR INSUFFICIENT_DATA(\"weather-story-bot-staging-repost-loop\")"
    error_message = "Staging's unknown rule names staging's alarms."
  }

  assert {
    condition     = aws_cloudwatch_composite_alarm.not_healthy.alarm_rule == "ALARM(\"weather-story-bot-staging-errors\") OR ALARM(\"weather-story-bot-staging-quiet\") OR ALARM(\"weather-story-bot-staging-repost-loop\")"
    error_message = "Staging's not-healthy rule names staging's alarms."
  }
}

# This unit builds on the five alarms and changes none of them (FR5.3).
run "the_five_existing_alarms_are_unchanged" {
  command = apply

  assert {
    condition = jsonencode({
      for k, a in {
        errors        = aws_cloudwatch_metric_alarm.errors
        missed_runs   = aws_cloudwatch_metric_alarm.missed_runs
        quiet         = aws_cloudwatch_metric_alarm.quiet
        repost_loop   = aws_cloudwatch_metric_alarm.repost_loop
        nws_ambiguous = aws_cloudwatch_metric_alarm.nws_ambiguous
        } : k => {
        period    = a.period
        evaluate  = a.evaluation_periods
        threshold = a.threshold
        compare   = a.comparison_operator
        missing   = a.treat_missing_data
      }
      }) == jsonencode({
      errors        = { period = 900, evaluate = 2, threshold = 1, compare = "GreaterThanOrEqualToThreshold", missing = "notBreaching" }
      missed_runs   = { period = 3600, evaluate = 1, threshold = 1, compare = "LessThanThreshold", missing = "breaching" }
      quiet         = { period = 86400, evaluate = 2, threshold = 1, compare = "LessThanThreshold", missing = "breaching" }
      repost_loop   = { period = 10800, evaluate = 1, threshold = 8, compare = "GreaterThanThreshold", missing = "notBreaching" }
      nws_ambiguous = { period = 900, evaluate = 1, threshold = 1, compare = "GreaterThanOrEqualToThreshold", missing = "notBreaching" }
    })
    error_message = "A health alarm's period, evaluation periods, threshold, comparison or missing-data setting changed."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.errors.datapoints_to_alarm == 2
    error_message = "errors still needs 2 of 2 periods."
  }

  assert {
    condition = alltrue([
      for a in [
        aws_cloudwatch_metric_alarm.errors,
        aws_cloudwatch_metric_alarm.missed_runs,
        aws_cloudwatch_metric_alarm.quiet,
        aws_cloudwatch_metric_alarm.repost_loop,
        aws_cloudwatch_metric_alarm.nws_ambiguous,
      ] : jsonencode(tolist(a.alarm_actions)) == jsonencode([aws_sns_topic.alerts.arn]) && jsonencode(tolist(a.ok_actions)) == jsonencode([aws_sns_topic.alerts.arn])
    ])
    error_message = "Each existing alarm still emails the alerts topic on ALARM and OK."
  }

  assert {
    condition     = jsonencode(output.alarm_names) == jsonencode(["weather-story-bot-errors", "weather-story-bot-missed-runs", "weather-story-bot-quiet", "weather-story-bot-repost-loop", "weather-story-bot-nws-ambiguous"])
    error_message = "alarm_names lists exactly the five existing alarms, for start and pause."
  }
}

# [x, y, width, height] of the 13 widgets, in the order they are read top to bottom and, on a phone,
# stacked in a single column.
run "the_thirteen_widgets_sit_on_the_grid_in_reading_order" {
  command = apply

  assert {
    condition = jsonencode([for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : [w.x, w.y, w.width, w.height]]) == jsonencode([
      [0, 0, 24, 5],
      [0, 5, 24, 3],
      [0, 8, 24, 3],
      [0, 11, 6, 4],
      [6, 11, 6, 4],
      [12, 11, 6, 4],
      [18, 11, 6, 4],
      [0, 15, 24, 3],
      [0, 18, 24, 3],
      [0, 21, 12, 6],
      [12, 21, 12, 6],
      [0, 27, 12, 6],
      [12, 27, 12, 6],
    ])
    error_message = "The widgets must keep the specified grid positions and sizes."
  }

  assert {
    condition = jsonencode([for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : w.type]) == jsonencode([
      "text", "alarm", "alarm", "metric", "metric", "metric", "metric", "alarm", "text", "metric", "metric", "metric", "metric",
    ])
    error_message = "The order is key, verdict, signals off, four tiles, signal states, detail heading, four charts."
  }

  assert {
    condition     = alltrue([for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : w.x + w.width <= 24])
    error_message = "No widget may overflow the 24-column grid."
  }

  # The tiles share one row and one height, and the verdict area leaves room for the next unit's totals.
  assert {
    condition     = length(distinct([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 3, 7) : [w.y, w.height]])) == 1
    error_message = "The four tiles must share one row and height."
  }

  assert {
    condition     = sum([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 0, 3) : w.height]) <= 11
    error_message = "The verdict area (key, verdict, signals off) must be at most 11 grid units tall."
  }
}

run "each_tile_shows_its_value_filled_with_zero_and_a_sparkline" {
  command = apply

  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 3, 7) : w.properties.title]) == jsonencode([
      "Runs on schedule: runs per hour",
      "No failed runs: failed runs per 15 minutes",
      "A story posted recently: posts per day",
      "No repost loop: posts per 3 hours",
    ])
    error_message = "Tiles are in signal order and each title names the signal and its unit."
  }

  assert {
    condition = alltrue([
      for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 3, 7) :
      w.properties.view == "singleValue" && w.properties.sparkline == true
    ])
    error_message = "A tile is a single value with a sparkline."
  }

  # A count with no events is zero, not blank: the visible series is FILL(m1, 0) over the hidden alarm metric.
  assert {
    condition = alltrue([
      for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 3, 7) :
      length(w.properties.metrics) == 2 && w.properties.metrics[0][0].expression == "FILL(m1, 0)" && w.properties.metrics[0][0].id == "e1" &&
      element(w.properties.metrics[1], length(w.properties.metrics[1]) - 1).id == "m1" && element(w.properties.metrics[1], length(w.properties.metrics[1]) - 1).visible == false
    ])
    error_message = "Each tile shows FILL(m1, 0) over its hidden alarm metric m1."
  }

  # The metric under the tile is the alarm's own (same for the fill = false shape, which keeps these fields).
  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 3, 7) : w.properties.metrics[1]]) == jsonencode([
      ["AWS/Lambda", "Invocations", "FunctionName", "weather-story-bot", { id = "m1", period = 3600, stat = "Sum", visible = false }],
      ["AWS/Lambda", "Errors", "FunctionName", "weather-story-bot", { id = "m1", period = 900, stat = "Sum", visible = false }],
      ["WeatherStoryBot", "StoriesPosted", { id = "m1", period = 86400, stat = "Sum", visible = false }],
      ["WeatherStoryBot", "StoriesPosted", { id = "m1", period = 10800, stat = "Sum", visible = false }],
    ])
    error_message = "Each tile's metric is its alarm's namespace, name, dimensions, statistic and period."
  }

  # An alarm with no dimensions gives [namespace, name]; one with FunctionName adds the pair. The
  # tile's own fill = false shape (the plain alarm metric, no hidden id) cannot be reached from a
  # test, because a local cannot be overridden; the metric row both shapes share is checked above.
  assert {
    condition     = length(local.alarm_metric["quiet"]) == 2 && length(local.alarm_metric["errors"]) == 4
    error_message = "A metric with no dimensions is [namespace, name] and one with FunctionName adds the pair."
  }
}

run "each_chart_draws_its_alarms_own_metric_and_threshold" {
  command = apply

  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 9, 13) : w.properties.metrics]) == jsonencode([
      [["AWS/Lambda", "Invocations", "FunctionName", "weather-story-bot", { period = 3600, stat = "Sum" }]],
      [["AWS/Lambda", "Errors", "FunctionName", "weather-story-bot", { period = 900, stat = "Sum" }]],
      [["WeatherStoryBot", "StoriesPosted", { period = 86400, stat = "Sum" }]],
      [["WeatherStoryBot", "StoriesPosted", { period = 10800, stat = "Sum" }]],
    ])
    error_message = "A chart's metric is its alarm's namespace, name, dimensions (none for quiet and repost-loop), statistic and period."
  }

  # Annotation = the alarm's threshold; the shaded side is the breaching side.
  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 9, 13) : w.properties.annotations.horizontal]) == jsonencode([
      [{ label = "Alarm threshold", value = aws_cloudwatch_metric_alarm.missed_runs.threshold, fill = "below" }],
      [{ label = "Alarm threshold", value = aws_cloudwatch_metric_alarm.errors.threshold, fill = "above" }],
      [{ label = "Alarm threshold", value = aws_cloudwatch_metric_alarm.quiet.threshold, fill = "below" }],
      [{ label = "Alarm threshold", value = aws_cloudwatch_metric_alarm.repost_loop.threshold, fill = "above" }],
    ])
    error_message = "Each chart's threshold line is its alarm's threshold, shaded on the side that breaches."
  }

  # Both quiet and repost-loop leave dimensions unset; the builder reads that as none, not an error.
  assert {
    condition     = aws_cloudwatch_metric_alarm.quiet.dimensions == null && aws_cloudwatch_metric_alarm.repost_loop.dimensions == null
    error_message = "This run is meant to exercise alarms with no dimensions."
  }
}

run "staging_charts_read_stagings_namespace_and_function" {
  command = apply

  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 9, 13) : slice(w.properties.metrics[0], 0, 2)]) == jsonencode([
      ["AWS/Lambda", "Invocations"],
      ["AWS/Lambda", "Errors"],
      ["WeatherStoryBot/staging", "StoriesPosted"],
      ["WeatherStoryBot/staging", "StoriesPosted"],
    ])
    error_message = "Staging's charts read staging's own StoriesPosted namespace."
  }

  assert {
    condition = jsonencode([for w in slice(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets, 9, 11) : slice(w.properties.metrics[0], 2, 4)]) == jsonencode([
      ["FunctionName", "weather-story-bot-staging"],
      ["FunctionName", "weather-story-bot-staging"],
    ])
    error_message = "Staging's Lambda charts read staging's function."
  }
}

run "the_alarm_lists_carry_the_right_alarms_filters_and_sort" {
  command = apply

  assert {
    condition = jsonencode(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[1].properties.alarms) == jsonencode([
      aws_cloudwatch_composite_alarm.unknown.arn, aws_cloudwatch_composite_alarm.not_healthy.arn,
    ])
    error_message = "The verdict list shows the two verdict alarms."
  }

  assert {
    condition = alltrue([
      for i in [2, 7] : jsonencode(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[i].properties.alarms) == jsonencode([
        aws_cloudwatch_metric_alarm.missed_runs.arn, aws_cloudwatch_metric_alarm.errors.arn, aws_cloudwatch_metric_alarm.quiet.arn, aws_cloudwatch_metric_alarm.repost_loop.arn,
      ])
    ])
    error_message = "Both signal lists show the four health alarms in signal order, and no others."
  }

  assert {
    condition     = jsonencode(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[2].properties.states) == jsonencode(["ALARM", "INSUFFICIENT_DATA"])
    error_message = "The signals-off list shows only ALARM and INSUFFICIENT_DATA."
  }

  assert {
    condition = alltrue([
      for i in [1, 7] : !contains(keys(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[i].properties), "states")
    ])
    error_message = "The verdict list and the signal states list are unfiltered."
  }

  assert {
    condition     = alltrue([for i in [1, 2, 7] : jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[i].properties.sortBy == "stateUpdatedTimestamp"])
    error_message = "The alarm lists sort by the time of the last state change."
  }
}

# The page follows the browser's time zone, so nothing on it carries one, a date, a time, the
# environment or the token parameter's name.
run "production_page_has_no_time_zone_date_environment_or_token" {
  command = apply

  assert {
    condition     = !strcontains(aws_cloudwatch_dashboard.health.dashboard_body, "timezone")
    error_message = "No widget may set a timezone: the property takes a fixed offset and cannot follow daylight saving time."
  }

  assert {
    condition = alltrue([
      for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : alltrue([
        !can(regex("[0-9]{4}-[0-9]{2}-[0-9]{2}", w.properties.markdown)),
        !can(regex("[0-9]{1,2}:[0-9]{2}", w.properties.markdown)),
        !strcontains(lower(w.properties.markdown), "production"),
        !strcontains(lower(w.properties.markdown), "staging"),
      ]) if w.type == "text"
    ])
    error_message = "No text widget may carry a date, a clock time or an environment name."
  }

  assert {
    condition     = !strcontains(lower(aws_cloudwatch_dashboard.health.dashboard_body), "telegram") && !strcontains(aws_cloudwatch_dashboard.health.dashboard_body, var.telegram_token_param_name)
    error_message = "The page must not name the Telegram token parameter."
  }
}

run "staging_page_has_no_time_zone_date_environment_or_token" {
  command = apply

  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition = alltrue([
      for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : alltrue([
        !strcontains(lower(w.properties.markdown), "production"),
        !strcontains(lower(w.properties.markdown), "staging"),
      ]) if w.type == "text"
    ])
    error_message = "Staging's text must not name the environment either: the page adds no label."
  }

  assert {
    condition     = !strcontains(aws_cloudwatch_dashboard.health.dashboard_body, "timezone") && !strcontains(lower(aws_cloudwatch_dashboard.health.dashboard_body), "telegram")
    error_message = "No time zone and no token parameter on staging's page."
  }
}

run "the_key_and_heading_say_how_to_read_the_page_in_order" {
  command = apply

  # The reading order comes first, then what an empty list means, then zeros under UNKNOWN, then the quiet signal.
  assert {
    condition = alltrue([
      length(split("Reading the verdict", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]) < length(split("Signals that are off", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]),
      length(split("Signals that are off", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]) < length(split("tiles below may show 0", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]),
      length(split("tiles below may show 0", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]) < length(split("with no post", jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown)[0]),
    ])
    error_message = "The key must give the reading order first, then the empty-list, zero-when-UNKNOWN and quiet sentences."
  }

  assert {
    condition = alltrue([
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown, "UNKNOWN if the `unknown` row is not OK (it wins). Otherwise NOT HEALTHY if the `not-healthy` row is not OK. Otherwise HEALTHY."),
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown, "is empty when all four signals are fine"),
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown, "may show 0 because the bot did not report"),
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[0].properties.markdown, "${var.quiet_alarm_days} day(s) with no post"),
    ])
    error_message = "The key must carry each sentence of the reading order and the empty and no-data cases."
  }

  assert {
    condition = alltrue([
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[8].properties.markdown, "A chart with no line has no data in this range"),
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[8].properties.markdown, "time zone control"),
      strcontains(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets[8].properties.markdown, "Local"),
    ])
    error_message = "The detail heading must say what no line means and how to show local time."
  }
}

run "the_body_opens_on_seven_days_and_stays_inside_its_budgets" {
  command = apply

  assert {
    condition     = jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).start == "-P7D" && jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).periodOverride == "inherit"
    error_message = "The page opens on the last 7 days and each widget keeps its alarm's period."
  }

  # Eight metrics today; 50 is the free allowance, and an expression is not a metric.
  assert {
    condition = sum([
      for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets :
      length([for m in try(w.properties.metrics, []) : m if !can(m[0].expression)])
    ]) <= 50
    error_message = "A dashboard may hold at most 50 metrics inside the free allowance."
  }

  assert {
    condition     = length(jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets) <= 30 && length(aws_cloudwatch_dashboard.health.dashboard_body) < 20000
    error_message = "At most 30 widgets, and a body far under CloudWatch's size limit."
  }

  # Extension points still make a valid rule and a valid layout: one more alarm term, one more row.
  assert {
    condition = alltrue([
      length(join(" OR ", concat(local.not_healthy_terms, [format(local.rule_term_format, "ALARM", "weather-story-bot-extra")]))) < 1000,
      length(split(" OR ", join(" OR ", concat(local.not_healthy_terms, [format(local.rule_term_format, "ALARM", "weather-story-bot-extra")])))) == length(local.not_healthy_terms) + 1,
      !startswith(join(" OR ", local.not_healthy_terms), " OR ") && !endswith(join(" OR ", local.not_healthy_terms), " OR "),
    ])
    error_message = "Appending a term to the not-healthy list must keep a well-formed rule under the budget."
  }

  assert {
    condition = alltrue([
      for i, r in local.dashboard_rows :
      sum([for w in jsondecode(aws_cloudwatch_dashboard.health.dashboard_body).widgets : w.y == sum(concat([0], [for p in slice(local.dashboard_rows, 0, i) : p.height])) ? 1 : 0]) == length(r.widgets)
    ])
    error_message = "Every widget's y is the heights of the rows above it, so a row added to dashboard_rows moves the rows below down."
  }
}
