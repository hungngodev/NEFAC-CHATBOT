# NEFAC AWS Infrastructure Setup

This document provides a comprehensive guide for setting up AWS infrastructure for the NEFAC project, including both local development with LocalStack and production deployment with Terraform.

## 🏗️ Architecture Overview

The NEFAC infrastructure consists of:

### Core Services

- **Lambda Functions**: Serverless text processing with spaCy and ML pipelines
- **SQS Queues**: Message orchestration for the processing pipeline
- **ECS Services**: Containerized backend and frontend applications
- **ECR Repositories**: Container image storage
- **S3 Buckets**: Data storage and artifacts

### Supporting Infrastructure

- **VPC & Networking**: Secure network isolation
- **IAM Roles & Policies**: Access control
- **CloudWatch**: Monitoring and logging
- **API Gateway**: HTTP endpoints
- **Application Load Balancer**: Traffic distribution

## 🚀 Quick Start

### 1. Local Development Setup

```bash
# Navigate to backend directory
cd backend

# Run LocalStack setup
./setup_localstack.sh

# Start LocalStack
docker-compose up localstack

# Test the setup
python test_localstack.py
```

### 2. Production Deployment

```bash
# Navigate to terraform directory
cd terraform

# Copy configuration
cp terraform.tfvars.example terraform.tfvars

# Edit configuration
nano terraform.tfvars

# Deploy infrastructure
./deploy.sh full -e dev -r us-east-1
```

## 📁 Project Structure

```
nefac/
├── backend/
│   ├── aws_config.py          # AWS client configuration
│   ├── lambda_functions/      # Lambda function code
│   │   ├── text_processor.py  # Text processing Lambda
│   │   └── requirements.txt   # Lambda dependencies
│   ├── lambda_utils.py        # Lambda deployment utilities
│   ├── sqs_utils.py           # SQS queue management
│   ├── test_localstack.py     # LocalStack testing
│   └── setup_localstack.sh    # LocalStack setup script
├── terraform/
│   ├── main.tf                # Main Terraform configuration
│   ├── variables.tf           # Input variables
│   ├── outputs.tf             # Output values
│   ├── deploy.sh              # Deployment script
│   ├── terraform.tfvars.example # Example configuration
│   └── modules/               # Terraform modules
│       ├── vpc/               # VPC and networking
│       ├── lambda/            # Lambda functions
│       ├── sqs/               # SQS queues
│       ├── iam/               # IAM roles and policies
│       └── s3/                # S3 buckets
└── docker-compose.yml         # LocalStack configuration
```

## 🔧 LocalStack Setup

### Purpose

LocalStack provides a local AWS environment for development and testing without incurring AWS costs.

### Services Available

- Lambda Functions
- SQS Queues
- S3 Buckets
- ECR Repositories
- ECS Services
- CloudWatch Logs
- IAM (basic)

### Configuration

```yaml
# docker-compose.yml
localstack:
  image: localstack/localstack:latest
  ports:
    - "4566:4566"
  environment:
    - SERVICES=lambda,sqs,s3,ecr,ecs,logs,iam,cloudwatch
    - DEBUG=1
    - LAMBDA_EXECUTOR=docker
```

### Usage

```python
# Example: Using LocalStack in Python
from aws_config import get_lambda_client

# Automatically uses LocalStack when AWS_ENDPOINT_URL is set
lambda_client = get_lambda_client()
functions = lambda_client.list_functions()
```

## 🏗️ Terraform Infrastructure

### Modules Overview

#### VPC Module (`modules/vpc/`)

- Custom VPC with public/private subnets
- Internet Gateway and NAT Gateway
- Route tables and security groups
- Multi-AZ deployment

#### Lambda Module (`modules/lambda/`)

- Lambda function deployment
- Function URLs for HTTP triggers
- SQS event source mappings
- CloudWatch log groups
- IAM permissions

#### SQS Module (`modules/sqs/`)

- Queue creation with configurable attributes
- Dead letter queue setup
- Queue policies
- CloudWatch alarms

#### IAM Module (`modules/iam/`)

- Lambda execution role
- ECS task and execution roles
- Service-specific policies
- Least privilege access

#### S3 Module (`modules/s3/`)

- Bucket creation with encryption
- Versioning and lifecycle policies
- Public access blocking
- Cost optimization

### Deployment Process

1. **Initialize**: Download providers and modules
2. **Plan**: Review infrastructure changes
3. **Apply**: Deploy infrastructure
4. **Verify**: Check outputs and test services

```bash
# Full deployment
./deploy.sh full -e dev -r us-east-1

# Step-by-step
./deploy.sh init
./deploy.sh plan
./deploy.sh apply
```

## 🤖 Lambda Functions

### Text Processor Function

**Purpose**: Process text documents using spaCy for chunking and ML for embeddings

**Features**:

- Intelligent sentence boundary detection
- Configurable chunk sizes
- Embedding generation (placeholder for Llama)
- PCA dimensionality reduction
- SQS integration for orchestration

**Configuration**:

```python
# Environment variables
CHUNK_SIZE = "1000"        # Characters per chunk
PCA_COMPONENTS = "256"     # Reduced dimensions
ENVIRONMENT = "production"
```

**Deployment**:

```bash
# Create deployment package
cd backend/lambda_functions
zip -r text_processor.zip text_processor.py

# Deploy via Terraform
cd ../../terraform
./deploy.sh apply
```

## 📨 SQS Queue Pipeline

