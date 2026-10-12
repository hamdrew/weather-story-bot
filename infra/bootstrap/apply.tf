# ci-apply-staging and ci-apply-production, one per environment, each assumable only from its own
# GitHub environment. An apply role reaches only its environment's resources: staging by name
# prefix, production by exact name (locals.tf), plus Environment tag conditions where the service
# supports them (the gaps are listed in infra/iam). Roles it creates or changes must carry the
# environment's own permissions boundary, and nothing here can change or delete a boundary.
locals {
  # Each environment's own Environment tag, which default_tags puts on everything it creates.
  tag_conditions = { for env in keys(local.environments) : env => {
    resource = { test = "StringEquals", variable = "aws:ResourceTag/Environment", values = [env] }
    request  = { test = "StringEquals", variable = "aws:RequestTag/Environment", values = [env] }
    # default_tags: exactly these three keys (infra/locals.tf).
    keys = { test = "ForAllValues:StringEquals", variable = "aws:TagKeys", values = ["Environment", "ManagedBy", "Project"] }
  } }

  apply_statements = { for env, e in local.environments : env => concat(
    [
      # Terraform's S3 backend: its own state object and its own lock file.
      {
        effect  = "Allow"
        sid     = "State"
        actions = ["s3:GetObject", "s3:PutObject"]
        resources = [
          "arn:aws:s3:::${var.state_bucket}/${e.state_key}",
          "arn:aws:s3:::${var.state_bucket}/${e.state_key}.tflock",
        ]
        conditions = []
      },
      # The one object a role may delete: its own lock file, released when an apply ends.
      {
        effect     = "Allow"
        sid        = "StateLock"
        actions    = ["s3:DeleteObject"]
        resources  = ["arn:aws:s3:::${var.state_bucket}/${e.state_key}.tflock"]
        conditions = []
      },
      # The backend checks the bucket exists. On the bucket ARN, so it lists key names and reads nothing.
      {
        effect     = "Allow"
        sid        = "StateList"
        actions    = ["s3:ListBucket"]
        resources  = ["arn:aws:s3:::${var.state_bucket}"]
        conditions = []
      },
      # Zips: written (once, the bucket policy refuses an overwrite) and read back by Lambda when it
      # creates or updates the function. Only this environment's prefix.
      {
        effect     = "Allow"
        sid        = "Zips"
        actions    = ["s3:PutObject", "s3:GetObject"]
        resources  = ["${local.artifacts_arn}/${env}/lambda/*"]
        conditions = []
      },
      {
        effect     = "Allow"
        sid        = "NoResourceLevelReads"
        actions    = local.no_resource_level_reads
        resources  = ["*"] # These actions support no resource-level permissions.
        conditions = []
      },
      # Roles: created and changed only under this environment's boundary, so a role the pipeline
      # makes can never be given more than the Lambda and Scheduler roles are allowed to do.
      {
        effect    = "Allow"
        sid       = "RoleCreate"
        actions   = ["iam:CreateRole"]
        resources = local.arns[env].role
        conditions = [
          local.tag_conditions[env].request,
          local.tag_conditions[env].keys,
          { test = "StringEquals", variable = "iam:PermissionsBoundary", values = [e.boundary_arn] },
        ]
      },
      {
        effect    = "Allow"
        sid       = "RolePolicies"
        actions   = ["iam:PutRolePolicy"]
        resources = local.arns[env].role
        conditions = [
          local.tag_conditions[env].resource,
          { test = "StringEquals", variable = "iam:PermissionsBoundary", values = [e.boundary_arn] },
        ]
      },
      {
        effect    = "Allow"
        sid       = "RoleAttach"
        actions   = ["iam:AttachRolePolicy"]
        resources = local.arns[env].role
        conditions = [
          local.tag_conditions[env].resource,
          { test = "StringEquals", variable = "iam:PermissionsBoundary", values = [e.boundary_arn] },
        ]
      },
      {
        effect     = "Allow"
        sid        = "RoleManage"
        actions    = ["iam:UpdateAssumeRolePolicy", "iam:DeleteRole", "iam:DeleteRolePolicy", "iam:DetachRolePolicy"]
        resources  = local.arns[env].role
        conditions = [local.tag_conditions[env].resource]
      },
      {
        effect    = "Allow"
        sid       = "RolePass"
        actions   = ["iam:PassRole"]
        resources = local.arns[env].role
        conditions = [
          { test = "StringEquals", variable = "iam:PassedToService", values = ["lambda.amazonaws.com", "scheduler.amazonaws.com"] },
        ]
      },
      # Subscribe and Unsubscribe take a subscription, which carries no tags, so no tag condition.
      {
        effect     = "Allow"
        sid        = "TopicSubscribe"
        actions    = ["sns:Subscribe", "sns:Unsubscribe"]
        resources  = local.arns[env].topic
        conditions = []
      },
    ],
    # Production reads the plan ci-plan saved, and nothing else under plans/.
    local.production_flags[env] ? [
      {
        effect     = "Allow"
        sid        = "Plans"
        actions    = ["s3:GetObject"]
        resources  = ["${local.artifacts_arn}/plans/production/*"]
        conditions = []
      },
    ] : [],
    # One statement per kind of access rather than per service: an action only ever matches a
    # resource of its own service, so merging them grants the same access in far less text, and the
    # role policy has to stay under IAM's 10,240-character inline limit. A tag condition applies to
    # every action in its statement, so services with no tag condition keys get their own statement.
    [
      {
        effect     = "Allow"
        sid        = "Reads"
        actions    = flatten([for svc, d in local.services : d.read])
        resources  = local.service_resources[env].all
        conditions = []
      },
      {
        effect     = "Allow"
        sid        = "Creates"
        actions    = flatten([for svc, d in local.services : d.create if d.conditioned])
        resources  = local.service_resources[env].conditioned
        conditions = [local.tag_conditions[env].request, local.tag_conditions[env].keys]
      },
      {
        effect     = "Allow"
        sid        = "Changes"
        actions    = flatten([for svc, d in local.services : d.manage if d.conditioned])
        resources  = local.service_resources[env].conditioned
        conditions = [local.tag_conditions[env].resource]
      },
      {
        effect  = "Allow"
        sid     = "Tags"
        actions = flatten([for svc, d in local.services : d.tag])
        # Only this environment's names, and only its own Environment value, so a role can't retag a
        # resource into another environment (infra/iam). No aws:ResourceTag: creating a tagged resource
        # also authorizes the tag action on it, and a resource that doesn't exist yet has no tags.
        resources  = local.service_resources[env].all
        conditions = [local.tag_conditions[env].request, local.tag_conditions[env].keys]
      },
      # Schedules and budgets have no tag condition keys (the gaps are listed in infra/iam).
      {
        effect     = "Allow"
        sid        = "WritesWithoutTagConditions"
        actions    = flatten([for svc, d in local.services : concat(d.create, d.manage) if !d.conditioned])
        resources  = local.service_resources[env].unconditioned
        conditions = []
      },
    ],
    [
      # infra/data-retention, enforced by IAM: the pipeline can never delete the table, the archive or
      # an object in it (or in the artifacts bucket, whose lifecycle rules do the expiring). Patterns
      # on purpose: the deny covers every environment, not only this role's own.
      {
        effect  = "Deny"
        sid     = "DenyDeletes"
        actions = ["dynamodb:DeleteTable", "s3:DeleteBucket", "s3:DeleteObject", "s3:DeleteObjectVersion"]
        resources = [
          "arn:aws:dynamodb:*:${local.account_id}:table/weather-story-bot*",
          "arn:aws:s3:::weather-story-bot*-archive-*",
          "arn:aws:s3:::weather-story-bot*-archive-*/*",
          local.artifacts_arn,
          "${local.artifacts_arn}/*",
        ]
        conditions = []
      },
      # The undo windows: expiring the archive, suspending its versioning or turning off PITR would
      # undo the deletes the Deny above forbids. These change only from the laptop with MFA, which
      # also means the pipeline can't create a new environment's table or archive.
      {
        effect  = "Deny"
        sid     = "DenyRetentionChanges"
        actions = ["dynamodb:UpdateContinuousBackups", "s3:PutBucketVersioning", "s3:PutLifecycleConfiguration"]
        resources = [
          "arn:aws:dynamodb:*:${local.account_id}:table/weather-story-bot*",
          "arn:aws:s3:::weather-story-bot*-archive-*",
        ]
        conditions = []
      },
    ],
  ) }

  # Every service's resource ARNs for this environment: all of them, and split by whether the
  # service supports tag conditions.
  service_resources = { for env in keys(local.environments) : env => {
    all           = distinct(flatten([for svc, d in local.services : local.arns[env][d.kind]]))
    conditioned   = distinct(flatten([for svc, d in local.services : local.arns[env][d.kind] if d.conditioned]))
    unconditioned = distinct(flatten([for svc, d in local.services : local.arns[env][d.kind] if !d.conditioned]))
  } }

  production_flags = { for env, e in local.environments : env => !e.prefix }
}

