variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "offices" {
  description = "NWS offices to watch, keyed by office id (e.g. MKX), each with its Telegram channel."
  type = map(object({
    chat_id = string
    name    = string
  }))

  validation {
    condition     = length(var.offices) > 0 && alltrue([for id in keys(var.offices) : can(regex("^[A-Z]{3}$", id))])
    error_message = "offices must be non-empty and keyed by three-letter uppercase office ids, e.g. MKX."
  }
}

variable "telegram_token_param_name" {
  description = "Name of the SecureString SSM parameter holding the Telegram bot token (created manually)."
  type        = string
  default     = "/weather-story-bot/telegram-token"
}

variable "nws_user_agent" {
  description = "User-Agent sent to api.weather.gov. NWS asks for app name plus contact info."
  type        = string
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression for how often to check for stories."
  type        = string
  default     = "rate(15 minutes)"
}

variable "lambda_zip_path" {
  description = "Path to the deployment package built by `make build`."
  type        = string
  default     = "../build/lambda.zip"
}
