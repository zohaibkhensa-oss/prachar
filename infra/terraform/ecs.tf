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

resource "aws_cloudwatch_log_group" "beat" {
  name              = "/ecs/${var.project_name}/beat"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-beat-logs"
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
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    JWT_SECRET         = "CHANGE_ME_AFTER_APPLY"
    JWT_REFRESH_SECRET = "CHANGE_ME_AFTER_APPLY"
    TOKEN_ENC_KEY      = "CHANGE_ME_32_HEX_BYTES"
    ANTHROPIC_API_KEY  = ""
    OPENAI_API_KEY     = ""
    STRIPE_API_KEY     = ""
    RAZORPAY_KEY_ID    = ""
    RAZORPAY_SECRET    = ""
    GROQ_API_KEY       = ""
  })

  # Prevent Terraform from resetting secrets that were populated manually
  # after the initial apply. Without this, every `terraform apply` would
  # overwrite real secrets with the placeholder values above.
  lifecycle {
    ignore_changes = [secret_string]
  }
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
      image     = var.ecr_api_image != "" ? var.ecr_api_image : "public.ecr.aws/docker/library/python:3.12-slim"
      essential = true

      portMappings = [{
        containerPort = 8000
        hostPort      = 8000
        protocol      = "tcp"
      }]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "REDIS_URL", value = "rediss://:${random_password.redis_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0?ssl_cert_reqs=CERT_NONE" },
        { name = "S3_ENDPOINT", value = "https://s3.${var.aws_region}.amazonaws.com" },
        { name = "S3_BUCKET", value = aws_s3_bucket.storage.bucket },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "CORS_ORIGINS", value = "https://${var.app_domain},https://${var.domain_name},https://www.${var.domain_name}" },
        { name = "WEB_URL", value = "https://${var.app_domain}" },
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
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)\" || exit 1"]
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

# ─── Migration task definition (one-off alembic runs via ecs run-task) ────────

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/ecs/${var.project_name}/migrate"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-migrate-logs"
    Environment = var.environment
  }
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.project_name}-migrate"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name             = "migrate"
      image            = var.ecr_api_image != "" ? var.ecr_api_image : "public.ecr.aws/docker/library/python:3.12-slim"
      essential        = true
      workingDirectory = "/app"
      command          = ["/bin/sh", "-c", "cd apps/api && alembic upgrade head"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "AWS_REGION", value = var.aws_region },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.migrate.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migrate"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-migrate-task"
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
      image     = var.ecr_worker_image != "" ? var.ecr_worker_image : "public.ecr.aws/docker/library/python:3.12-slim"
      essential = true

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "REDIS_URL", value = "rediss://:${random_password.redis_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0?ssl_cert_reqs=CERT_NONE" },
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

# ─── Celery Beat task definition (singleton scheduler) ──────────────────────
# Beat must NEVER run more than 1 replica — duplicate beat instances cause
# duplicate task dispatch. desired_count is hardcoded to 1.

resource "aws_ecs_task_definition" "beat" {
  family                   = "${var.project_name}-beat"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "beat"
      image     = var.ecr_worker_image != "" ? var.ecr_worker_image : "public.ecr.aws/docker/library/python:3.12-slim"
      essential = true

      command = ["celery", "-A", "prachar_workers.celery_app", "beat", "-l", "info"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://prachar_admin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/prachar" },
        { name = "REDIS_URL", value = "rediss://:${random_password.redis_token.result}@${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0?ssl_cert_reqs=CERT_NONE" },
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
          "awslogs-group"         = aws_cloudwatch_log_group.beat.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "beat"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-beat-task"
    Environment = var.environment
  }
}

# ─── Celery Beat ECS service (singleton — desired_count = 1) ────────────────

resource "aws_ecs_service" "beat" {
  name            = "${var.project_name}-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1 # MUST remain 1 — beat is a singleton
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

  deployment_maximum_percent         = 100 # Never run 2 beat instances
  deployment_minimum_healthy_percent = 0   # Allow rolling deploys

  tags = {
    Name        = "${var.project_name}-beat-service"
    Environment = var.environment
  }
}

# ─── Web (Next.js) task definition ───────────────────────────────────────────
# Next.js requires a running Node server for the /api rewrite proxy and
# 30-min proxyTimeout for SSE video generation. S3+CloudFront static hosting
# is NOT viable for this application.

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${var.project_name}/web"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-web-logs"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "web" {
  name        = "${var.project_name}-web-tg"
  port        = 3002
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200-399"
  }

  tags = {
    Name        = "${var.project_name}-web-tg"
    Environment = var.environment
  }
}

resource "aws_lb_listener_rule" "web" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }

  condition {
    host_header {
      values = [var.app_domain]
    }
  }
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.project_name}-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = var.ecr_web_image != "" ? var.ecr_web_image : "public.ecr.aws/docker/library/node:20-slim"
      essential = true

      portMappings = [{
        containerPort = 3002
        hostPort      = 3002
        protocol      = "tcp"
      }]

      environment = [
        { name = "NODE_ENV", value = "production" },
        { name = "NEXT_PUBLIC_API_BASE", value = "https://${var.api_domain}" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.web.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "web"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "node -e \"fetch('http://localhost:3002/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-web-task"
    Environment = var.environment
  }
}

resource "aws_ecs_service" "web" {
  name            = "${var.project_name}-web"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3002
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
    Name        = "${var.project_name}-web-service"
    Environment = var.environment
  }
}
