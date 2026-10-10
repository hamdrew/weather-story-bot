variable "github_repository" {
  description = "The GitHub repository whose workflows may assume the CI roles, as owner/name."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be owner/name."
  }
}

variable "state_bucket" {
  description = "The S3 bucket that holds every stack's Terraform state."
  type        = string
}

variable "region" {
  description = "AWS region of the main stack's resources (and of this stack)."
  type        = string
  default     = "us-east-2"
}
