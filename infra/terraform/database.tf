# ─── RDS PostgreSQL 16 (multi-AZ) ────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name        = "${var.project_name}-db-subnet-group"
  description = "Database subnet group for ${var.project_name}"
  subnet_ids  = aws_subnet.database[*].id

  tags = {
    Name        = "${var.project_name}-db-subnet-group"
    Environment = var.environment
  }
}

resource "aws_db_parameter_group" "main" {
  name   = "${var.project_name}-pg16"
  family = "postgres16"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500" # Log queries slower than 500ms
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "max_connections"
    value = "200"
  }

  tags = {
    Name        = "${var.project_name}-pg16-params"
    Environment = var.environment
  }
}

resource "aws_db_instance" "main" {
  identifier                = "${var.project_name}-${var.environment}"
  engine                    = "postgres"
  engine_version            = "16.4"
  instance_class            = var.db_instance_class
  allocated_storage         = var.db_allocated_storage
  storage_encrypted         = true
  kms_key_id                = aws_kms_key.rds.arn

  db_name                   = "prachar"
  username                  = "prachar_admin"
  password                  = aws_secretsmanager_secret_version.db_password.secret_string
  manage_master_user_password = false

  db_subnet_group_name      = aws_db_subnet_group.main.name
  parameter_group_name      = aws_db_parameter_group.main.name
  vpc_security_group_ids    = [aws_security_group.rds.id]

  multi_az                  = true
  storage_type              = "gp3"
  backup_retention_period   = 14
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:30-sun:05:30"
  deletion_protection       = var.environment == "production"
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-${var.environment}-final"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name        = "${var.project_name}-rds"
    Environment = var.environment
  }
}

# ─── KMS key for RDS encryption ──────────────────────────────────────────────

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name        = "${var.project_name}-rds-kms"
    Environment = var.environment
  }
}

# ─── RDS password in Secrets Manager ─────────────────────────────────────────

resource "aws_secretsmanager_secret" "db_password" {
  name        = "/${var.project_name}/${var.environment}/db/password"
  description = "RDS master password for ${var.project_name}"

  tags = {
    Name        = "${var.project_name}-db-secret"
    Environment = var.environment
  }
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}
