# GitHub's token issuer. One per account: if the account already has one, import it instead of
# creating a duplicate (README, Bootstrap).
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# One trust policy per role: the audience and an exact subject, both StringEquals. Never StringLike,
# so no other repository, fork, branch or environment can assume a role. The subject decides which
# job gets which role (infra/pipeline): pull requests get the read-only role, main gets the
# plan role, and each apply role is assumable only from its own GitHub environment, which is where
# production's approval lives.
data "aws_iam_policy_document" "trust" {
  for_each = local.ci_roles

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = [each.value]
    }
  }
}

resource "aws_iam_role" "ci" {
  for_each = local.ci_roles

  name               = "weather-story-bot-ci-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.trust[each.key].json
}
