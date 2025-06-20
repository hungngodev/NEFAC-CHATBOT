# AWS Infrastructure and Utilities

This directory contains AWS-related infrastructure code and utilities for the NEFAC project.

## Structure

```
aws/
├── __init__.py              # Package initialization and exports
├── aws_config.py           # AWS client configuration and setup
├── lambda_utils.py         # Lambda function management utilities
├── sqs_utils.py            # SQS queue management utilities
├── lambda_functions/       # Lambda function code
│   ├── requirements.txt    # Lambda dependencies
│   └── text_processor.py  # Text processing Lambda function
├── test_localstack.py      # LocalStack testing utilities
├── setup_localstack.sh     # LocalStack setup script
└── README.md              # This file
```

## Components

### AWS Configuration (`aws_config.py`)

- Provides unified AWS client configuration for both LocalStack (local development) and production AWS
- Includes convenience functions for common AWS services (Lambda, SQS, S3, etc.)

### Lambda Utilities (`lambda_utils.py`)

- `LambdaManager` class for deploying, updating, and managing Lambda functions
- Functions for creating deployment packages and invoking Lambda functions
- Example deployment function for the text processor

### SQS Utilities (`sqs_utils.py`)

- `SQSManager` class for managing SQS queues and messages
- Functions for creating queues, sending/receiving messages, and queue management
- Text processing pipeline queue setup

### Lambda Functions (`lambda_functions/`)

- Contains actual Lambda function code
- `text_processor.py` - Processes text chunks for the RAG system
- `requirements.txt` - Dependencies for Lambda functions

### LocalStack Integration

- `test_localstack.py` - Testing utilities for LocalStack
- `setup_localstack.sh` - Setup script for LocalStack environment

## Usage

### Local Development with LocalStack

1. Start LocalStack:

```bash
docker-compose up localstack
```

2. Set up the environment:

```bash
cd aws
./setup_localstack.sh
```

3. Test the setup:

```bash
python test_localstack.py
```

### Using AWS Utilities

```python
from aws import LambdaManager, SQSManager, get_lambda_client

# Create Lambda manager
lambda_manager = LambdaManager()

# Create SQS manager
sqs_manager = SQSManager()

# Get AWS clients
lambda_client = get_lambda_client()
sqs_client = get_sqs_client()
```

## Environment Variables

For LocalStack development:

- `AWS_ENDPOINT_URL=http://localhost:4566`
- `AWS_ACCESS_KEY_ID=test`
- `AWS_SECRET_ACCESS_KEY=test`
- `AWS_DEFAULT_REGION=us-east-1`

For production AWS:

- Standard AWS credentials (IAM roles, access keys, etc.)
- No `AWS_ENDPOINT_URL` (uses production AWS endpoints)
