# The OIDC provider and the four CI roles' trust policies: the audience and an exact subject, never
# a pattern, so a fork or another branch can't assume a role. Runs offline against a mock provider.

mock_provider "aws" {
  # Resources validate the policy JSON they are given, and a mock would generate a random string.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }

  # An attachment validates the ARN it is given.
  mock_resource "aws_iam_policy" {
    defaults = {
      arn = "arn:aws:iam::123456789012:policy/mock"
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
  github_repository = "octo/weather-story-bot"
  state_bucket      = "state-bucket"
}

run "oidc_provider_is_githubs_with_the_sts_audience" {
  assert {
    condition     = aws_iam_openid_connect_provider.github.url == "https://token.actions.githubusercontent.com"
    error_message = "The provider must be GitHub's token issuer."
  }

  assert {
    condition     = aws_iam_openid_connect_provider.github.client_id_list == toset(["sts.amazonaws.com"])
    error_message = "Only the sts.amazonaws.com audience may be accepted."
  }
}

run "the_four_ci_roles_exist" {
  assert {
    condition = jsonencode({ for k, r in aws_iam_role.ci : k => r.name }) == jsonencode({
      "pr-plan"          = "weather-story-bot-ci-pr-plan"
      "plan"             = "weather-story-bot-ci-plan"
      "apply-staging"    = "weather-story-bot-ci-apply-staging"
      "apply-production" = "weather-story-bot-ci-apply-production"
    })
    error_message = "There must be exactly the four CI roles."
  }
}

run "each_trust_policy_pins_the_audience_and_an_exact_subject" {
  assert {
    condition = jsonencode({
      for k, d in data.aws_iam_policy_document.trust : k => tolist(one([
        for c in one(d.statement).condition : c.values if c.variable == "token.actions.githubusercontent.com:sub"
      ]))
      }) == jsonencode({
      "pr-plan"          = ["repo:octo/weather-story-bot:pull_request"]
      "plan"             = ["repo:octo/weather-story-bot:ref:refs/heads/main"]
      "apply-staging"    = ["repo:octo/weather-story-bot:environment:staging"]
      "apply-production" = ["repo:octo/weather-story-bot:environment:production"]
    })
    error_message = "Each role's subject must be exact and name this repository."
  }

  assert {
    condition = alltrue([
      for k, d in data.aws_iam_policy_document.trust : toset(one([
        for c in one(d.statement).condition : c.values if c.variable == "token.actions.githubusercontent.com:aud"
      ])) == toset(["sts.amazonaws.com"])
    ])
    error_message = "Every trust policy must pin the sts.amazonaws.com audience."
  }

  assert {
    condition = alltrue([
      for k, d in data.aws_iam_policy_document.trust :
      length(one(d.statement).condition) == 2 && alltrue([for c in one(d.statement).condition : c.test == "StringEquals"])
    ])
    error_message = "Trust conditions must be exactly aud and sub, both StringEquals, never StringLike."
  }

  assert {
    condition = alltrue([
      for k, d in data.aws_iam_policy_document.trust :
      toset(one(d.statement).actions) == toset(["sts:AssumeRoleWithWebIdentity"])
    ])
    error_message = "The roles are assumed only with a web identity."
  }
}

run "the_repository_variable_is_validated" {
  command = plan

  variables {
    github_repository = "not-a-repository"
  }

  expect_failures = [var.github_repository]
}
