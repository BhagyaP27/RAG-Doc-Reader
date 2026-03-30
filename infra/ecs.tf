resource "aws_ecs_cluster" "main" {
  name = "rag-doc-reader"
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "rag-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"   # 1 vCPU — sentence-transformers needs it
  memory                   = "2048"   # 2 GB — FAISS + model in memory

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  # EFS volume for FAISS persistence
  volume {
    name = "vector-store"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.vector_store.id
      root_directory = "/"
    }
  }

  container_definitions = jsonencode([{
    name  = "backend"
    image = "${aws_ecr_repository.backend.repository_url}:${var.image_tag}"
    portMappings = [{ containerPort = 8000 }]

    # Mount EFS at the same path your app uses
    mountPoints = [{
      sourceVolume  = "vector-store"
      containerPath = "/app/vector_store"
    }]

    # Pull secrets from AWS Secrets Manager — never hardcode keys
    secrets = [
      { name = "ANTHROPIC_API_KEY",
        valueFrom = aws_secretsmanager_secret.anthropic_key.arn },
    ]

    # Override Ollama to use Anthropic in production
    environment = [
      { name = "LLM_PROVIDER", value = "anthropic" },
      { name = "LLM_MODEL",    value = "claude-haiku-4-5-20251001" },
      { name = "VECTOR_DB_PATH", value = "/app/vector_store" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = "/ecs/rag-backend"
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "rag-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private.id]
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }
}