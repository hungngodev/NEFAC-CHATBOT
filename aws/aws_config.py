import os
import boto3
from typing import Optional
from botocore.config import Config

def get_aws_client(service_name: str, region_name: Optional[str] = None):
    """
    Get AWS client configured for either LocalStack (local development) or production AWS.
    
    Args:
        service_name: AWS service name (e.g., 'lambda', 'sqs', 's3')
        region_name: AWS region name (defaults to environment variable or 'us-east-1')
    
    Returns:
        boto3 client configured for the appropriate environment
    """
    # Check if we're running locally with LocalStack
    endpoint_url = os.getenv('AWS_ENDPOINT_URL')
    is_local = endpoint_url is not None
    
    # AWS credentials
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', 'test')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
    
    # Region
    if region_name is None:
        region_name = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    # Configuration
    config = Config(
        region_name=region_name,
        retries={'max_attempts': 3}
    )
    
    if is_local:
        # LocalStack configuration
        return boto3.client(
            service_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            config=config
        )
    else:
        # Production AWS configuration
        return boto3.client(
            service_name,
            region_name=region_name,
            config=config
        )

# Convenience functions for common AWS services
def get_lambda_client():
    """Get AWS Lambda client."""
    return get_aws_client('lambda')

def get_sqs_client():
    """Get AWS SQS client."""
    return get_aws_client('sqs')

def get_s3_client():
    """Get AWS S3 client."""
    return get_aws_client('s3')

def get_ecr_client():
    """Get AWS ECR client."""
    return get_aws_client('ecr')

def get_ecs_client():
    """Get AWS ECS client."""
    return get_aws_client('ecs')

def get_logs_client():
    """Get AWS CloudWatch Logs client."""
    return get_aws_client('logs')

def get_iam_client():
    """Get AWS IAM client."""
    return get_aws_client('iam')

def get_cloudwatch_client():
    """Get AWS CloudWatch client."""
    return get_aws_client('cloudwatch') 