# ─── ElastiCache Redis (HA replication group) ────────────────────────────────

resource "aws_elasticache_subnet_group" "main" {
  name        = "${var.project_name}-redis-subnet-group"
  description = "Redis subnet group for ${var.project_name}"
  subnet_ids  = aws_subnet.private[*].id

  tags = {
    Name        = "${var.project_name}-redis-subnet-group"
    Environment = var.environment
  }
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id          = "${var.project_name}-${var.environment}"
  description                   = "Redis HA cluster for ${var.project_name}"
  node_type                     = var.redis_node_type
  num_cache_clusters            = var.redis_cluster_size + 1
  port                          = 6379
  engine_version                = "7.1"
  parameter_group_name          = "default.redis7.x"
  subnet_group_name             = aws_elasticache_subnet_group.main.name
  security_group_ids            = [aws_security_group.redis.id]
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  auth_token                    = aws_secretsmanager_secret_version.redis_token.secret_string

  snapshot_retention_limit = 7
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:30-sun:06:30"

  tags = {
    Name        = "${var.project_name}-redis"
    Environment = var.environment
  }
}

# ─── Redis auth token in Secrets Manager ─────────────────────────────────────

resource "aws_secretsmanager_secret" "redis_token" {
  name        = "/${var.project_name}/${var.environment}/redis/token"
  description = "Redis AUTH token for ${var.project_name}"

  tags = {
    Name        = "${var.project_name}-redis-secret"
    Environment = var.environment
  }
}

resource "random_password" "redis_token" {
  length  = 32
  special = false # Redis AUTH tokens: alphanumeric only
}

resource "aws_secretsmanager_secret_version" "redis_token" {
  secret_id     = aws_secretsmanager_secret.redis_token.id
  secret_string = random_password.redis_token.result
}
