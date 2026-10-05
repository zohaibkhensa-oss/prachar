# ─── CloudFront distribution (CDN for frontend) ──────────────────────────────

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} frontend CDN"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # North America + Europe
  aliases             = [var.domain_name, var.app_domain, "www.${var.domain_name}"]

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "s3-frontend"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }
  }

  # SPA fallback — serve index.html for all routes
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.cloudfront.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  logging_config {
    bucket = aws_s3_bucket.cf_logs.bucket_domain_name
    prefix = "cloudfront/"
  }

  tags = {
    Name        = "${var.project_name}-cdn"
    Environment = var.environment
  }

  depends_on = [aws_s3_bucket_acl.cf_logs]
}

# ─── S3 bucket for frontend (static hosting) ─────────────────────────────────

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-${var.environment}-frontend"

  tags = {
    Name        = "${var.project_name}-frontend"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# ─── CloudFront origin access control (OAC) ──────────────────────────────────

resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${var.project_name}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# SPA routing for the static export: clean URLs need .html appended, and
# runtime dynamic segments map to the exported "placeholder" stub pages
# (client components read the real params from the URL via useParams()).
resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${var.project_name}-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "SPA clean-URL + dynamic-segment stub rewrite"
  publish = true

  code = <<-EOT
    function handler(event) {
      var uri = event.request.uri;
      uri = uri.replace(/^(\/app\/(brands|review|performance)\/)[^/]+(\/.*)?$/, "$1placeholder$3");
      if (uri === "/") {
        uri = "/index.html";
      } else if (uri.endsWith("/")) {
        uri = uri.slice(0, -1) + ".html";
      } else if (!uri.match(/\.[a-zA-Z0-9]+$/)) {
        uri += ".html";
      }
      event.request.uri = uri;
      return event.request;
    }
  EOT
}

# ─── S3 bucket policy allowing CloudFront to read ────────────────────────────

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "cloudfront.amazonaws.com"
      }
      Action   = "s3:GetObject"
      Resource = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.main.arn
        }
      }
    }]
  })
}