# One role policy would pass IAM's 10,240-character limit on inline policies, so each role gets
# three customer managed policies (6,144 characters each), grouped by what they do. Production's
# are about 3.2, 3.9 and 4.0 KB; a statement that pushes one over fails at apply, so move it to a
# lighter group (apply_group_of is exhaustive, so an unassigned statement fails the plan).
locals {
  apply_group_of = {
    State                      = "access"
    StateLock                  = "access"
    StateList                  = "access"
    Zips                       = "access"
    Plans                      = "access"
    NoResourceLevelReads       = "access"
    Reads                      = "access"
    RoleCreate                 = "roles-tags"
    RolePolicies               = "roles-tags"
    RoleAttach                 = "roles-tags"
    RoleManage                 = "roles-tags"
    RolePass                   = "roles-tags"
    TopicSubscribe             = "roles-tags"
    Creates                    = "writes"
    Changes                    = "writes"
    Tags                       = "roles-tags"
    WritesWithoutTagConditions = "writes"
    DenyDeletes                = "writes"
    DenyRetentionChanges       = "writes"
  }

  apply_policies = merge([
    for env in keys(local.environments) : {
      for group in ["access", "roles-tags", "writes"] : "${env}-${group}" => {
        env        = env
        group      = group
        statements = [for s in local.apply_statements[env] : s if local.apply_group_of[s.sid] == group]
      }
    }
  ]...)
}

