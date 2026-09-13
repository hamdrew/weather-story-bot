resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 30
}

resource "aws_lambda_function" "bot" {
  function_name    = local.name
  description      = "Posts new NWS Weather Stories to Telegram"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "weather_story_bot.handler.lambda_handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = 256
  timeout          = 300

  environment {
    variables = {
      OFFICES_JSON         = jsonencode(var.offices)
      STATE_TABLE          = aws_dynamodb_table.posted.name
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
