terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "prachar-tfstate"
    key            = "terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "prachar-tf-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

provider "aws" {
  alias  = "acm"
  region = "us-east-1" # CloudFront certificates must be in us-east-1
}
