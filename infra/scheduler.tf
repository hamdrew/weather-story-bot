resource "aws_scheduler_schedule" "bot" {
  #checkov:skip=CKV_AWS_297:The schedule carries no input and nothing sensitive, so the default AWS owned key is enough
  name                = local.name
  description         = "Check for new NWS Weather Stories"
  schedule_expression = var.schedule_expression
  state               = "DISABLED"

  # Every environment's schedule is created DISABLED. `state` is only the initial value: make start / make pause
  # toggle it through the API (scripts/set_run_state.py), and a later apply must not flip it back.
  lifecycle {
    ignore_changes = [state]
  }

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.bot.arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}
