locals {
  metric_namespace = "WeatherStoryBot"
  logs_console_url = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#logsV2:log-groups/log-group/${replace(aws_cloudwatch_log_group.lambda.name, "/", "$252F")}"
}

# Left unencrypted on purpose: CloudWatch alarms can't publish to a topic encrypted
# with the AWS managed aws/sns key.
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

# Stays PendingConfirmation (and drops alerts) until the confirmation link is clicked.
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Counts every message Telegram accepts (new posts and "Updated" reposts), including ones whose
# DynamoDB record then fails. Depends on the Telegram client's exact "Telegram message sent" message.
resource "aws_cloudwatch_log_metric_filter" "stories_posted" {
  name           = "${local.name}-stories-posted"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.message = \"Telegram message sent\" }"

  metric_transformation {
    name      = "StoriesPosted"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name        = "${local.name}-errors"
  alarm_description = "The bot failed on 2 runs in a row (an NWS, Telegram, AWS or config error, or a timeout). Check the latest ERROR lines in the logs: ${local.logs_console_url}"

  namespace   = "AWS/Lambda"
  metric_name = "Errors"
  dimensions = {
    FunctionName = aws_lambda_function.bot.function_name
  }
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "missed_runs" {
  alarm_name        = "${local.name}-missed-runs"
  alarm_description = "The bot was not invoked in the last hour, so the schedule is probably disabled, deleted or failing to invoke the function. Check the EventBridge Scheduler schedule ${aws_scheduler_schedule.bot.name}, then the logs for recent runs: ${local.logs_console_url}"

  namespace   = "AWS/Lambda"
  metric_name = "Invocations"
  dimensions = {
    FunctionName = aws_lambda_function.bot.function_name
  }
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  # A stopped schedule publishes no data points at all.
  treat_missing_data = "breaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "quiet" {
  alarm_name        = "${local.name}-quiet"
  alarm_description = "No stories were posted for ${var.quiet_alarm_days} day(s) even though runs are not failing. NWS may have changed the API, or the bot is skipping everything. Check \"Run complete\" summaries in the logs and compare with each office's weather.gov weatherstory page: ${local.logs_console_url}"

  namespace           = local.metric_namespace
  metric_name         = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].name
  statistic           = "Sum"
  period              = 86400
  evaluation_periods  = var.quiet_alarm_days
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  # Nothing posted means no data points, not zeros.
  treat_missing_data = "breaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "repost_loop" {
  alarm_name        = "${local.name}-repost-loop"
  alarm_description = "More than ${var.repost_alarm_max_posts} stories were posted in 3 hours, so the bot may be reposting the same stories (for example, DynamoDB writes failing after each post). Check the Telegram channel for duplicates and the logs for \"Telegram message sent\" lines with repeated image_filename values that have no matching \"Story posted\" line: ${local.logs_console_url}"

  namespace           = local.metric_namespace
  metric_name         = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].name
  statistic           = "Sum"
  period              = 10800
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.repost_alarm_max_posts
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# One line per office per run while NWS lists ambiguous stories. Depends on the handler's exact
# "Ambiguous stories from NWS" message. Rejections don't fail the run, so the errors alarm stays quiet.
resource "aws_cloudwatch_log_metric_filter" "nws_ambiguous" {
  name           = "${local.name}-nws-ambiguous"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "{ $.message = \"Ambiguous stories from NWS\" }"

  metric_transformation {
    name      = "AmbiguousStories"
    namespace = local.metric_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "nws_ambiguous" {
  alarm_name        = "${local.name}-nws-ambiguous"
  alarm_description = "NWS listed active stories that share an image ID, a title and start time, or an identical image, so the bot skipped all of them. No action is needed if NWS fixes its data; the OK email follows once a run sees a clean listing. Check the \"stories\" and \"reasons\" fields of \"Ambiguous stories from NWS\" lines in the logs and compare with each office's weather.gov weatherstory page: ${local.logs_console_url}"

  namespace           = local.metric_namespace
  metric_name         = aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].name
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  # No rejections means no data points.
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# Covers the whole account, not just this project. Emails directly rather than through SNS.
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.alert_email]
  }
}
