# ─── Outputs ─────────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
  sensitive   = true
}

output "s3_bucket_name" {
  description = "S3 bucket for object storage"
  value       = aws_s3_bucket.storage.bucket
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "ecr_api_repo" {
  description = "ECR repository URI for API"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_web_repo" {
  description = "ECR repository URI for web"
  value       = aws_ecr_repository.web.repository_url
}

output "ecr_worker_repo" {
  description = "ECR repository URI for worker"
  value       = aws_ecr_repository.worker.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "sns_alerts_topic" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

output "nameservers" {
  description = "Route53 nameservers (delegate your domain to these)"
  value       = aws_route53_zone.main.name_servers
}
