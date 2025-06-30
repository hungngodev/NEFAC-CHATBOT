# Dead Letter Queue
resource "aws_sqs_queue" "dead_letter" {
  name = "${var.project}-${var.environment}-dlq"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-dlq"
  })
}

# SQS Queues
resource "aws_sqs_queue" "queues" {
  for_each = var.sqs_queues

  name = "${var.project}-${var.environment}-${each.value.name}"

  visibility_timeout_seconds  = each.value.visibility_timeout
  message_retention_seconds   = each.value.message_retention_period
  receive_wait_time_seconds   = each.value.receive_wait_time
  delay_seconds              = lookup(each.value, "delay_seconds", 0)
  max_message_size           = lookup(each.value, "max_message_size", 262144)

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn
    maxReceiveCount     = lookup(each.value, "max_receive_count", 3)
  })

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-${each.value.name}"
  })
}

# SQS Queue Policies
resource "aws_sqs_queue_policy" "queue_policies" {
  for_each = {
    for k, v in var.sqs_queues : k => v
    if lookup(v, "enable_policy", false)
  }

  queue_url = aws_sqs_queue.queues[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.queues[each.key].arn
      }
    ]
  })
}

# CloudWatch alarms for queue metrics
resource "aws_cloudwatch_metric_alarm" "queue_alarms" {
  for_each = var.sqs_queues

  alarm_name          = "${var.project}-${var.environment}-${each.value.name}-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = lookup(each.value, "alarm_threshold", 100)
  alarm_description   = "This metric monitors SQS queue message count"
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.queues[each.key].name
  }

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-${each.value.name}-alarm"
  })
} 