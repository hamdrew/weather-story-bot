data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  # No Environment tag condition: whether PutLogEvents evaluates log-group tags is unverified, and
  # a wrong guess would lose logs quietly, taking the metric-filter alarms with them.
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  # Only the state table. The MVP table is the rollback and the Lambda no longer touches it.
  # UpdateItem is history.py's last_seen_at on current-story items. DeleteItem is only the office
  # lease's release (state.OfficeLease); nothing else in the Lambda deletes.
  #
  # The Environment tag condition reads the table's own tag. DynamoDB supports aws:ResourceTag on
  # item actions only while the account's DynamoDB ABAC setting is on ("enabled by default for most
  # accounts", console Settings page only). If it's off, the table looks untagged and this Allow
  # fails closed.
  statement {
    sid       = "State"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.state.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }

  # PutObject on bucket/stories/* reads the bucket's tags, which S3 honours only with bucket ABAC on
  # (aws_s3_bucket_abac.archive).
  statement {
    sid       = "Archive"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.archive.arn}/stories/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }

  # SecureString uses the AWS managed aws/ssm key, whose key policy already allows decryption.
  # The Environment tag condition reads the parameter's own tags. Terraform doesn't manage the
  # parameter (the token stays out of state), so it is tagged by hand when it's created.
  statement {
    sid       = "TelegramToken"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${trimprefix(var.telegram_token_param_name, "/")}"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Environment"
      values   = [var.environment]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

# Built from local.name rather than aws_lambda_function.bot.arn: a reference to the function
# defers this data source to apply time on every code deploy, making the plan show the policy
# as "known after apply" even though it never changes.
data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:${local.name}"]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "${local.name}-scheduler"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
