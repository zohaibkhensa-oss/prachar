# ─── ECS Fargate cluster ─────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-ecs"
    Environment = var.environment
  }
}

# ─── CloudWatch log groups ───────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}/api"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-api-logs"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}/worker"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-worker-logs"
    Environment = var.environment
  }
}

# ─── IAM roles for ECS task execution ────────────────────────────────────────

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS to read secrets from Secrets Manager
resource "aws_iam_role_policy" "ecs_secrets" {
  name = "${var.project_name}-ecs-secrets-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = [
        aws_secretsmanager_secret.db_password.arn,
        aws_secretsmanager_secret.redis_token.arn,
        aws_secretsmanager_secret.app_secrets.arn,
      ]
    }]
  })
}

# ─── IAM role for ECS tasks (application permissions) ────────────────────────

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${var.project_name}-ecs-s3-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.storage.arn,
        "${aws_s3_bucket.storage.arn}/*"
      ]
    }]
  })
}

# ─── Application secrets in Secrets Manager ──────────────────────────────────

resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "/${var.project_name}/${var.environment}/app/env"
  description = "Application environment secrets for ${var.project_name}"

  tags = {
    Name        = "${var.project_name}-app-secrets"
    Environment = var.environment
  }
}

# This secret holds JSON with: JWT_SECRET, JWT_REFRESH_SECRET, TOKEN_ENC_KEY,
# ANTHROPIC_API_KEY, OPENAI_API_KEY, STRIPE_API_KEY, RAZORPAY_KEY_ID,
# RAZORPAY_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, META_*, etc.
# Populate manually after initial terraform apply.
resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id     = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    JWT_SECRET           = "CHANGE_ME_AFTER_APPLY"
    JWT_REFRESH_SECRET   = "CHANGE_ME_AFTER_APPLY"
    TOKEN_ENC_KEY        = "CHANGE_ME_32_HEX_BYTES"
    ANTHROPIC_API_KEY    = ""
    OPENAI_API_KEY       = ""
    STRIPE_API_KEY       = ""
    RAZORPAY_KEY_ID      = ""
    RAZORPAY_SECRET      = ""
    GROQ_API_KEY         = ""
  })
}

# ─── API task definition ────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_api_cpu
  memory                   = var.ecs_api_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = coalesce(var.ecr_api_image, "public.ecr.aws/docker/library/python:3.12-slim")
      essential = true

      portMappings = [{
        containerPort = 8000
        hostPort      = 8000
        protocol      = "tcp"
      }]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "REDIS_URL", value = "rediss://:${random_password.redis_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0" },
        { name = "S3_ENDPOINT", value = "https://s3.${var.aws_region}.amazonaws.com" },
        { name = "S3_BUCKET", value = aws_s3_bucket.storage.bucket },
        { name = "AWS_REGION", value = var.aws_region },
      ]

      secrets = [
        { name = "JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:JWT_SECRET::" },
        { name = "JWT_REFRESH_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:JWT_REFRESH_SECRET::" },
        { name = "TOKEN_ENC_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:TOKEN_ENC_KEY::" },
        { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:ANTHROPIC_API_KEY::" },
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:OPENAI_API_KEY::" },
        { name = "GROQ_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:GROQ_API_KEY::" },
        { name = "STRIPE_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:STRIPE_API_KEY::" },
        { name = "RAZORPAY_KEY_ID", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:RAZORPAY_KEY_ID::" },
        { name = "RAZORPAY_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:RAZORPAY_SECRET::" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-api-task"
    Environment = var.environment
  }
}

# ─── API ECS service ─────────────────────────────────────────────────────────

resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  health_check_grace_period_seconds = 120

  depends_on = [aws_lb_listener.https]

  tags = {
    Name        = "${var.project_name}-api-service"
    Environment = var.environment
  }
}

# ─── Worker task definition ──────────────────────────────────────────────────

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = coalesce(var.ecr_worker_image, "public.ecr.aws/docker/library/python:3.12-slim")
      essential = true

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "REDIS_URL", value = "rediss://:${random_password.redis_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0" },
        { name = "S3_ENDPOINT", value = "https://s3.${var.aws_region}.amazonaws.com" },
        { name = "S3_BUCKET", value = aws_s3_bucket.storage.bucket },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "CELERY_WORKER", value = "true" },
      ]

      secrets = [
        { name = "JWT_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:JWT_SECRET::" },
        { name = "JWT_REFRESH_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:JWT_REFRESH_SECRET::" },
        { name = "TOKEN_ENC_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:TOKEN_ENC_KEY::" },
        { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:ANTHROPIC_API_KEY::" },
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:OPENAI_API_KEY::" },
        { name = "GROQ_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:GROQ_API_KEY::" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-worker-task"
    Environment = var.environment
  }
}

# ─── Worker ECS service ──────────────────────────────────────────────────────

resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  tags = {
    Name        = "${var.project_name}-worker-service"
    Environment = var.environment
  }
}
