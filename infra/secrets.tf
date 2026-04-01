resource "aws_secretsmanager_secret" "anthropic_key" {
  name = "rag-doc-reader/anthropic-api-key"
  # Value set manually once: aws secretsmanager put-secret-value ...
}