### Queue Structure

1. **text-processing-input**: Receives processing requests
2. **processed-chunks**: Stores chunked text
3. **embedding-results**: Stores final embeddings

### Message Flow

```
Input Text → SQS → Lambda → Chunks → SQS → Lambda → Embeddings → SQS
```

### Configuration

```hcl
sqs_queues = {
  text_processing_input = {
    visibility_timeout       = 300    # 5 minutes
    message_retention_period = 1209600 # 14 days
    receive_wait_time        = 20     # Long polling
    max_receive_count        = 3      # DLQ after 3 failures
  }
}
```

## 🐳 Container Deployment

### ECS Services

#### Backend Service

- **Image**: `nefac-backend:latest`
- **CPU**: 256 units (0.25 vCPU)
- **Memory**: 512 MB
- **Port**: 8000
- **Instances**: 2 (for high availability)

#### Frontend Service

- **Image**: `nefac-frontend:latest`
- **CPU**: 128 units (0.125 vCPU)
- **Memory**: 256 MB
- **Port**: 80
- **Instances**: 2 (for high availability)

### ECR Repositories

```hcl
ecr_repositories = {
  nefac_backend = {
    name                 = "nefac-backend"
    image_tag_mutability = "MUTABLE"
    scan_on_push         = true
  }
  nefac_frontend = {
    name                 = "nefac-frontend"
    image_tag_mutability = "MUTABLE"
    scan_on_push         = true
  }
}
```

## 🔒 Security Configuration

### IAM Roles

- **Lambda Role**: Basic execution + SQS/S3 access
- **ECS Task Role**: Application-level permissions
- **ECS Exec Role**: Container execution permissions

### Security Groups

- **ALB**: Allows HTTP/HTTPS from internet
- **ECS**: Allows traffic from ALB only
- **Private**: No direct internet access

### Network Security

- **Private Subnets**: ECS services isolated
- **NAT Gateway**: Controlled internet access
- **VPC Endpoints**: Secure AWS service access

## 📊 Monitoring & Logging

### CloudWatch Logs

- **Retention**: 14 days
- **Log Groups**: Auto-created for each service
- **Structured Logging**: JSON format

### CloudWatch Alarms

- **SQS Queue Depth**: Alert on message buildup
- **Lambda Errors**: Monitor function failures
- **ECS Service Health**: Track container health

### Metrics

- **Lambda**: Invocations, duration, errors
- **SQS**: Message count, age, throughput
- **ECS**: CPU, memory, network usage

## 💰 Cost Optimization

### Recommendations

1. **Use Spot Instances**: For dev/staging environments
2. **Reserved Instances**: For production workloads
3. **Lambda Provisioned Concurrency**: For consistent performance
4. **S3 Lifecycle Policies**: Archive old data
5. **CloudWatch Logs**: Set appropriate retention

### Estimated Monthly Costs (us-east-1)

- **VPC**: ~$50 (NAT Gateway)
- **Lambda**: ~$10-50 (depending on usage)
- **SQS**: ~$1-10 (depending on messages)
- **ECS**: ~$50-200 (depending on instance types)
- **CloudWatch**: ~$10-30
- **Total**: ~$121-340/month

## 🧪 Testing

### LocalStack Testing

```bash
# Run comprehensive tests
cd backend
python test_localstack.py

# Test individual services
python -c "from aws_config import get_lambda_client; print('Lambda OK')"
python -c "from sqs_utils import SQSManager; print('SQS OK')"
```

### Terraform Testing

```bash
# Validate configuration
cd terraform
terraform validate

# Plan changes
terraform plan

# Test specific modules
terraform plan -target=module.lambda
```

## 🚨 Troubleshooting

### Common Issues

#### LocalStack

1. **Port conflicts**: Change port 4566 if needed
2. **Docker permissions**: Ensure Docker access
3. **Service startup**: Check LocalStack logs

#### Terraform

1. **State locks**: Check for concurrent operations
2. **IAM permissions**: Verify AWS credentials
3. **VPC limits**: Check account limits
4. **Lambda timeout**: Increase function timeout

### Debug Commands

```bash
# Check AWS credentials
aws sts get-caller-identity

# Validate Terraform
terraform validate

# Check LocalStack health
curl http://localhost:4566/_localstack/health

# View Lambda logs
aws logs describe-log-groups
```

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy Infrastructure
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: hashicorp/setup-terraform@v2
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v2
      - name: Deploy
        run: |
          cd terraform
          ./deploy.sh plan -e ${{ github.ref_name }}
          ./deploy.sh apply -e ${{ github.ref_name }}
```

## 📚 Additional Resources

### Documentation

- [LocalStack Documentation](https://docs.localstack.cloud/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [Amazon ECS Developer Guide](https://docs.aws.amazon.com/ecs/)

### Tools

- [AWS CLI](https://aws.amazon.com/cli/)
- [Terraform CLI](https://www.terraform.io/cli)
- [LocalStack CLI](https://docs.localstack.cloud/getting-started/installation/)

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**
3. **Make changes**
4. **Test locally with LocalStack**
5. **Test with Terraform plan**
6. **Submit a pull request**

## 📞 Support

For issues and questions:

1. Check the troubleshooting section
2. Review AWS and Terraform documentation
3. Open an issue in the repository
4. Contact the development team

---

**Note**: This infrastructure setup provides a solid foundation for the NEFAC project. Adjust configurations based on your specific requirements and scale as needed.
