# The apply roles and the per-environment permissions boundaries: each environment's role reaches
# only its own resources, can't delete the table, bucket or objects, and can create roles only
# under its own boundary. Runs offline against a mock provider.

mock_provider "aws" {
  # Resources validate the policy JSON they are given, and a mock would generate a random string.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{}"
    }
  }

  # An attachment validates the ARN it is given.
  mock_resource "aws_iam_policy" {
    defaults = {
      arn = "arn:aws:iam::123456789012:policy/mock"
    }
  }
}

override_data {
  target = data.aws_caller_identity.current
  values = {
    account_id = "123456789012"
  }
}

variables {
  github_repository = "octo/weather-story-bot"
  state_bucket      = "state-bucket"
}

run "the_staging_role_names_only_staging_resources" {
  assert {
    condition = alltrue(flatten([
      for s in({ for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) })["staging"] : [
        for r in s.resources : strcontains(r, "staging")
      ] if s.effect == "Allow" && !contains(["NoResourceLevelReads", "StateList"], s.sid)
    ]))
    error_message = "Every staging resource must name staging: no production ARN or state key."
  }
}

run "the_production_role_uses_exact_names" {
  assert {
    condition = alltrue(flatten([
      for s in({ for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) })["production"] : [
        for r in s.resources : !strcontains(r, "staging") && !strcontains(r, "weather-story-bot*")
      ] if s.effect == "Allow" && !contains(["NoResourceLevelReads", "StateList"], s.sid)
    ]))
    error_message = "Production's names are a prefix of staging's, so its ARNs must be exact and never match staging."
  }
}

run "each_role_reads_and_writes_only_its_own_state" {
  assert {
    condition = jsonencode({
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : env => sort(tolist(one([for s in d : s.resources if s.sid == "State"])))
      }) == jsonencode({
      "staging"    = ["arn:aws:s3:::state-bucket/weather-story-bot/staging/terraform.tfstate", "arn:aws:s3:::state-bucket/weather-story-bot/staging/terraform.tfstate.tflock"]
      "production" = ["arn:aws:s3:::state-bucket/weather-story-bot/terraform.tfstate", "arn:aws:s3:::state-bucket/weather-story-bot/terraform.tfstate.tflock"]
    })
    error_message = "Each apply role holds its own state key and its own .tflock."
  }

  assert {
    condition = jsonencode({
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : env => tolist(one([for s in d : s.resources if s.sid == "StateLock"]))
      }) == jsonencode({
      "staging"    = ["arn:aws:s3:::state-bucket/weather-story-bot/staging/terraform.tfstate.tflock"]
      "production" = ["arn:aws:s3:::state-bucket/weather-story-bot/terraform.tfstate.tflock"]
    })
    error_message = "The only object a role may delete is its own lock file."
  }
}

run "zips_go_under_the_environments_own_prefix" {
  assert {
    condition = jsonencode({
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : env => tolist(one([for s in d : s.resources if s.sid == "Zips"]))
      }) == jsonencode({
      "staging"    = ["arn:aws:s3:::weather-story-bot-artifacts-123456789012/staging/lambda/*"]
      "production" = ["arn:aws:s3:::weather-story-bot-artifacts-123456789012/production/lambda/*"]
    })
    error_message = "Each apply role writes only its own prefix."
  }

  assert {
    condition = jsonencode({
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : env => length([for s in d : s if s.sid == "Plans"])
    }) == jsonencode({ "staging" = 0, "production" = 1 })
    error_message = "Only production reads saved plans."
  }

  assert {
    condition     = toset(one([for s in({ for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) })["production"] : s.resources if s.sid == "Plans"])) == toset(["arn:aws:s3:::weather-story-bot-artifacts-123456789012/plans/production/*"])
    error_message = "Production reads plans/production/* and nothing else."
  }
}

