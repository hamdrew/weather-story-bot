# Passed by the Makefile from ENV (-var environment=...), never set in a tfvars file, so it can't
# disagree with the backend config the same ENV selects.
variable "environment" {
  description = "Deployment environment: production or staging. Selects names, the token parameter and the metric namespace."
  type        = string

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "environment must be production or staging."
  }
}

variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-2"
}

variable "offices" {
  description = "NWS offices to watch, keyed by office id (e.g. MKX), each with its Telegram channel."
  type = map(object({
    chat_id = string
    name    = string
  }))
  # The repo is public and so are its Actions logs, and a plan prints variable values.
  sensitive = true

  validation {
    condition     = length(var.offices) > 0 && alltrue([for id in keys(var.offices) : can(regex("^[A-Z]{3}$", id))])
    error_message = "offices must be non-empty and keyed by three-letter uppercase office ids, e.g. MKX."
  }
}

variable "telegram_token_param_name" {
  description = "Name of the SecureString SSM parameter holding this environment's Telegram bot token (created manually), e.g. /weather-story-bot/telegram-token."
  type        = string

  # Each environment has its own bot, and its parameter lives under that environment's name. The
  # prefixes can't overlap (/weather-story-bot/ vs /weather-story-bot-staging/), so no
  # environment's role can be granted another's token.
  validation {
    condition     = startswith(var.telegram_token_param_name, "/${local.name}/")
    error_message = "telegram_token_param_name must be under this environment's own prefix, /${local.name}/."
  }
}

variable "nws_user_agent" {
  description = "User-Agent sent to api.weather.gov. NWS asks for app name plus contact info."
  type        = string
  sensitive   = true # Contact info, and plans print in public logs.
}

# Keep the interval longer than state.LEASE_DURATION (360s), or a crashed run's lease blocks the next run.
variable "schedule_expression" {
  description = "EventBridge Scheduler expression for how often to check for stories."
  type        = string
  default     = "rate(15 minutes)"
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm and AWS Budget alerts."
  type        = string
  sensitive   = true # Plans print in public logs.
}

variable "monthly_budget_usd" {
  description = "Monthly AWS spend (whole account) that triggers budget alerts."
  type        = number
  default     = 5
}

variable "quiet_alarm_days" {
  description = "Alarm when no stories are posted for this many days in a row."
  type        = number
  default     = 2

  validation {
    # CloudWatch evaluates at most 7 days for alarms with periods of 1 hour or longer.
    condition     = var.quiet_alarm_days >= 1 && var.quiet_alarm_days <= 7 && floor(var.quiet_alarm_days) == var.quiet_alarm_days
    error_message = "quiet_alarm_days must be a whole number from 1 to 7."
  }
}

variable "repost_alarm_max_posts" {
  description = "Alarm when more than this many stories are posted within 3 hours."
  type        = number
  default     = 8
}

variable "lambda_max_concurrency" {
  description = "Most runs of the function at once (reserved concurrency). A ceiling on spend from a retry storm or a runaway invoker, not mutual exclusion: the office lease does that."
  type        = number
  default     = 10

  validation {
    # Reserved concurrency of 0 throttles every invocation, which switches the function off.
    condition     = var.lambda_max_concurrency >= 1 && floor(var.lambda_max_concurrency) == var.lambda_max_concurrency
    error_message = "lambda_max_concurrency must be a whole number of at least 1; 0 would switch the function off."
  }
}

variable "lambda_zip_path" {
  description = "Path to the deployment package built by `make build`."
  type        = string
  default     = "../build/lambda.zip"
}

# Passed by `make plan` from the zip it just built (build/lambda.zip.sha256), never set in a tfvars
# file. Terraform takes it as a plain input instead of hashing the file itself, so a plan is
# made for one exact build, and `make deploy` refuses to apply it if the rebuilt zip differs.
variable "lambda_zip_sha256" {
  description = "Base64 sha256 of the zip at lambda_zip_path, as printed by scripts/build_zip.py."
  type        = string

  validation {
    # 32 bytes in base64 is 43 characters and one "=", so an empty or truncated value is refused.
    condition     = can(regex("^[A-Za-z0-9+/]{43}=$", var.lambda_zip_sha256))
    error_message = "lambda_zip_sha256 must be a base64 sha256, as printed by scripts/build_zip.py."
  }
}
