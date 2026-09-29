# Production only: it's production's rollback, and no other environment ever had MVP data.
resource "aws_dynamodb_table" "posted" {
  count = local.production ? 1 : 0

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

# Replaces aws_dynamodb_table.posted (see backend/dynamodb-schema). posted stays untouched as the
# rollback until the new keys have soaked, then goes away deliberately.
# Items under PK = OFFICE#<id>, each carrying schema_version:
#   STORY#<start_utc_iso>#<story_key>                current story
#   EVENT#<start_utc_iso>#<story_key>#<at_utc_iso>   ledger event (append-only)
#   RUN#<at_utc_iso>                                 run record (append-only)
#   LEASE                                            office lease
resource "aws_dynamodb_table" "state" {
  name         = "${local.name}-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # No secondary indexes: keys serve the bot's own access patterns, and analytics reads a native
  # export to S3 instead (backend/dynamodb-schema). Never add an LSI: it can only be created with
  # the table and caps each office partition at 10 GB. A GSI can be added later and backfills from
  # ordinary attributes such as event_at.

  # No ttl block, on purpose: records are permanent and the ledger is a source of truth. Don't
  # add a TTL. The lease expires through a conditional write on its own expires_at attribute.

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

# S3 evaluates bucket tags (aws:ResourceTag, s3:BucketTag) on a general purpose bucket only once
# ABAC is enabled, so this goes live a deploy before any policy condition reads the Environment tag.
# Enabling it changes no access while no policy checks bucket tags. Once it's on, PutBucketTagging
# and DeleteBucketTagging stop working and tags must go through S3 Control TagResource and
# UntagResource. Provider >= 6.23 switches to those only when the caller holds s3:TagResource,
# s3:UntagResource and s3:ListTagsForResource; without them it silently falls back to
# PutBucketTagging, which then fails. To undo, apply with status = "Disabled".
resource "aws_s3_bucket_abac" "archive" {
  bucket = aws_s3_bucket.archive.id

  abac_status {
    status = "Enabled"
  }
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