run "the_table_the_archive_and_their_objects_cannot_be_deleted" {
  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } :
      length([for s in d : s if s.sid == "DenyDeletes" && s.effect == "Deny"]) == 1
    ])
    error_message = "Both apply roles carry the explicit Deny."
  }

  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : alltrue([
        for a in ["dynamodb:DeleteTable", "s3:DeleteBucket", "s3:DeleteObject", "s3:DeleteObjectVersion"] :
        contains(flatten([for s in d : tolist(s.actions) if s.sid == "DenyDeletes"]), a)
      ])
    ])
    error_message = "The Deny must cover DeleteTable, DeleteBucket and DeleteObject*."
  }

  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : !anytrue([
        for s in d : anytrue([for a in s.actions : contains(["dynamodb:DeleteTable", "s3:DeleteBucket"], a)]) if s.effect == "Allow"
      ])
    ])
    error_message = "Nothing may Allow the deletions the Deny forbids."
  }
}

run "roles_are_created_and_changed_only_under_the_environments_boundary" {
  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : alltrue([
        for a in ["iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy"] :
        length([
          for s in d : s if contains(s.actions, a) && anytrue([
            for c in s.condition : c.test == "StringEquals" && c.variable == "iam:PermissionsBoundary" && toset(c.values) == toset([local.boundary_arns[env]])
          ])
        ]) == 1
      ])
    ])
    error_message = "CreateRole, PutRolePolicy and AttachRolePolicy each need iam:PermissionsBoundary pinned to the role's own boundary."
  }

  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : !anytrue([
        for s in d : anytrue([
          for a in s.actions : can(regex("^iam:.*(PermissionsBoundary|Policy|PolicyVersion)$", a)) && !contains(["iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:GetRolePolicy", "iam:UpdateAssumeRolePolicy"], a)
        ])
      ])
    ])
    error_message = "Nothing may change or delete a boundary: no policy or permissions-boundary actions beyond the role's own policies."
  }

  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : alltrue([
        for s in d : contains(s.actions, "iam:PassRole") ? anytrue([
          for c in s.condition : c.variable == "iam:PassedToService" && toset(c.values) == toset(["lambda.amazonaws.com", "scheduler.amazonaws.com"])
        ]) : true
      ])
    ])
    error_message = "PassRole must be limited with iam:PassedToService."
  }
}

run "tag_writes_pin_the_request_tag_and_work_at_create_time" {
  assert {
    condition = alltrue(flatten([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : [
        for s in d : [
          anytrue([for c in s.condition : c.variable == "aws:RequestTag/Environment" && c.test == "StringEquals" && toset(c.values) == toset([env])]),
          anytrue([for c in s.condition : c.variable == "aws:TagKeys"]),
        ] if anytrue([for a in s.actions : can(regex(":Tag(Resource|Role)$", a))])
      ]
    ]))
    error_message = "A tag-write action must pin Environment on aws:RequestTag to the role's own environment and limit aws:TagKeys."
  }

  # Creating a resource with tags also authorizes the tag action on it, and a resource that doesn't
  # exist yet has no tags: a ResourceTag condition would deny every create.
  assert {
    condition = !anytrue(flatten([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : [
        for s in d : anytrue([for c in s.condition : startswith(c.variable, "aws:ResourceTag/")])
        if anytrue([for a in s.actions : can(regex(":Tag(Resource|Role)$", a))])
      ]
    ]))
    error_message = "A tag-write action must not require aws:ResourceTag, or creating a tagged resource is denied."
  }

  assert {
    condition = !anytrue(flatten([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : [for s in d : [for a in s.actions : can(regex(":Untag", a))] if s.effect == "Allow"]
    ]))
    error_message = "Untag requests carry no aws:RequestTag, so no Untag action can be granted under the tag conditions."
  }

  assert {
    condition = alltrue(flatten([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : [
        for s in d : anytrue([for c in s.condition : c.variable == "aws:RequestTag/Environment" && toset(c.values) == toset([env])])
        if anytrue([for a in s.actions : can(regex(":Create(Function|Table|Role|Topic|LogGroup|Bucket)$", a))])
      ]
    ]))
    error_message = "Creates must carry the environment in aws:RequestTag."
  }
}

