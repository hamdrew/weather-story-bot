terraform {
  # use_lockfile (native S3 state locking) is GA from 1.11.
  required_version = ">= 1.11"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = local.name
      ManagedBy = "terraform"
    }
  }
}

locals {
  name = "weather-story-bot"
}

data "aws_caller_identity" "current" {}
