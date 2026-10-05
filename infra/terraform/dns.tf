# ─── ACM certificate for CloudFront (must be in us-east-1) ──────────────────

resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.acm
  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    var.app_domain,
    "www.${var.domain_name}",
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-cloudfront-cert"
    Environment = var.environment
  }
}

# ─── ACM certificate for ALB (must be in the deployment region) ──────────────

resource "aws_acm_certificate" "alb" {
  domain_name       = var.api_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-alb-cert"
    Environment = var.environment
  }
}

# ─── Route53 hosted zone ─────────────────────────────────────────────────────

resource "aws_route53_zone" "main" {
  name = var.domain_name

  tags = {
    Name        = "${var.project_name}-zone"
    Environment = var.environment
  }
}

# ─── DNS validation records for CloudFront cert (us-east-1) ──────────────────
#
# for_each keys must be known at plan time, so we iterate over the static
# certificate domain list and look up the computed DVO attributes per key.

locals {
  cloudfront_cert_domains = toset([
    var.domain_name,
    var.app_domain,
    "www.${var.domain_name}",
  ])
  alb_cert_domains = toset([
    var.api_domain,
  ])
}

resource "aws_route53_record" "cloudfront_cert_validation" {
  for_each = local.cloudfront_cert_domains

  allow_overwrite = true
  name            = [for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.resource_record_name if dvo.domain_name == each.key][0]
  records         = [[for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.resource_record_value if dvo.domain_name == each.key][0]]
  ttl             = 60
  type            = [for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.resource_record_type if dvo.domain_name == each.key][0]
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "cloudfront" {
  provider                = aws.acm
  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for r in aws_route53_record.cloudfront_cert_validation : r.fqdn]
}

# ─── DNS validation records for ALB cert (regional) ──────────────────────────

resource "aws_route53_record" "alb_cert_validation" {
  for_each = local.alb_cert_domains

  allow_overwrite = true
  name            = [for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.resource_record_name if dvo.domain_name == each.key][0]
  records         = [[for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.resource_record_value if dvo.domain_name == each.key][0]]
  ttl             = 60
  type            = [for dvo in aws_acm_certificate.alb.domain_validation_options : dvo.resource_record_type if dvo.domain_name == each.key][0]
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "alb" {
  certificate_arn         = aws_acm_certificate.alb.arn
  validation_record_fqdns = [for r in aws_route53_record.alb_cert_validation : r.fqdn]
}

# ─── DNS records ─────────────────────────────────────────────────────────────

# API → ALB
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.api_domain
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# App → CloudFront
resource "aws_route53_record" "app" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.app_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# Root → CloudFront
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

# www → CloudFront
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [var.domain_name]
}
