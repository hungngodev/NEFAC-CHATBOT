output "function_names" {
  description = "Names of the Lambda functions"
  value       = [for func in aws_lambda_function.functions : func.function_name]
}

output "function_arns" {
  description = "ARNs of the Lambda functions"
  value       = [for func in aws_lambda_function.functions : func.arn]
}

output "function_urls" {
  description = "URLs of the Lambda functions (if configured)"
  value       = { for k, v in aws_lambda_function_url.function_urls : k => v.url }
}

output "function_invoke_arns" {
  description = "Invoke ARNs of the Lambda functions"
  value       = [for func in aws_lambda_function.functions : func.invoke_arn]
}

output "log_group_names" {
  description = "Names of the CloudWatch log groups"
  value       = [for log_group in aws_cloudwatch_log_group.lambda_logs : log_group.name]
} 