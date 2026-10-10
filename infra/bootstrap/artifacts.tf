# Lambda zips (<env>/lambda/<sha256>.zip) and production's saved plans (plans/production/<run>.tfplan).
# Everything here is derived and rebuildable, so unlike the archive bucket it may expire
# (infra/data-retention). A saved plan holds tfvars values in plain text, which is why it lives in
# a private bucket and never in a GitHub artifact on a public repository.
resource "aws_s3_bucket" "artifacts" {
  #checkov:skip=CKV2_AWS_62:Nothing consumes events from this bucket
  #checkov:skip=CKV_AWS_144:Everything here is rebuilt from the repository, so replication would only cost money
  #checkov:skip=CKV_AWS_145:SSE-S3 (AES256); a customer managed key costs $1/month and needs a grant for every role
  #checkov:skip=CKV_AWS_18:Access logs need a second bucket, which a bucket written only by CI does not justify
  bucket = local.artifacts_bucket
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

data "aws_iam_policy_document" "artifacts_bucket" {
  statement {
    sid       = "TlsOnly"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [local.artifacts_arn, "${local.artifacts_arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Every write must send If-None-Match: *, so S3 refuses to replace an existing object. A zip's key
  # is its content hash, so "already there" means the same bytes, and a saved plan is never replaced.
  statement {
    sid       = "NoOverwrites"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${local.artifacts_arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Null"
      variable = "s3:if-none-match"
      values   = ["true"]
    }
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = data.aws_iam_policy_document.artifacts_bucket.json

  # The public access block rejects a policy it considers public while it is still being applied.
  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  depends_on = [aws_s3_bucket_versioning.artifacts]

  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    expiration {
      expired_object_delete_marker = true
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # A zip is only read to deploy it, and rebuilding the same commit gives the same key, so an
  # expired one is simply uploaded again by the next deploy.
  rule {
    id     = "expire-staging-zips"
    status = "Enabled"

    filter {
      prefix = "staging/lambda/"
    }

    expiration {
      days = 90
    }
  }

  rule {
    id     = "expire-production-zips"
    status = "Enabled"

    filter {
      prefix = "production/lambda/"
    }

    expiration {
      days = 90
    }
  }

  # A saved plan is applied within hours of being made; a stale one is refused anyway.
  rule {
    id     = "expire-plans"
    status = "Enabled"

    filter {
      prefix = "plans/"
    }

    expiration {
      days = 14
    }
  }
}
