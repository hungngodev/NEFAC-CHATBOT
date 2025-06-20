# S3 buckets
resource "aws_s3_bucket" "buckets" {
  for_each = var.buckets

  bucket = "${var.project}-${var.environment}-${each.value.name}"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-${each.value.name}"
  })
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "versioning" {
  for_each = {
    for k, v in var.buckets : k => v
    if lookup(v, "versioning", false)
  }

  bucket = aws_s3_bucket.buckets[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "encryption" {
  for_each = aws_s3_bucket.buckets

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "public_access_block" {
  for_each = aws_s3_bucket.buckets

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "lifecycle" {
  for_each = {
    for k, v in var.buckets : k => v
    if lookup(v, "lifecycle_rules", null) != null
  }

  bucket = aws_s3_bucket.buckets[each.key].id

  dynamic "rule" {
    for_each = each.value.lifecycle_rules
    content {
      id     = rule.value.id
      status = rule.value.status

      dynamic "transition" {
        for_each = lookup(rule.value, "transitions", [])
        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }

      dynamic "expiration" {
        for_each = lookup(rule.value, "expiration", [])
        content {
          days = expiration.value.days
        }
      }
    }
  }
} 