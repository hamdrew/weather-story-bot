# The Lambda role's policy: every statement stays on exact ARNs, the Environment tag conditions stay
# attached to them, and Logs has none (infra/iam). A mocked policy document's .json is a
# placeholder, so these assert on the document's inputs. Runs offline against a mock provider (see
# environments.tftest.hcl).

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
  lambda_zip_sha256         = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
}

run "production_lambda_policy_conditions_stay_on_exact_arns" {
  command = apply

  assert {
    condition     = toset([for s in data.aws_iam_policy_document.lambda.statement : s.sid]) == toset(["Logs", "State", "Archive", "TelegramToken"])
    error_message = "The Lambda role has exactly these four statements. Review a new one against infra/iam."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"]).resources) == toset(["arn:aws:dynamodb:us-east-2:123456789012:table/state-mock"])
    error_message = "State is granted on the state table's exact ARN, never on a wildcard or the MVP table."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "production"]]
    error_message = "State must stay conditioned on the production Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Archive"]).resources) == toset(["arn:aws:s3:::archive-mock/stories/*"])
    error_message = "Archive is granted on this environment's bucket, under stories/ only."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Archive"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "production"]]
    error_message = "Archive must stay conditioned on the production Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "TelegramToken"]).resources) == toset(["arn:aws:ssm:us-east-2:123456789012:parameter/weather-story-bot/telegram-token"])
    error_message = "TelegramToken is granted on this environment's own parameter ARN only."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "TelegramToken"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "production"]]
    error_message = "TelegramToken must stay conditioned on the production Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Logs"]).resources) == toset(["${aws_cloudwatch_log_group.lambda.arn}:*"])
    error_message = "Logs is granted on this function's log group only."
  }

  assert {
    condition     = length(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Logs"]).condition) == 0
    error_message = "Logs has no Environment tag condition: whether PutLogEvents evaluates log-group tags is unverified, and a wrong guess would lose logs."
  }

  assert {
    condition     = !anytrue(flatten([for s in data.aws_iam_policy_document.lambda.statement : [for a in s.actions : can(regex("Tag", a))]]))
    error_message = "The Lambda role must hold no tag-write action; a role that can retag could widen its own tag conditions."
  }

  assert {
    condition     = toset(flatten([for s in data.aws_iam_policy_document.lambda.statement : [for a in s.actions : a if can(regex("Delete", a))]])) == toset(["dynamodb:DeleteItem"])
    error_message = "The only delete the Lambda role may hold is DeleteItem, for the office lease."
  }
}

run "staging_lambda_policy_conditions_stay_on_exact_arns" {
  command = apply

  variables {
    environment               = "staging"
    telegram_token_param_name = "/weather-story-bot-staging/telegram-token"
  }

  assert {
    condition     = toset([for s in data.aws_iam_policy_document.lambda.statement : s.sid]) == toset(["Logs", "State", "Archive", "TelegramToken"])
    error_message = "The Lambda role has exactly these four statements. Review a new one against infra/iam."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"]).resources) == toset(["arn:aws:dynamodb:us-east-2:123456789012:table/state-mock"])
    error_message = "State is granted on the state table's exact ARN, never on a wildcard or the MVP table."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "staging"]]
    error_message = "State must stay conditioned on the staging Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Archive"]).resources) == toset(["arn:aws:s3:::archive-mock/stories/*"])
    error_message = "Archive is granted on this environment's bucket, under stories/ only."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Archive"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "staging"]]
    error_message = "Archive must stay conditioned on the staging Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "TelegramToken"]).resources) == toset(["arn:aws:ssm:us-east-2:123456789012:parameter/weather-story-bot-staging/telegram-token"])
    error_message = "TelegramToken is granted on this environment's own parameter ARN only."
  }

  assert {
    condition     = [for c in one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "TelegramToken"]).condition : [c.test, c.variable, join(",", c.values)]] == [["StringEquals", "aws:ResourceTag/Environment", "staging"]]
    error_message = "TelegramToken must stay conditioned on the staging Environment tag with StringEquals."
  }

  assert {
    condition     = toset(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Logs"]).resources) == toset(["${aws_cloudwatch_log_group.lambda.arn}:*"])
    error_message = "Logs is granted on this function's log group only."
  }

  assert {
    condition     = length(one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "Logs"]).condition) == 0
    error_message = "Logs has no Environment tag condition: whether PutLogEvents evaluates log-group tags is unverified, and a wrong guess would lose logs."
  }

  assert {
    condition     = !anytrue(flatten([for s in data.aws_iam_policy_document.lambda.statement : [for a in s.actions : can(regex("Tag", a))]]))
    error_message = "The Lambda role must hold no tag-write action; a role that can retag could widen its own tag conditions."
  }

  assert {
    condition     = toset(flatten([for s in data.aws_iam_policy_document.lambda.statement : [for a in s.actions : a if can(regex("Delete", a))]])) == toset(["dynamodb:DeleteItem"])
    error_message = "The only delete the Lambda role may hold is DeleteItem, for the office lease."
  }
}
