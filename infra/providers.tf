provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = local.name
      ManagedBy = "terraform"
      # What IAM tag conditions (aws:ResourceTag/Environment) match on. Tag values compare
      # case-sensitively, so it's always the lowercase var.environment, never a display name.
      Environment = var.environment
    }
  }
}
