output "queue_urls" {
  description = "URLs of the SQS queues"
  value       = { for k, v in aws_sqs_queue.queues : k => v.url }
}

output "queue_arns" {
  description = "ARNs of the SQS queues"
  value       = { for k, v in aws_sqs_queue.queues : k => v.arn }
}

output "queue_names" {
  description = "Names of the SQS queues"
  value       = { for k, v in aws_sqs_queue.queues : k => v.name }
}

output "dead_letter_queue_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.dead_letter.url
}

output "dead_letter_queue_arn" {
  description = "ARN of the dead letter queue"
  value       = aws_sqs_queue.dead_letter.arn
} 