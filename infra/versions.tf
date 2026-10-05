terraform {
  # use_lockfile (native S3 state locking) is GA from 1.11.
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # 6.23 moved bucket tagging to the S3 Control API, which bucket ABAC relies on (storage.tf).
      version = "~> 6.23"
    }
  }
}
