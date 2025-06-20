variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "lambda_functions" {
  description = "Map of Lambda function configurations"
  type = map(object({
    filename         = string
    function_name    = string
    handler          = string
    runtime          = string
    timeout          = number
    memory_size      = number
    environment_vars = map(string)
  }))
  default = {
    text_processor = {
      filename      = "lambda_functions/text_processor.zip"
      function_name = "text-processor"
      handler       = "text_processor.lambda_handler"
      runtime       = "python3.9"
      timeout       = 300
      memory_size   = 512
      environment_vars = {
        CHUNK_SIZE      = "1000"
        PCA_COMPONENTS  = "256"
      }
    }
  }
}

variable "sqs_queues" {
  description = "Map of SQS queue configurations"
  type = map(object({
    name                    = string
    visibility_timeout      = number
    message_retention_period = number
    receive_wait_time       = number
    dead_letter_queue_arn   = optional(string)
  }))
  default = {
    text_processing_input = {
      name                     = "text-processing-input"
      visibility_timeout       = 300
      message_retention_period = 1209600
      receive_wait_time        = 20
    }
    processed_chunks = {
      name                     = "processed-chunks"
      visibility_timeout       = 60
      message_retention_period = 1209600
      receive_wait_time        = 20
    }
    embedding_results = {
      name                     = "embedding-results"
      visibility_timeout       = 60
      message_retention_period = 1209600
      receive_wait_time        = 20
    }
  }
}

variable "ecr_repositories" {
  description = "Map of ECR repository configurations"
  type = map(object({
    name                 = string
    image_tag_mutability = string
    scan_on_push         = bool
  }))
  default = {
    nefac_backend = {
      name                 = "nefac-backend"
      image_tag_mutability = "MUTABLE"
      scan_on_push         = true
    }
    nefac_frontend = {
      name                 = "nefac-frontend"
      image_tag_mutability = "MUTABLE"
      scan_on_push         = true
    }
  }
}

variable "ecs_services" {
  description = "Map of ECS service configurations"
  type = map(object({
    name           = string
    desired_count  = number
    cpu            = number
    memory         = number
    port_mappings  = list(object({
      container_port = number
      host_port      = number
      protocol       = string
    }))
    environment_vars = map(string)
  }))
  default = {
    backend = {
      name          = "nefac-backend"
      desired_count = 2
      cpu           = 256
      memory        = 512
      port_mappings = [{
        container_port = 8000
        host_port      = 8000
        protocol       = "tcp"
      }]
      environment_vars = {
        ENVIRONMENT = "production"
      }
    }
    frontend = {
      name          = "nefac-frontend"
      desired_count = 2
      cpu           = 128
      memory        = 256
      port_mappings = [{
        container_port = 80
        host_port      = 80
        protocol       = "tcp"
      }]
      environment_vars = {
        REACT_APP_API_URL = "https://api.nefac.com"
      }
    }
  }
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "nefac.com"
}

variable "certificate_arn" {
  description = "ARN of the SSL certificate"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
} 