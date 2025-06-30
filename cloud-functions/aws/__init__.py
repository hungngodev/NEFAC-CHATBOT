"""
AWS utilities and infrastructure for the NEFAC project.

This package contains:
- Lambda functions for text processing
- SQS utilities for message queuing
- AWS configuration and client setup
- LocalStack testing utilities
"""

from .aws_config import (
    get_aws_client,
    get_cloudwatch_client,
    get_ecr_client,
    get_ecs_client,
    get_iam_client,
    get_lambda_client,
    get_logs_client,
    get_s3_client,
    get_sqs_client,
)
from .lambda_utils import LambdaManager, deploy_text_processor
from .sqs_utils import SQSManager, setup_text_processing_queues

__all__ = [
    "get_aws_client",
    "get_lambda_client",
    "get_sqs_client",
    "get_s3_client",
    "get_ecr_client",
    "get_ecs_client",
    "get_logs_client",
    "get_iam_client",
    "get_cloudwatch_client",
    "LambdaManager",
    "deploy_text_processor",
    "SQSManager",
    "setup_text_processing_queues",
]
