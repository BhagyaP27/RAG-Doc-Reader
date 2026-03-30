# Persistent storage for FAISS index + metadata.json
# Without this, every deployment wipes all uploaded documents.
resource "aws_efs_file_system" "vector_store" {
  creation_token = "rag-vector-store"
  encrypted      = true

  tags = { Name = "rag-vector-store" }
}

resource "aws_efs_mount_target" "vector_store" {
  file_system_id  = aws_efs_file_system.vector_store.id
  subnet_id       = aws_subnet.private.id
  security_groups = [aws_security_group.efs_sg.id]
}

resource "aws_security_group" "efs_sg" {
  name   = "rag-efs-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 2049   # NFS port
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}