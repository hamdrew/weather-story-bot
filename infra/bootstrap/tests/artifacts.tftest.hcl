# The artifacts bucket: private, TLS-only, never overwritten, and everything in it is derived data
# that may expire (infra/data-retention). Runs offline against a mock provider.

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

run "the_bucket_is_named_for_the_account_and_locked_down" {
  assert {
    condition     = aws_s3_bucket.artifacts.bucket == "weather-story-bot-artifacts-123456789012"
    error_message = "The bucket is named from the account."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.artifacts.block_public_acls,
      aws_s3_bucket_public_access_block.artifacts.block_public_policy,
      aws_s3_bucket_public_access_block.artifacts.ignore_public_acls,
      aws_s3_bucket_public_access_block.artifacts.restrict_public_buckets,
    ])
    error_message = "Public access must be blocked."
  }
}

run "a_put_without_if_none_match_is_denied" {
  assert {
    condition = length([
      for s in data.aws_iam_policy_document.artifacts_bucket.statement : s
      if s.effect == "Deny" && toset(s.actions) == toset(["s3:PutObject"]) && anytrue([
        for c in s.condition : c.test == "Null" && c.variable == "s3:if-none-match" && toset(c.values) == toset(["true"])
      ])
    ]) == 1
    error_message = "PutObject without If-None-Match must be denied, so an object is never overwritten."
  }
}

run "plain_http_is_denied" {
  assert {
    condition = length([
      for s in data.aws_iam_policy_document.artifacts_bucket.statement : s
      if s.effect == "Deny" && anytrue([
        for c in s.condition : c.test == "Bool" && c.variable == "aws:SecureTransport" && toset(c.values) == toset(["false"])
      ])
    ]) == 1
    error_message = "Requests that don't use TLS must be denied."
  }
}

run "derived_data_expires_on_its_own_schedules" {
  assert {
    condition = jsonencode({
      for r in aws_s3_bucket_lifecycle_configuration.artifacts.rule : r.id => one(r.expiration).days
      if contains(["expire-staging-zips", "expire-production-zips", "expire-plans"], r.id)
      }) == jsonencode({
      "expire-staging-zips"    = 90
      "expire-production-zips" = 90
      "expire-plans"           = 14
    })
    error_message = "Zips expire after 90 days and saved plans after 14."
  }

  assert {
    condition = jsonencode({
      for r in aws_s3_bucket_lifecycle_configuration.artifacts.rule : r.id => one(r.filter).prefix
      if contains(["expire-staging-zips", "expire-production-zips", "expire-plans"], r.id)
      }) == jsonencode({
      "expire-staging-zips"    = "staging/lambda/"
      "expire-production-zips" = "production/lambda/"
      "expire-plans"           = "plans/"
    })
    error_message = "Each expiry rule must apply to its own prefix."
  }

  assert {
    condition = one([
      for r in aws_s3_bucket_lifecycle_configuration.artifacts.rule : one(r.noncurrent_version_expiration).noncurrent_days
      if r.id == "expire-noncurrent-versions"
    ]) == 7
    error_message = "Noncurrent versions expire after 7 days."
  }
}
