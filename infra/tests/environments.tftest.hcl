# What var.environment derives: names, the metric namespace, the production-only resources and the
# Environment tag. Runs offline against a mock provider, so it needs no AWS
# credentials, and a mocked policy document's .json is a placeholder (iam.tftest.hcl asserts on
# the documents' inputs instead).

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

run "production_keeps_the_unsuffixed_names" {
  assert {
    condition     = local.name == "weather-story-bot"
    error_message = "Production must keep the unsuffixed name; renaming the table or bucket is a replace."
  }

  assert {
    condition     = aws_lambda_function.bot.function_name == "weather-story-bot"
    error_message = "The function is named from local.name."
  }

  assert {
    condition     = aws_dynamodb_table.state.name == "weather-story-bot-state"
    error_message = "The state table is named from local.name."
  }

  assert {
    condition     = aws_s3_bucket.archive.bucket == "weather-story-bot-archive-123456789012"
    error_message = "The archive bucket is named from local.name and the account."
  }

  assert {
    condition     = aws_iam_role.lambda.name == "weather-story-bot-lambda" && aws_iam_role.scheduler.name == "weather-story-bot-scheduler"
    error_message = "Roles are named from local.name."
  }

  assert {
    condition     = aws_sns_topic.alerts.name == "weather-story-bot-alerts" && aws_scheduler_schedule.bot.name == "weather-story-bot"
    error_message = "The topic and schedule are named from local.name."
  }
}

run "staging_is_suffixed_everywhere" {
  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = local.name == "weather-story-bot-staging"
    error_message = "Staging is weather-story-bot-<env>."
  }

  assert {
    condition     = aws_lambda_function.bot.function_name == "weather-story-bot-staging"
    error_message = "The function is named from local.name."
  }

  assert {
    condition     = aws_dynamodb_table.state.name == "weather-story-bot-staging-state"
    error_message = "The state table is named from local.name."
  }

  assert {
    condition     = aws_s3_bucket.archive.bucket == "weather-story-bot-staging-archive-123456789012"
    error_message = "The archive bucket is named from local.name and the account."
  }

  assert {
    condition     = aws_iam_role.lambda.name == "weather-story-bot-staging-lambda" && aws_iam_role.scheduler.name == "weather-story-bot-staging-scheduler"
    error_message = "Roles are named from local.name."
  }

  assert {
    condition     = aws_sns_topic.alerts.name == "weather-story-bot-staging-alerts" && aws_scheduler_schedule.bot.name == "weather-story-bot-staging"
    error_message = "The topic and schedule are named from local.name."
  }
}

run "production_keeps_the_original_metric_namespace" {
  assert {
    condition     = local.metric_namespace == "WeatherStoryBot"
    error_message = "Production keeps its original namespace so its metric history carries on."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].namespace == "WeatherStoryBot" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].namespace == "WeatherStoryBot"
    error_message = "Both metric filters publish to the environment's namespace."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.quiet.namespace == "WeatherStoryBot" && aws_cloudwatch_metric_alarm.repost_loop.namespace == "WeatherStoryBot" && aws_cloudwatch_metric_alarm.nws_ambiguous.namespace == "WeatherStoryBot"
    error_message = "Every custom-metric alarm reads the environment's namespace."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.pattern == "{ $.event = \"telegram.message_sent\" }" && aws_cloudwatch_log_metric_filter.nws_ambiguous.pattern == "{ $.event = \"nws.ambiguous_stories\" }"
    error_message = "Each filter counts its event and nothing else (FR-007)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.name == "weather-story-bot-stories-posted" && aws_cloudwatch_log_metric_filter.nws_ambiguous.name == "weather-story-bot-nws-ambiguous"
    error_message = "The filters keep their names (FR-004)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].name == "StoriesPosted" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].name == "AmbiguousStories"
    error_message = "The filters keep their metric names, so the charted history continues (FR-004)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].value == "1" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].value == "1"
    error_message = "Each matching line still counts as 1 (FR-004)."
  }
}

