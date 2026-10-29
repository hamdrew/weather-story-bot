variable "github_subject_prefix" {
  description = "The OIDC subject prefix of the repository whose workflows may assume the CI roles: its sub_claim_prefix, from gh api repos/<owner>/<name>/actions/oidc/customization/sub."
  type        = string

  # Immutable subjects only (repo:<owner>@<owner id>/<name>@<repository id>): they still match after
  # a rename, and a repository recreated under the same name can't match. The name-only form is
  # refused, because this repository's tokens never carry it.
  validation {
    condition     = can(regex("^repo:[A-Za-z0-9-]+@[0-9]+/[A-Za-z0-9_.-]+@[0-9]+$", var.github_subject_prefix))
    error_message = "github_subject_prefix must be the repository's immutable sub_claim_prefix, repo:<owner>@<owner id>/<name>@<repository id>."
  }
}

variable "state_bucket" {
  description = "The S3 bucket that holds every stack's Terraform state."
  type        = string
}

variable "region" {
  description = "AWS region of the main stack's resources (and of this stack). The boundaries' ARNs use it, so it must equal the main stack's region."
  type        = string
  default     = "us-east-2"
}
