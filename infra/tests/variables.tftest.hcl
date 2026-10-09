# Variable rules: what is sensitive, and the token parameter's validation. Runs offline against a
# mock provider (see environments.tftest.hcl). One validation per run, because expect_failures
# names the checkable objects that must fail and any other failure still fails the run.

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

run "values_that_print_in_public_logs_are_sensitive" {
  command = plan

  assert {
    condition     = issensitive(var.offices)
    error_message = "offices holds chat ids, and plans print in public Actions logs."
  }

  assert {
    condition     = issensitive(var.alert_email)
    error_message = "alert_email is contact info, and plans print in public Actions logs."
  }

  assert {
    condition     = issensitive(var.nws_user_agent)
    error_message = "nws_user_agent is contact info, and plans print in public Actions logs."
  }
}

run "production_accepts_its_own_token_parameter" {
  command = plan
}

run "staging_accepts_its_own_token_parameter" {
  command = plan

  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }
}

run "production_refuses_stagings_token_parameter" {
  command = plan

  variables {
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  expect_failures = [var.telegram_token_param_name]
}

run "staging_refuses_productions_token_parameter" {
  command = plan

  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot/telegram-token"
  }

  expect_failures = [var.telegram_token_param_name]
}

run "production_refuses_the_slashless_token_parameter" {
  command = plan

  variables {
    telegram_token_param_name = "weather-story-bot/telegram-token"
  }

  expect_failures = [var.telegram_token_param_name]
}

run "staging_refuses_the_slashless_token_parameter" {
  command = plan

  variables {
    environment               = "staging"
    telegram_token_param_name = "weather-story-bot-staging/telegram-token"
  }

  expect_failures = [var.telegram_token_param_name]
}

run "an_unknown_environment_is_refused" {
  command = plan

  variables {
    environment = "dev"
  }

  expect_failures = [var.environment]
}

run "an_empty_zip_hash_is_refused" {
  command = plan

  variables {
    lambda_zip_sha256 = ""
  }

  expect_failures = [var.lambda_zip_sha256]
}

run "a_zip_hash_in_the_wrong_form_is_refused" {
  command = plan

  variables {
    lambda_zip_sha256 = "not-a-base64-sha256"
  }

  expect_failures = [var.lambda_zip_sha256]
}

run "a_concurrency_of_zero_is_refused_because_it_switches_the_function_off" {
  command = plan

  variables {
    lambda_max_concurrency = 0
  }

  expect_failures = [var.lambda_max_concurrency]
}
