resource "aws_dynamodb_table" "posted" {
  name         = "${local.name}-posted"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "office_id"
  range_key    = "image_id"

  attribute {
    name = "office_id"
    type = "S"
  }

  attribute {
    name = "image_id"
    type = "S"
  }

  # Blocks DeleteTable, including terraform destroy or a key change that forces replacement.
  # To really remove the table, apply with this set to false first.
  deletion_protection_enabled = true

  # Billed on table size, not window length, so keep the full window. Restores go to a new table.
  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 35
  }
}

resource "aws_s3_bucket" "archive" {
  bucket = "${local.name}-archive-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Replaced or deleted files stay recoverable for 35 days, the same window as DynamoDB PITR.
# Current objects never expire: the archive is kept forever, so never add expiration days/date here.
resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  depends_on = [aws_s3_bucket_versioning.archive]

  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 35
    }

    expiration {
      expired_object_delete_marker = true
    }
  }
}

resource "aws_s3_bucket_public_access_block" "archive" {
  bucket = aws_s3_bucket.archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
