variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
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
  default     = "prachar.ai"
}

variable "api_domain" {
  description = "API subdomain"
  type        = string
  default     = "api.prachar.ai"
}

variable "app_domain" {
  description = "App subdomain"
  type        = string
  default     = "app.prachar.ai"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_cluster_size" {
  description = "Number of Redis replicas (excluding primary)"
  type        = number
  default     = 2
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
  default     = 2
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks"
  type        = number
  default     = 2
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
