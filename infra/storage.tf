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
}

resource "aws_s3_bucket" "archive" {
  bucket = "${local.name}-archive-${data.aws_caller_identity.current.account_id}"
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
