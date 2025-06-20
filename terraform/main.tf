terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "nefac-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "nefac"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# VPC and networking
module "vpc" {
  source = "./modules/vpc"
  
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

# S3 buckets
module "s3" {
  source = "./modules/s3"
  
  environment = var.environment
  project     = "nefac"
}

# IAM roles and policies
module "iam" {
  source = "./modules/iam"
  
  environment = var.environment
  account_id  = data.aws_caller_identity.current.account_id
}

# SQS queues
module "sqs" {
  source = "./modules/sqs"
  
  environment = var.environment
  project     = "nefac"
}

# Lambda functions
module "lambda" {
  source = "./modules/lambda"
  
  environment     = var.environment
  project         = "nefac"
  lambda_role_arn = module.iam.lambda_role_arn
  sqs_queue_urls  = module.sqs.queue_urls
}

# ECR repositories
module "ecr" {
  source = "./modules/ecr"
  
  environment = var.environment
  project     = "nefac"
}

# ECS cluster and services
module "ecs" {
  source = "./modules/ecs"
  
  environment      = var.environment
  project          = "nefac"
  vpc_id           = module.vpc.vpc_id
  private_subnets  = module.vpc.private_subnet_ids
  public_subnets   = module.vpc.public_subnet_ids
  ecr_repository_url = module.ecr.repository_url
  ecs_task_role_arn = module.iam.ecs_task_role_arn
  ecs_exec_role_arn = module.iam.ecs_exec_role_arn
}

# CloudWatch logs
module "cloudwatch" {
  source = "./modules/cloudwatch"
  
  environment = var.environment
  project     = "nefac"
}

# API Gateway (if needed for Lambda functions)
module "api_gateway" {
  source = "./modules/api_gateway"
  
  environment = var.environment
  project     = "nefac"
  lambda_functions = module.lambda.function_arns
} 