variable "aws_region"   { default = "us-east-1" }
variable "environment"  { default = "prod" }
variable "image_tag"    { description = "Docker image SHA from GitHub Actions" }