provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "weather-story-bot-bootstrap"
      ManagedBy = "terraform"
      # Not an environment: no role's Environment tag condition matches it.
      Environment = "bootstrap"
    }
  }
}