run "staging_has_its_own_metric_namespace" {
  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = local.metric_namespace == "WeatherStoryBot/staging"
    error_message = "A shared namespace would merge staging's posts into production's quiet and repost-loop alarms."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].namespace == "WeatherStoryBot/staging" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].namespace == "WeatherStoryBot/staging"
    error_message = "Both metric filters publish to the environment's namespace."
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.quiet.namespace == "WeatherStoryBot/staging" && aws_cloudwatch_metric_alarm.repost_loop.namespace == "WeatherStoryBot/staging" && aws_cloudwatch_metric_alarm.nws_ambiguous.namespace == "WeatherStoryBot/staging"
    error_message = "Every custom-metric alarm reads the environment's namespace."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.pattern == "{ $.event = \"telegram.message_sent\" }" && aws_cloudwatch_log_metric_filter.nws_ambiguous.pattern == "{ $.event = \"nws.ambiguous_stories\" }"
    error_message = "Each filter counts its event and nothing else (FR-007)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.name == "weather-story-bot-staging-stories-posted" && aws_cloudwatch_log_metric_filter.nws_ambiguous.name == "weather-story-bot-staging-nws-ambiguous"
    error_message = "The filters keep their names (FR-004)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].name == "StoriesPosted" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].name == "AmbiguousStories"
    error_message = "The filters keep their metric names, so the charted history continues (FR-004)."
  }

  assert {
    condition     = aws_cloudwatch_log_metric_filter.stories_posted.metric_transformation[0].value == "1" && aws_cloudwatch_log_metric_filter.nws_ambiguous.metric_transformation[0].value == "1"
    error_message = "Each matching line still counts as 1 (FR-004)."
  }
}

run "production_has_the_budget_and_the_mvp_table" {
  assert {
    condition     = length(aws_budgets_budget.monthly) == 1
    error_message = "The budget covers the whole account, so production owns it."
  }

  assert {
    condition     = length(aws_dynamodb_table.posted) == 1 && aws_dynamodb_table.posted[0].name == "weather-story-bot-posted"
    error_message = "The MVP table is production's rollback."
  }
}

run "staging_has_neither_the_budget_nor_the_mvp_table" {
  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0
    error_message = "A budget per environment would send duplicate emails for the same spend."
  }

  assert {
    condition     = length(aws_dynamodb_table.posted) == 0
    error_message = "No other environment ever had MVP data."
  }
}

run "production_tags_everything_with_the_lowercase_environment" {
  assert {
    condition     = local.default_tags.Environment == "production"
    error_message = "IAM tag conditions compare case-sensitively, so the tag is the lowercase environment."
  }

  assert {
    condition     = local.default_tags.Project == "weather-story-bot" && local.default_tags.ManagedBy == "terraform"
    error_message = "Project is local.name and ManagedBy is terraform."
  }
}

run "staging_tags_everything_with_the_lowercase_environment" {
  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = local.default_tags.Environment == "staging"
    error_message = "IAM tag conditions compare case-sensitively, so the tag is the lowercase environment."
  }

  assert {
    condition     = local.default_tags.Project == "weather-story-bot-staging"
    error_message = "Cost Explorer splits on Project, which is local.name."
  }
}

run "the_function_has_a_concurrency_ceiling_in_every_environment" {
  assert {
    condition     = aws_lambda_function.bot.reserved_concurrent_executions == 10
    error_message = "A ceiling caps the spend from a retry storm or a runaway invoker. It is not mutual exclusion; the office lease does that."
  }
}

run "the_ceiling_follows_the_variable" {
  variables {
    lambda_max_concurrency = 3
  }

  assert {
    condition     = aws_lambda_function.bot.reserved_concurrent_executions == 3
    error_message = "The function's reserved concurrency is var.lambda_max_concurrency."
  }
}

run "alarm_emails_name_the_event_to_search_for" {
  assert {
    condition = alltrue([
      strcontains(aws_cloudwatch_metric_alarm.repost_loop.alarm_description, "telegram.message_sent"),
      strcontains(aws_cloudwatch_metric_alarm.repost_loop.alarm_description, "Story posted"),
      strcontains(aws_cloudwatch_metric_alarm.nws_ambiguous.alarm_description, "nws.ambiguous_stories"),
    ])
    error_message = "The repost-loop and nws-ambiguous emails name the event to search for (FR-009)."
  }

  assert {
    condition = alltrue([
      !strcontains(aws_cloudwatch_metric_alarm.repost_loop.alarm_description, "Telegram message sent"),
      !strcontains(aws_cloudwatch_metric_alarm.nws_ambiguous.alarm_description, "Ambiguous stories from NWS"),
    ])
    error_message = "The emails no longer point at message text (FR-009)."
  }

  assert {
    condition     = strcontains(aws_cloudwatch_metric_alarm.repost_loop.alarm_description, local.logs_console_url) && strcontains(aws_cloudwatch_metric_alarm.nws_ambiguous.alarm_description, local.logs_console_url)
    error_message = "Both emails still link to the logs."
  }

  assert {
    condition     = strcontains(aws_cloudwatch_metric_alarm.quiet.alarm_description, "Run complete")
    error_message = "The quiet email still points at the Run complete summaries (FR-009)."
  }
}

