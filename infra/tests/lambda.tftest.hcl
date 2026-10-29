# The Lambda's code comes from the artifacts bucket under a key derived from the zip's hash, and both
# workload roles carry their environment's permissions boundary (infra/iam). Runs offline against a
# mock provider (see environments.tftest.hcl).

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

# Distinct ARNs per resource, so an assertion can tell the state table from the MVP table and the
# archive bucket from anything else. (The mock_resource defaults above give every table one ARN.)
override_resource {
  target = aws_dynamodb_table.state
  values = {
    arn = "arn:aws:dynamodb:us-east-2:123456789012:table/state-mock"
  }
}

override_resource {
  target = aws_dynamodb_table.posted[0]
  values = {
    arn = "arn:aws:dynamodb:us-east-2:123456789012:table/posted-mock"
  }
}

override_resource {
  target = aws_s3_bucket.archive
  values = {
    arn = "arn:aws:s3:::archive-mock"
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
  # "+" and "/" are the two characters base64url replaces.
  lambda_zip_sha256        = "a+b/cdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNO="
  artifacts_bucket         = "weather-story-bot-artifacts-123456789012"
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/weather-story-bot-boundary"
}

run "production_code_comes_from_its_own_prefix_under_the_hash" {
  assert {
    condition     = aws_lambda_function.bot.s3_bucket == "weather-story-bot-artifacts-123456789012"
    error_message = "The code comes from the artifacts bucket."
  }

  assert {
    condition     = aws_lambda_function.bot.s3_key == "production/lambda/a-b_cdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNO.zip"
    error_message = "The key is <env>/lambda/<base64url of the hash, unpadded>.zip."
  }

  assert {
    condition     = aws_lambda_function.bot.source_code_hash == var.lambda_zip_sha256
    error_message = "The hash is the zip's own base64 sha256, so Lambda redeploys exactly when the bytes change."
  }

  assert {
    condition     = aws_lambda_function.bot.filename == null
    error_message = "No local file: the zip is uploaded by mise run deploy, never by Terraform."
  }

  assert {
    condition     = output.lambda_s3_key == aws_lambda_function.bot.s3_key
    error_message = "mise run deploy uploads to the key the plan holds, so the output must match the function's."
  }
}

run "staging_code_comes_from_its_own_prefix" {
  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
  }

  assert {
    condition     = aws_lambda_function.bot.s3_key == "staging/lambda/a-b_cdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNO.zip"
    error_message = "Each apply role writes only its own environment's prefix."
  }
}

run "production_roles_carry_the_production_boundary" {
  assert {
    condition     = aws_iam_role.lambda.permissions_boundary == var.permissions_boundary_arn && aws_iam_role.scheduler.permissions_boundary == var.permissions_boundary_arn
    error_message = "Both workload roles are created under the environment's boundary."
  }
}

run "staging_roles_carry_the_staging_boundary" {
  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
    permissions_boundary_arn  = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
  }

  assert {
    condition     = aws_iam_role.lambda.permissions_boundary == "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary" && aws_iam_role.scheduler.permissions_boundary == "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
    error_message = "Both workload roles are created under the environment's boundary."
  }
}

run "production_refuses_stagings_boundary" {
  command = plan

  variables {
    permissions_boundary_arn = "arn:aws:iam::123456789012:policy/weather-story-bot-staging-boundary"
  }

  expect_failures = [var.permissions_boundary_arn]
}

run "staging_refuses_productions_boundary" {
  command = plan

  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  expect_failures = [var.permissions_boundary_arn]
}
