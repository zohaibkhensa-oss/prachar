variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "prachar"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  default     = "production"
}

variable "domain_name" {
  description = "Primary domain name for the application"
  type        = string
  default     = "curvai.org"
}

variable "api_domain" {
  description = "API subdomain"
  type        = string
  default     = "api.curvai.org"
}

variable "app_domain" {
  description = "App subdomain"
  type        = string
  default     = "app.curvai.org"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS (true for production, false for dev/staging)"
  type        = bool
  default     = true
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.small"
}

variable "redis_cluster_size" {
  description = "Number of Redis replicas (excluding primary)"
  type        = number
  default     = 1
}

variable "enable_waf" {
  description = "Enable WAF on ALB (true for production, false for dev/staging)"
  type        = bool
  default     = true
}

variable "enable_nat_single_az" {
  description = "Use single NAT gateway (true for dev/staging, false for production Multi-AZ)"
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications (leave empty to skip subscription)"
  type        = string
  default     = ""
}

variable "ecs_api_cpu" {
  description = "CPU units for API task"
  type        = number
  default     = 1024
}

variable "ecs_api_memory" {
  description = "Memory (MB) for API task"
  type        = number
  default     = 2048
}

variable "api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 1
}

variable "worker_cpu" {
  description = "CPU units for worker task"
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Memory (MB) for worker task"
  type        = number
  default     = 1024
}

variable "ecr_api_image" {
  description = "ECR image URI for the API"
  type        = string
  default     = ""
}

variable "ecr_web_image" {
  description = "ECR image URI for the web frontend"
  type        = string
  default     = ""
}

variable "ecr_worker_image" {
  description = "ECR image URI for the worker"
  type        = string
  default     = ""
}
