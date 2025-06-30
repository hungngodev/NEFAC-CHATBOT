variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "sqs_queues" {
  description = "Map of SQS queue configurations"
  type = map(object({
    name                     = string
    visibility_timeout       = number
    message_retention_period = number
    receive_wait_time        = number
    delay_seconds           = optional(number, 0)
    max_message_size        = optional(number, 262144)
    max_receive_count       = optional(number, 3)
    enable_policy           = optional(bool, false)
    alarm_threshold         = optional(number, 100)
  }))
}

variable "alarm_actions" {
  description = "List of ARNs for CloudWatch alarm actions"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
} 