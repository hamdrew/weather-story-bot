# What var.environment derives: names, the metric namespace, the production-only resources and the
# Environment tag (infra/environments). Runs offline against a mock provider, so it needs no AWS
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
}

run "staging_has_its_own_metric_namespace" {
  variables {
    environment               = "staging"
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
