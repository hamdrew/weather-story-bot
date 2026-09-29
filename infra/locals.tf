locals {
  production = var.environment == "production"
  # Production stays unsuffixed: renaming the table or bucket is a replace, which
  # infra/data-retention forbids. Every other environment is weather-story-bot-<env>.
  name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"
}

data "aws_caller_identity" "current" {}
