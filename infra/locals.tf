locals {
  production = var.environment == "production"
  # Production stays unsuffixed: renaming the table or bucket is a replace, which
  # infra/data-retention forbids. Every other environment is weather-story-bot-<env>.
  name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"

  # The provider's default_tags. Here rather than inline so tests/ can assert on them.
  default_tags = {
    Project   = local.name
    ManagedBy = "terraform"
    # What IAM tag conditions (aws:ResourceTag/Environment) match on. Tag values compare
    # case-sensitively, so it's always the lowercase var.environment, never a display name.
    Environment = var.environment
  }

  # Where mise run deploy uploads the zip and Lambda reads it: <env>/lambda/<sha256>.zip, so an apply
  # role writes only its own prefix and a key never holds two different zips. The hash is base64url
  # without padding, since "/" would nest the key and "+" and "=" are awkward in URLs and logs.
  lambda_s3_key = "${var.environment}/lambda/${replace(replace(trimsuffix(var.lambda_zip_sha256, "="), "+", "-"), "/", "_")}.zip"
}

data "aws_caller_identity" "current" {}
