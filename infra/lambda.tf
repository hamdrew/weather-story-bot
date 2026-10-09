resource "aws_cloudwatch_log_group" "lambda" {
  #checkov:skip=CKV_AWS_338:30 days is deliberate; retention is a cost decision (infra/budget)
  #checkov:skip=CKV_AWS_158:Logs hold no secrets (backend/secrets-in-errors) and a customer managed key costs $1/month
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 30
}

resource "aws_lambda_function" "bot" {
  #checkov:skip=CKV_AWS_50:The structured JSON logs are the trace, and X-Ray bills per trace
  #checkov:skip=CKV_AWS_117:A VPC needs a NAT gateway, which bills by the hour, to reach NWS and Telegram (infra/budget)
  #checkov:skip=CKV_AWS_116:Async retries are off; the next scheduled run is the retry (backend/retries)
  #checkov:skip=CKV_AWS_173:The variables hold no credentials (the token is in SSM) and a customer managed key costs $1/month
  #checkov:skip=CKV_AWS_272:No signing pipeline; the zip is built from this repo by make build and deployed only after a reviewed plan
  function_name    = local.name
  description      = "Posts new NWS Weather Stories to Telegram"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "weather_story_bot.handler.lambda_handler"
  filename         = var.lambda_zip_path
  source_code_hash = var.lambda_zip_sha256
  memory_size      = 256
  # A ceiling for runaway spend, well above what runs overlap (staggered schedules, a handful of
  # offices). Async invocations over it are throttled, which Lambda retries for up to 6 hours, so
  # a low ceiling delays a run and never drops one. Not mutual exclusion; the office lease does that.
  reserved_concurrent_executions = var.lambda_max_concurrency
  # state.LEASE_DURATION (360s) must stay longer than this, or a slow run's lease can expire mid-run.
  timeout = 300

  environment {
    variables = {
      OFFICES_JSON         = jsonencode(var.offices)
      STATE_TABLE          = aws_dynamodb_table.state.name
      ARCHIVE_BUCKET       = aws_s3_bucket.archive.bucket
      TELEGRAM_TOKEN_PARAM = var.telegram_token_param_name
      NWS_USER_AGENT       = var.nws_user_agent
    }
  }

  logging_config {
    # The handler formats its own JSON log lines.
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }

  depends_on = [aws_iam_role_policy.lambda]
}

# The next scheduled run is the retry; async retries would only repeat failures sooner.
resource "aws_lambda_function_event_invoke_config" "bot" {
  function_name          = aws_lambda_function.bot.function_name
  maximum_retry_attempts = 0
}
