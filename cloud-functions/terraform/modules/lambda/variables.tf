variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  type        = string
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
    create_function_url = optional(bool, false)
    sqs_queue_name   = optional(string)
    batch_size       = optional(number, 10)
  }))
}

variable "sqs_queue_urls" {
  description = "Map of SQS queue URLs"
  type        = map(string)
  default     = {}
}

variable "api_gateway_execution_arn" {
  description = "API Gateway execution ARN"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
} 