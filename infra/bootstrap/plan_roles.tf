# ci-pr-plan (pull requests) and ci-plan (main) share one read policy. It reads configuration and
# never data: Describe/List/Get per service on the project's ARNs only, with no GetItem, Query or
# Scan and nothing in ssm. ReadOnlyAccess would include ssm:GetParameter, and the aws/ssm key lets
# any principal in the account decrypt it, which would hand the Telegram token to a pull request.
# Granting s3:Get* on a bucket ARN (never bucket/*) reads the bucket's configuration without
# reading an object. This is the scoped exception to "exact actions" in infra/iam.
locals {
  plan_read_statements = concat(
    [
      {
        sid     = "State"
        actions = ["s3:GetObject"]
        # Exactly the two state objects. Plans run with -lock=false, so there is no lock file to read.
        resources = [for k in local.state_keys : "arn:aws:s3:::${var.state_bucket}/${k}"]
      },
      {
        sid       = "StateList"
        actions   = ["s3:ListBucket"]
        resources = ["arn:aws:s3:::${var.state_bucket}"]
      },
      {
        sid       = "NoResourceLevelReads"
        actions   = local.no_resource_level_reads
        resources = ["*"] # These actions support no resource-level permissions.
      },
    ],
    [
      for svc, d in local.services : {
        sid       = "${d.sid}Read"
        actions   = d.read
        resources = distinct(flatten([for env in keys(local.environments) : local.arns[env][d.kind]]))
      }
    ],
  )
}

data "aws_iam_policy_document" "plan_read" {
  dynamic "statement" {
    for_each = local.plan_read_statements

    content {
      sid       = statement.value.sid
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

# Only ci-plan, which runs on main, saves a plan: production's, for ci-apply-production to read after
# approval. A pull request's role can't write anywhere.
data "aws_iam_policy_document" "plan_write" {
  statement {
    sid       = "Plans"
    actions   = ["s3:PutObject"]
    resources = ["${local.artifacts_arn}/plans/production/*"]
  }
}

resource "aws_iam_role_policy" "plan_read" {
  for_each = toset(["pr-plan", "plan"])

  name   = "read"
  role   = aws_iam_role.ci[each.key].id
  policy = data.aws_iam_policy_document.plan_read.json
}

resource "aws_iam_role_policy" "plan_write" {
  for_each = toset(["plan"])

  name   = "write-plans"
  role   = aws_iam_role.ci[each.key].id
  policy = data.aws_iam_policy_document.plan_write.json
}
