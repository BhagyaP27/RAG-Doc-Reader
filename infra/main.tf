terraform{
    required_providers {
        aws = {source = "hashicorp/aws", version = "~> 5.0"}
    }

    backend "s3" {
        bucket = "rag-doc-reader-tf-state"
        key = "prod/terraform.tfstate"
        region = "us-east-1"
        dynamodb_table = "rag-tf-lock" # prevents concurrent apply corruption
        encrypt = true
    }
}

provider "aws" { region = var.aws_region}