# Two consecutive breaching periods need a run in each one. On a slower schedule the empty periods
# count as not breaching, so the alarm could never fire.
run "the_slow_run_alarm_refuses_a_schedule_it_cannot_see" {
  command = plan

  variables {
    schedule_expression = "rate(30 minutes)"
  }

  expect_failures = [aws_cloudwatch_metric_alarm.slow_runs]
}

run "production_has_the_slow_run_alarm" {
  assert {
    condition     = aws_cloudwatch_metric_alarm.slow_runs.alarm_name == "weather-story-bot-slow-runs" && aws_cloudwatch_metric_alarm.slow_runs.dimensions.FunctionName == aws_lambda_function.bot.function_name && aws_lambda_function.bot.function_name == "weather-story-bot"
    error_message = "Production's slow-run alarm is named from local.name and reads its own function."
  }

  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.slow_runs.namespace == "AWS/Lambda",
      aws_cloudwatch_metric_alarm.slow_runs.metric_name == "Duration",
      aws_cloudwatch_metric_alarm.slow_runs.statistic == "Maximum",
      aws_cloudwatch_metric_alarm.slow_runs.period == 900,
      aws_cloudwatch_metric_alarm.slow_runs.evaluation_periods == 2,
      aws_cloudwatch_metric_alarm.slow_runs.datapoints_to_alarm == 2,
      aws_cloudwatch_metric_alarm.slow_runs.comparison_operator == "GreaterThanThreshold",
      aws_cloudwatch_metric_alarm.slow_runs.threshold == 60000,
      aws_cloudwatch_metric_alarm.slow_runs.treat_missing_data == "notBreaching",
      aws_cloudwatch_metric_alarm.slow_runs.actions_enabled == true,
    ])
    error_message = "The alarm fires when the maximum Duration is above 60,000 ms in 2 consecutive 15-minute periods, and no runs is not breaching (FR-013, FR-014, FR-017)."
  }

  assert {
    condition = alltrue([
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "60 seconds"),
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "300 seconds"),
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "record.metrics.durationMs"),
    ])
    error_message = "The email states the threshold, the function's time limit and where to read each run's duration (FR-016)."
  }

  assert {
    condition     = contains(output.alarm_names, aws_cloudwatch_metric_alarm.slow_runs.alarm_name)
    error_message = "Start and pause must switch the slow-run alarm (FR-015, FR-017)."
  }
}

run "staging_has_its_own_slow_run_alarm" {
  variables {
    environment               = "staging"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.slow_runs.alarm_name == "weather-story-bot-staging-slow-runs" && aws_cloudwatch_metric_alarm.slow_runs.dimensions.FunctionName == aws_lambda_function.bot.function_name && aws_lambda_function.bot.function_name == "weather-story-bot-staging"
    error_message = "Staging's slow-run alarm is named from local.name and reads its own function."
  }

  assert {
    condition = alltrue([
      aws_cloudwatch_metric_alarm.slow_runs.namespace == "AWS/Lambda",
      aws_cloudwatch_metric_alarm.slow_runs.metric_name == "Duration",
      aws_cloudwatch_metric_alarm.slow_runs.statistic == "Maximum",
      aws_cloudwatch_metric_alarm.slow_runs.period == 900,
      aws_cloudwatch_metric_alarm.slow_runs.evaluation_periods == 2,
      aws_cloudwatch_metric_alarm.slow_runs.datapoints_to_alarm == 2,
      aws_cloudwatch_metric_alarm.slow_runs.comparison_operator == "GreaterThanThreshold",
      aws_cloudwatch_metric_alarm.slow_runs.threshold == 60000,
      aws_cloudwatch_metric_alarm.slow_runs.treat_missing_data == "notBreaching",
      aws_cloudwatch_metric_alarm.slow_runs.actions_enabled == true,
    ])
    error_message = "The alarm fires when the maximum Duration is above 60,000 ms in 2 consecutive 15-minute periods, and no runs is not breaching (FR-013, FR-014, FR-017)."
  }

  assert {
    condition = alltrue([
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "60 seconds"),
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "300 seconds"),
      strcontains(aws_cloudwatch_metric_alarm.slow_runs.alarm_description, "record.metrics.durationMs"),
    ])
    error_message = "The email states the threshold, the function's time limit and where to read each run's duration (FR-016)."
  }

  assert {
    condition     = contains(output.alarm_names, aws_cloudwatch_metric_alarm.slow_runs.alarm_name)
    error_message = "Start and pause must switch the slow-run alarm (FR-015, FR-017)."
  }
}
