# Lambda functions
resource "aws_lambda_function" "functions" {
  for_each = var.lambda_functions

  filename         = each.value.filename
  function_name    = "${var.project}-${var.environment}-${each.value.function_name}"
  role            = var.lambda_role_arn
  handler         = each.value.handler
  runtime         = each.value.runtime
  timeout         = each.value.timeout
  memory_size     = each.value.memory_size
  source_code_hash = filebase64sha256(each.value.filename)

  environment {
    variables = merge(each.value.environment_vars, {
      ENVIRONMENT = var.environment
      PROJECT     = var.project
    })
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-${each.value.function_name}"
  })
}

# Lambda function URLs (for HTTP triggers)
resource "aws_lambda_function_url" "function_urls" {
  for_each = {
    for k, v in var.lambda_functions : k => v
    if lookup(v, "create_function_url", false)
  }

  function_name      = aws_lambda_function.functions[each.key].function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
  }
}

# SQS event source mappings for Lambda functions
resource "aws_lambda_event_source_mapping" "sqs_mappings" {
  for_each = {
    for k, v in var.lambda_functions : k => v
    if lookup(v, "sqs_queue_name", null) != null
  }

  event_source_arn = var.sqs_queue_urls[each.value.sqs_queue_name]
  function_name    = aws_lambda_function.functions[each.key].arn
  enabled          = true
  batch_size       = lookup(each.value, "batch_size", 10)
}

# CloudWatch log groups for Lambda functions
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = var.lambda_functions

  name              = "/aws/lambda/${aws_lambda_function.functions[each.key].function_name}"
  retention_in_days = 14

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-${each.value.function_name}-logs"
  })
}

# Lambda permissions for SQS
resource "aws_lambda_permission" "sqs_permissions" {
  for_each = {
    for k, v in var.lambda_functions : k => v
    if lookup(v, "sqs_queue_name", null) != null
  }

  statement_id  = "AllowExecutionFromSQS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.functions[each.key].function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = var.sqs_queue_urls[each.value.sqs_queue_name]
}

# Lambda permissions for API Gateway (if needed)
resource "aws_lambda_permission" "api_gateway_permissions" {
  for_each = {
    for k, v in var.lambda_functions : k => v
    if lookup(v, "create_function_url", false)
  }

  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.functions[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api_gateway_execution_arn}/*/*"
} 