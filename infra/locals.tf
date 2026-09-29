locals {
  production = var.environment == "production"
  # Production stays unsuffixed: renaming the table or bucket is a replace, which
  # infra/data-retention forbids. Every other environment is weather-story-bot-<env>.
  name = local.production ? "weather-story-bot" : "weather-story-bot-${var.environment}"

  # Non-production environments are invoked by hand (make invoke-staging), so their schedule is off
  # unless a tfvars file says otherwise.
  schedule_enabled = coalesce(var.schedule_enabled, local.production)
}

data "aws_caller_identity" "current" {}
