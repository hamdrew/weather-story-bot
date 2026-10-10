# The plan roles: one shared read policy that reads configuration and never data (no objects,
# items or parameters), and ci-plan's one write. Runs offline against a mock provider.

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

run "the_read_policy_has_no_data_access" {
  # Never an item read: a plan role could otherwise copy the state table's ledger.
  assert {
    condition = !anytrue([
      for s in data.aws_iam_policy_document.plan_read.statement : anytrue([
        for a in s.actions : can(regex("^dynamodb:(Get|Query|Scan|BatchGet)", a))
      ])
    ])
    error_message = "The read policy must not read table items."
  }

  # ReadOnlyAccess includes ssm:GetParameter, and the aws/ssm key lets any principal decrypt: that would leak the token.
  assert {
    condition = !anytrue([
      for s in data.aws_iam_policy_document.plan_read.statement : anytrue([
        for a in s.actions : startswith(a, "ssm:") || startswith(a, "kms:")
      ])
    ])
    error_message = "The read policy must grant nothing in ssm or kms."
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.plan_read.statement : alltrue([
        for a in s.actions : a != "*" && !endswith(a, ":*")
      ])
    ])
    error_message = "No service-wide or global wildcard actions."
  }

  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.plan_read.statement : alltrue([
        for r in s.resources : !endswith(r, "/*") || startswith(r, "arn:aws:logs:")
      ])
    ])
    error_message = "Only bucket ARNs, never bucket/*, so no object is readable. (Log group ARNs end in :* and are not objects.)"
  }
}

run "the_read_policy_reads_only_the_two_state_objects" {
  assert {
    condition = jsonencode(tolist(one([
      for s in data.aws_iam_policy_document.plan_read.statement : s.resources if s.sid == "State"
      ]))) == jsonencode([
      "arn:aws:s3:::state-bucket/weather-story-bot/staging/terraform.tfstate",
      "arn:aws:s3:::state-bucket/weather-story-bot/terraform.tfstate",
    ])
    error_message = "The plan roles read the two state objects and nothing else under the state bucket."
  }

  assert {
    condition = toset(one([
      for s in data.aws_iam_policy_document.plan_read.statement : s.actions if s.sid == "State"
    ])) == toset(["s3:GetObject"])
    error_message = "State is read, never written, by the plan roles."
  }
}

run "the_read_policy_reads_the_archive_buckets_configuration_not_objects" {
  assert {
    condition = alltrue([
      for s in data.aws_iam_policy_document.plan_read.statement : alltrue([
        for r in s.resources : !can(regex("archive[^/]*/", r))
      ])
    ])
    error_message = "No statement may name an object in an archive bucket."
  }
}

run "ci_plan_writes_only_the_production_plans_prefix" {
  assert {
    condition     = toset(one(data.aws_iam_policy_document.plan_write.statement).actions) == toset(["s3:PutObject"])
    error_message = "ci-plan's extra permission is one PutObject."
  }

  assert {
    condition     = toset(one(data.aws_iam_policy_document.plan_write.statement).resources) == toset(["arn:aws:s3:::weather-story-bot-artifacts-123456789012/plans/production/*"])
    error_message = "ci-plan writes only plans/production/*."
  }
}

run "only_ci_plan_gets_the_write_policy" {
  assert {
    condition     = jsonencode(keys(aws_iam_role_policy.plan_write)) == jsonencode(["plan"])
    error_message = "ci-pr-plan must stay read-only."
  }

  assert {
    condition     = jsonencode(keys(aws_iam_role_policy.plan_read)) == jsonencode(["plan", "pr-plan"])
    error_message = "Both plan roles share the read policy."
  }
}

run "no_bucket_pattern_can_reach_an_object" {
  # In IAM, * also matches /, so a wildcard bucket ARN paired with s3:Get* reads its objects too.
  assert {
    condition = alltrue(flatten([
      for s in data.aws_iam_policy_document.plan_read.statement : [
        for r in s.resources : !strcontains(r, "*") if startswith(r, "arn:aws:s3:::") && !strcontains(r, "/")
      ]
    ]))
    error_message = "A bucket ARN in the read policy must be exact: a pattern would also match the bucket's objects."
  }
}