run "an_existing_alarm_can_be_changed" {
  # PutMetricAlarm both creates and updates, and an update may send no tags.
  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : anytrue([
        for s in d : contains(s.actions, "cloudwatch:PutMetricAlarm") && anytrue([
          for c in s.condition : c.variable == "aws:ResourceTag/Environment" && toset(c.values) == toset([env])
        ])
      ])
    ])
    error_message = "PutMetricAlarm must also be allowed on an existing alarm by its Environment tag."
  }
}

run "the_undo_windows_cannot_be_turned_off" {
  # infra/data-retention: expiring the archive, suspending its versioning or turning off PITR would
  # undo the delete Deny by other means. Those changes go through the laptop with MFA.
  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : alltrue([
        for a in ["s3:PutLifecycleConfiguration", "s3:PutBucketVersioning", "dynamodb:UpdateContinuousBackups"] :
        anytrue([for s in d : contains(s.actions, a) && s.effect == "Deny"])
      ])
    ])
    error_message = "Both apply roles must Deny lifecycle, versioning and PITR changes on the archive and tables."
  }

  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : !anytrue([
        for s in d : anytrue([for a in s.actions : contains(["s3:PutLifecycleConfiguration", "s3:PutBucketVersioning", "dynamodb:UpdateContinuousBackups"], a)]) if s.effect == "Allow"
      ])
    ])
    error_message = "Nothing may Allow the retention changes the Deny forbids."
  }
}

run "no_bucket_pattern_can_reach_an_object" {
  assert {
    condition = alltrue(flatten([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } : [
        for s in d : [
          for r in s.resources : !strcontains(r, "*") if startswith(r, "arn:aws:s3:::") && !strcontains(r, "/")
        ] if s.effect == "Allow"
      ]
    ]))
    error_message = "An allowed bucket ARN must be exact: in IAM a pattern also matches the bucket's objects."
  }
}

run "the_function_can_set_its_reserved_concurrency" {
  assert {
    condition = alltrue([
      for env, d in { for env in ["staging", "production"] : env => flatten([for k, doc in data.aws_iam_policy_document.apply : doc.statement if startswith(k, "${env}-")]) } :
      contains(flatten([for s in d : tolist(s.actions)]), "lambda:PutFunctionConcurrency")
    ])
    error_message = "The Lambda's reserved concurrency (lambda_max_concurrency) needs PutFunctionConcurrency."
  }
}

run "boundaries_differ_and_are_named_per_environment" {
  assert {
    condition = jsonencode({
      for env, p in aws_iam_policy.boundary : env => p.name
      }) == jsonencode({
      "staging"    = "weather-story-bot-staging-boundary"
      "production" = "weather-story-bot-boundary"
    })
    error_message = "A boundary per environment, named from the environment's name."
  }

  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.boundary["staging"].statement : [for r in s.resources : strcontains(r, "weather-story-bot-staging")]
    ]))
    error_message = "The staging boundary must name only staging ARNs, or a staging role could be granted production's table."
  }

  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.boundary["production"].statement : [
        for r in s.resources : !strcontains(r, "staging") && !strcontains(r, "*weather") && !strcontains(r, "bot*")
      ]
    ]))
    error_message = "The production boundary must use exact names."
  }

  assert {
    condition = jsonencode({
      for env, d in data.aws_iam_policy_document.boundary : env => sort([for s in d.statement : s.sid])
      }) == jsonencode({
      "staging"    = ["Archive", "Invoke", "Logs", "State", "TelegramToken"]
      "production" = ["Archive", "Invoke", "Logs", "State", "TelegramToken"]
    })
    error_message = "A boundary covers exactly what the Lambda and Scheduler roles do."
  }

  assert {
    condition = jsonencode({
      for env, d in data.aws_iam_policy_document.boundary : env => tolist(one([for s in d.statement : s.resources if s.sid == "TelegramToken"]))
      }) == jsonencode({
      "staging"    = ["arn:aws:ssm:us-east-2:123456789012:parameter/weather-story-bot-staging/telegram-token"]
      "production" = ["arn:aws:ssm:us-east-2:123456789012:parameter/weather-story-bot/telegram-token"]
    })
    error_message = "Each boundary reaches its own environment's token parameter only."
  }
}
