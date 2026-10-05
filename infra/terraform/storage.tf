# ─── S3 bucket for object storage (uploads, assets, reports) ─────────────────

resource "aws_s3_bucket" "storage" {
  bucket = "${var.project_name}-${var.environment}-storage"

  tags = {
    Name        = "${var.project_name}-storage"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "storage" {
  bucket = aws_s3_bucket.storage.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "storage" {
  bucket = aws_s3_bucket.storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "storage" {
  bucket = aws_s3_bucket.storage.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "expire-temp-uploads"
    status = "Enabled"

    filter {
      prefix = "temp/"
    }

    expiration {
      days = 7
    }
  }
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-s3-kms"
    Environment = var.environment
  }
}

# ─── S3 bucket for CloudFront logs ───────────────────────────────────────────

resource "aws_s3_bucket" "cf_logs" {
  bucket = "${var.project_name}-${var.environment}-cf-logs"

  tags = {
    Name        = "${var.project_name}-cf-logs"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "cf_logs" {
  bucket = aws_s3_bucket.cf_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── Terraform state backend bucket ──────────────────────────────────────────
# NOTE: prachar-tfstate is intentionally NOT Terraform-managed — Terraform cannot
# create/destroy the bucket that stores its own state. Managed out-of-band per
# STATE_BOOTSTRAP.md.