data "aws_iam_policy_document" "apply" {
  for_each = local.apply_policies

  dynamic "statement" {
    for_each = each.value.statements

    content {
      effect    = statement.value.effect
      sid       = statement.value.sid
      actions   = statement.value.actions
      resources = statement.value.resources

      dynamic "condition" {
        for_each = statement.value.conditions

        content {
          test     = condition.value.test
          variable = condition.value.variable
          values   = condition.value.values
        }
      }
    }
  }
}

resource "aws_iam_policy" "apply" {
  for_each = local.apply_policies

  name   = "weather-story-bot-ci-apply-${each.key}"
  policy = data.aws_iam_policy_document.apply[each.key].json
}

resource "aws_iam_role_policy_attachment" "apply" {
  for_each = local.apply_policies

  role       = aws_iam_role.ci["apply-${each.value.env}"].name
  policy_arn = aws_iam_policy.apply[each.key].arn
}

# What this environment's Lambda and Scheduler roles may ever do, mirroring infra/iam.tf's role
# policies without the tag conditions. Exact names even for staging: a boundary written with a
# prefix pattern, next to a role policy the staging pipeline writes itself, could let the staging
# Lambda reach production's table. One boundary per environment, so staging can't.
data "aws_iam_policy_document" "boundary" {
  for_each = local.environments

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${each.value.name}:*"]
  }

  statement {
    sid       = "State"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"]
    resources = ["arn:aws:dynamodb:${var.region}:${local.account_id}:table/${each.value.name}-state"]
  }

  statement {
    sid       = "Archive"
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${each.value.name}-archive-${local.account_id}/stories/*"]
  }

  statement {
    sid       = "TelegramToken"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/${each.value.name}/telegram-token"]
  }

  statement {
    sid       = "Invoke"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${var.region}:${local.account_id}:function:${each.value.name}"]
  }
}

resource "aws_iam_policy" "boundary" {
  for_each = local.environments

  name        = "${each.value.name}-boundary"
  description = "Permissions boundary for ${each.key}'s Lambda and Scheduler roles"
  policy      = data.aws_iam_policy_document.boundary[each.key].json
}
