variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "buckets" {
  description = "Map of S3 bucket configurations"
  type = map(object({
    name = string
    versioning = optional(bool, false)
    lifecycle_rules = optional(list(object({
      id     = string
      status = string
      transitions = optional(list(object({
        days          = number
        storage_class = string
      })), [])
      expiration = optional(list(object({
        days = number
      })), [])
    })), [])
  }))
  default = {
    data = {
      name = "data"
      versioning = true
    }
    artifacts = {
      name = "artifacts"
      versioning = true
    }
    logs = {
      name = "logs"
      lifecycle_rules = [{
        id     = "log_retention"
        status = "Enabled"
        expiration = [{
          days = 90
        }]
      }]
    }
  }
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
} 