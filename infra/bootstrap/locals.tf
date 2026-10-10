data "aws_caller_identity" "current" {}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  oidc_host        = "token.actions.githubusercontent.com"
  artifacts_bucket = "weather-story-bot-artifacts-${local.account_id}"
  # Built from the name, not read from the resource: the policies stay readable in a plan and in tests.
  artifacts_arn = "arn:aws:s3:::${local.artifacts_bucket}"

  # Production is unsuffixed and staging is weather-story-bot-staging, so production's names are a
  # prefix of staging's (infra/environments). Staging therefore matches by prefix, which also
  # covers a resource added later, and production lists exact names: a pattern would match staging.
  environments = {
    staging = {
      name         = "weather-story-bot-staging"
      prefix       = true
      state_key    = "weather-story-bot/staging/terraform.tfstate"
      boundary_arn = "arn:aws:iam::${local.account_id}:policy/weather-story-bot-staging-boundary"
    }
    production = {
      name         = "weather-story-bot"
      prefix       = false
      state_key    = "weather-story-bot/terraform.tfstate"
      boundary_arn = "arn:aws:iam::${local.account_id}:policy/weather-story-bot-boundary"
    }
  }

  boundary_arns = { for env, e in local.environments : env => e.boundary_arn }

  # The GitHub OIDC subject each role is assumable from. Exact strings, never patterns.
  ci_roles = {
    "pr-plan"          = "repo:${var.github_repository}:pull_request"
    "plan"             = "repo:${var.github_repository}:ref:refs/heads/main"
    "apply-staging"    = "repo:${var.github_repository}:environment:staging"
    "apply-production" = "repo:${var.github_repository}:environment:production"
  }

  state_keys = [for env in ["staging", "production"] : local.environments[env].state_key]

  # What each environment's resources are called, as name patterns per kind.
  names = { for env, e in local.environments : env => {
    function = e.prefix ? ["${e.name}*"] : [e.name]
    role     = e.prefix ? ["${e.name}*"] : ["${e.name}-lambda", "${e.name}-scheduler"]
    table    = e.prefix ? ["${e.name}*"] : ["${e.name}-state", "${e.name}-posted"]
    # Exact even for staging: in IAM, * also matches /, so a bucket pattern beside s3:Get* would
    # read the archive's objects. The archive is the main stack's only bucket.
    bucket   = ["${e.name}-archive-${local.account_id}"]
    topic    = e.prefix ? ["${e.name}*"] : ["${e.name}-alerts"]
    schedule = e.prefix ? ["${e.name}*"] : [e.name]
    alarm = e.prefix ? ["${e.name}*"] : [
      for a in ["errors", "missed-runs", "quiet", "repost-loop", "nws-ambiguous"] : "${e.name}-${a}"
    ]
    log_group = e.prefix ? ["/aws/lambda/${e.name}*"] : ["/aws/lambda/${e.name}"]
    # Production only: the budget covers the whole account (infra/environments).
    budget = e.prefix ? [] : ["${e.name}-monthly"]
  } }

  arns = { for env, n in local.names : env => {
    function = [for x in n.function : "arn:aws:lambda:${var.region}:${local.account_id}:function:${x}"]
    role     = [for x in n.role : "arn:aws:iam::${local.account_id}:role/${x}"]
    table    = [for x in n.table : "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${x}"]
    bucket   = [for x in n.bucket : "arn:aws:s3:::${x}"]
    # A subscription's ARN is the topic's plus an id.
    topic    = flatten([for x in n.topic : ["arn:aws:sns:${var.region}:${local.account_id}:${x}", "arn:aws:sns:${var.region}:${local.account_id}:${x}:*"]])
    schedule = [for x in n.schedule : "arn:aws:scheduler:${var.region}:${local.account_id}:schedule/default/${x}"]
    alarm    = [for x in n.alarm : "arn:aws:cloudwatch:${var.region}:${local.account_id}:alarm:${x}"]
    # A log group's ARN is used with and without the trailing :* depending on the action.
    log_group = flatten([for x in n.log_group : ["arn:aws:logs:${var.region}:${local.account_id}:log-group:${x}", "arn:aws:logs:${var.region}:${local.account_id}:log-group:${x}:*"]])
    budget    = [for x in n.budget : "arn:aws:budgets::${local.account_id}:budget/${x}"]
  } }
}
