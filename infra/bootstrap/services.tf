# What each service's resources need, shared by the plan roles (reads only) and the apply roles.
# Per service: read (describe/list/get), create (carries the request tags), manage (changes an
# existing resource, gated on its Environment tag) and tag (tag writes, gated on the request's tags).
# No Untag action: an untag request carries no aws:RequestTag, so the tag conditions could never allow it.
# `conditioned = false` marks a service with no tag condition keys (schedules and budgets).
locals {
  services = {
    lambda = {
      sid         = "Lambda"
      kind        = "function"
      conditioned = true
      read = [
        "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:GetFunctionCodeSigningConfig",
        "lambda:GetFunctionConcurrency", "lambda:GetFunctionEventInvokeConfig", "lambda:ListVersionsByFunction",
        "lambda:ListTags",
      ]
      create = ["lambda:CreateFunction"]
      manage = [
        "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration", "lambda:DeleteFunction",
        # The function's reserved concurrency (lambda_max_concurrency).
        "lambda:PutFunctionConcurrency", "lambda:DeleteFunctionConcurrency",
        "lambda:PutFunctionEventInvokeConfig", "lambda:UpdateFunctionEventInvokeConfig", "lambda:DeleteFunctionEventInvokeConfig",
      ]
      tag = ["lambda:TagResource"]
    }
    dynamodb = {
      sid         = "Table"
      kind        = "table"
      conditioned = true
      # Never an item action (GetItem, Query, Scan): a plan or apply role has no business with the ledger.
      read = [
        "dynamodb:DescribeTable", "dynamodb:DescribeContinuousBackups", "dynamodb:DescribeTimeToLive",
        "dynamodb:DescribeContributorInsights", "dynamodb:DescribeKinesisStreamingDestination", "dynamodb:ListTagsOfResource",
      ]
      create = ["dynamodb:CreateTable"]
      # No DeleteTable or UpdateContinuousBackups (both denied outright) and no UpdateTimeToLive
      # (records are permanent).
      manage = ["dynamodb:UpdateTable"]
      tag    = ["dynamodb:TagResource"]
    }
    s3 = {
      sid         = "Bucket"
      kind        = "bucket"
      conditioned = true
      # On the bucket ARN, never bucket/*: Get* here reads configuration and no object.
      read   = ["s3:Get*", "s3:List*"]
      create = ["s3:CreateBucket"]
      # No DeleteBucket, PutBucketVersioning or PutLifecycleConfiguration (denied outright) and no
      # bucket policy: nothing in the main stack sets one.
      manage = [
        "s3:PutBucketPublicAccessBlock",
        "s3:PutEncryptionConfiguration", "s3:PutBucketOwnershipControls", "s3:PutBucketABAC",
      ]
      tag = ["s3:TagResource"]
    }
    iam = {
      sid         = "Role"
      kind        = "role"
      conditioned = true
      read        = ["iam:GetRole", "iam:GetRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole"]
      # Create and manage hold the permissions boundary condition, so they are written out in apply.tf.
      create = []
      manage = []
      tag    = ["iam:TagRole"]
    }
    sns = {
      sid         = "Topic"
      kind        = "topic"
      conditioned = true
      read        = ["sns:GetTopicAttributes", "sns:ListTagsForResource", "sns:ListSubscriptionsByTopic", "sns:GetSubscriptionAttributes"]
      create      = ["sns:CreateTopic"]
      manage      = ["sns:SetTopicAttributes", "sns:DeleteTopic"]
      tag         = ["sns:TagResource"]
    }
    scheduler = {
      sid         = "Schedule"
      kind        = "schedule"
      conditioned = false
      read        = ["scheduler:GetSchedule"]
      create      = ["scheduler:CreateSchedule"]
      manage      = ["scheduler:UpdateSchedule", "scheduler:DeleteSchedule"]
      tag         = []
    }
    alarms = {
      sid         = "Alarm"
      kind        = "alarm"
      conditioned = true
      read        = ["cloudwatch:ListTagsForResource"]
      create      = ["cloudwatch:PutMetricAlarm"]
      # PutMetricAlarm also updates an existing alarm, and an update may send no tags.
      manage = ["cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms"]
      tag    = ["cloudwatch:TagResource"]
    }
    logs = {
      sid         = "LogGroup"
      kind        = "log_group"
      conditioned = true
      read        = ["logs:ListTagsForResource"]
      create      = ["logs:CreateLogGroup"]
      manage      = ["logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy", "logs:DeleteLogGroup", "logs:PutMetricFilter", "logs:DeleteMetricFilter"]
      tag         = ["logs:TagResource"]
    }
    budgets = {
      sid         = "Budget"
      kind        = "budget"
      conditioned = false
      read        = ["budgets:ViewBudget", "budgets:DescribeBudgetActionsForBudget", "budgets:ListTagsForResource"]
      create      = []
      manage      = ["budgets:ModifyBudget"]
      tag         = []
    }
    # The health dashboard. A dashboard has no tags, so it takes no tag condition and no tag action;
    # it is named like the alarms (staging by prefix, production exactly), and PutDashboard both
    # creates and updates it.
    dashboards = {
      sid         = "Dashboard"
      kind        = "dashboard"
      conditioned = false
      read        = ["cloudwatch:GetDashboard"]
      create      = ["cloudwatch:PutDashboard"]
      manage      = ["cloudwatch:PutDashboard", "cloudwatch:DeleteDashboards"]
      tag         = []
    }
  }

  # Actions with no resource-level permissions, so they can only be granted on *.
  no_resource_level_reads = ["cloudwatch:DescribeAlarms", "logs:DescribeLogGroups", "logs:DescribeMetricFilters"]

  # AWS requires * for PutCompositeAlarm, so it cannot be scoped to an alarm ARN or an Environment
  # tag. Staging can therefore rewrite production's two verdict composites, and a composite can carry
  # actions; the guard against that is that the dashboard's composites carry none (tested).
  no_resource_level_writes = ["cloudwatch:PutCompositeAlarm"]
}
