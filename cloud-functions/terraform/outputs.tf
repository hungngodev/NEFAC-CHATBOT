# VPC outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.vpc.private_subnet_ids
}

# S3 outputs
output "s3_bucket_names" {
  description = "Names of the S3 buckets"
  value       = module.s3.bucket_names
}

output "s3_bucket_arns" {
  description = "ARNs of the S3 buckets"
  value       = module.s3.bucket_arns
}

# IAM outputs
output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.iam.lambda_role_arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.iam.ecs_task_role_arn
}

output "ecs_exec_role_arn" {
  description = "ARN of the ECS execution role"
  value       = module.iam.ecs_exec_role_arn
}

# SQS outputs
output "sqs_queue_urls" {
  description = "URLs of the SQS queues"
  value       = module.sqs.queue_urls
}

output "sqs_queue_arns" {
  description = "ARNs of the SQS queues"
  value       = module.sqs.queue_arns
}

# Lambda outputs
output "lambda_function_names" {
  description = "Names of the Lambda functions"
  value       = module.lambda.function_names
}

output "lambda_function_arns" {
  description = "ARNs of the Lambda functions"
  value       = module.lambda.function_arns
}

output "lambda_function_urls" {
  description = "URLs of the Lambda functions (if configured)"
  value       = module.lambda.function_urls
}

# ECR outputs
output "ecr_repository_urls" {
  description = "URLs of the ECR repositories"
  value       = module.ecr.repository_urls
}

output "ecr_repository_arns" {
  description = "ARNs of the ECR repositories"
  value       = module.ecr.repository_arns
}

# ECS outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.ecs.cluster_arn
}

output "ecs_service_names" {
  description = "Names of the ECS services"
  value       = module.ecs.service_names
}

output "ecs_service_arns" {
  description = "ARNs of the ECS services"
  value       = module.ecs.service_arns
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.ecs.alb_dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = module.ecs.alb_zone_id
}

# CloudWatch outputs
output "cloudwatch_log_groups" {
  description = "Names of the CloudWatch log groups"
  value       = module.cloudwatch.log_group_names
}

# API Gateway outputs
output "api_gateway_url" {
  description = "URL of the API Gateway"
  value       = module.api_gateway.api_url
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = module.api_gateway.api_id
}

# Application URLs
output "frontend_url" {
  description = "URL of the frontend application"
  value       = "https://${var.domain_name}"
}

output "backend_url" {
  description = "URL of the backend API"
  value       = "https://api.${var.domain_name}"
}

# Summary
output "infrastructure_summary" {
  description = "Summary of the deployed infrastructure"
  value = {
    environment = var.environment
    region      = var.aws_region
    vpc_id      = module.vpc.vpc_id
    lambda_functions = length(module.lambda.function_names)
    sqs_queues  = length(module.sqs.queue_urls)
    ecr_repositories = length(module.ecr.repository_urls)
    ecs_services = length(module.ecs.service_names)
    frontend_url = "https://${var.domain_name}"
    backend_url  = "https://api.${var.domain_name}"
  }
} 