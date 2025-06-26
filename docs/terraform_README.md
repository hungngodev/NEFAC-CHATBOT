# NEFAC Infrastructure with Terraform

This directory contains the Terraform configuration for deploying the NEFAC application infrastructure on AWS, including Lambda functions, SQS queues, ECS services, and supporting resources.

## Architecture Overview

The infrastructure includes:

- **VPC & Networking**: Custom VPC with public and private subnets, NAT Gateway, and security groups
- **Lambda Functions**: Serverless functions for text processing with spaCy and ML pipelines
- **SQS Queues**: Message queues for orchestrating the text processing pipeline
- **ECS Services**: Containerized backend and frontend applications
- **ECR Repositories**: Container image repositories
- **IAM Roles & Policies**: Secure access control for all services
- **CloudWatch**: Logging and monitoring
- **API Gateway**: HTTP endpoints for Lambda functions

## Prerequisites

Before using this Terraform configuration, ensure you have:

1. **Terraform** (>= 1.0) installed
2. **AWS CLI** installed and configured
3. **AWS credentials** with appropriate permissions
4. **Docker** (for building container images)

### Installing Prerequisites

#### Terraform

```bash
# macOS
brew install terraform

# Linux
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs)"
sudo apt-get update && sudo apt-get install terraform
```

#### AWS CLI

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

#### Configure AWS

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, region, and output format
```

## Quick Start

1. **Clone and navigate to the project**:

   ```bash
   cd terraform
   ```

2. **Copy the example configuration**:

   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

3. **Edit the configuration**:

   ```bash
   # Edit terraform.tfvars with your specific values
   nano terraform.tfvars
   ```

4. **Deploy the infrastructure**:
   ```bash
   ./deploy.sh full -e dev -r us-east-1
   ```

## Configuration

### Environment Variables

The deployment script uses these environment variables:

- `TF_VAR_environment`: Environment name (dev, staging, prod)
- `TF_VAR_aws_region`: AWS region

### terraform.tfvars

Key configuration options in `terraform.tfvars`:

```hcl
# AWS Configuration
aws_region = "us-east-1"
environment = "dev"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"

# Lambda Functions
lambda_functions = {
  text_processor = {
    filename      = "lambda_functions/text_processor.zip"
    function_name = "text-processor"
    handler       = "text_processor.lambda_handler"
    runtime       = "python3.9"
    timeout       = 300
    memory_size   = 512
    environment_vars = {
      CHUNK_SIZE     = "1000"
      PCA_COMPONENTS = "256"
    }
  }
}

# SQS Queues
sqs_queues = {
  text_processing_input = {
    name                     = "text-processing-input"
    visibility_timeout       = 300
    message_retention_period = 1209600
    receive_wait_time        = 20
  }
}
```

## Deployment Commands

### Using the Deployment Script

```bash
# Initialize Terraform
./deploy.sh init

# Plan changes
./deploy.sh plan

# Apply changes
./deploy.sh apply

# Show outputs
./deploy.sh output

# Create Lambda deployment package
./deploy.sh package

# Full deployment (init, plan, apply)
./deploy.sh full -e dev -r us-east-1

# Destroy infrastructure
./deploy.sh destroy
```

### Using Terraform Directly

```bash
# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply

# Destroy
terraform destroy
```

## Lambda Functions

### Text Processor Function

The text processor Lambda function handles:

- **Text Chunking**: Using spaCy for intelligent sentence boundaries
- **Embedding Generation**: Transform text chunks to embeddings
- **PCA Dimensionality Reduction**: Reduce embedding dimensions

#### Deployment Package

Create the Lambda deployment package:

```bash
cd ../backend/lambda_functions
zip -r text_processor.zip text_processor.py
```

#### Environment Variables

- `CHUNK_SIZE`: Target size for text chunks (default: 1000)
- `PCA_COMPONENTS`: Number of PCA components (default: 256)

## SQS Queues

The infrastructure creates three main SQS queues:

1. **text-processing-input**: Receives text processing requests
2. **processed-chunks**: Stores processed text chunks
3. **embedding-results**: Stores final embedding results

### Queue Configuration

- **Visibility Timeout**: 300 seconds for input, 60 seconds for others
- **Message Retention**: 14 days
- **Long Polling**: 20 seconds
- **Dead Letter Queue**: Automatic retry with 3 attempts

## ECS Services

### Backend Service

- **CPU**: 256 units
- **Memory**: 512 MB
- **Port**: 8000
- **Desired Count**: 2 instances

### Frontend Service

- **CPU**: 128 units
- **Memory**: 256 MB
- **Port**: 80
- **Desired Count**: 2 instances

## Monitoring and Logging

### CloudWatch Logs

All Lambda functions and ECS services log to CloudWatch:

- **Log Retention**: 14 days
- **Log Groups**: Automatically created with proper naming

### CloudWatch Alarms

SQS queues have automatic alarms for:

- **Message Count**: Alerts when queue has >100 messages
- **Error Rate**: Monitors failed message processing

## Security

### IAM Roles

- **Lambda Role**: Basic execution + SQS/S3 access
- **ECS Task Role**: Application-level permissions
- **ECS Exec Role**: Container execution permissions

### Security Groups

- **ALB Security Group**: Allows HTTP/HTTPS traffic
- **ECS Security Group**: Allows traffic from ALB only

### Network Security

- **Private Subnets**: ECS services run in private subnets
- **NAT Gateway**: Private resources can access internet
- **VPC Endpoints**: For AWS service access (optional)

## Cost Optimization

### Recommendations

1. **Use Spot Instances**: For ECS tasks in dev/staging
2. **Reserved Instances**: For production workloads
3. **Lambda Provisioned Concurrency**: For consistent performance
4. **S3 Lifecycle Policies**: Archive old data
5. **CloudWatch Logs**: Set appropriate retention periods

### Estimated Costs (us-east-1)

- **VPC**: ~$50/month (NAT Gateway)
- **Lambda**: ~$10-50/month (depending on usage)
- **SQS**: ~$1-10/month (depending on messages)
- **ECS**: ~$50-200/month (depending on instance types)
- **CloudWatch**: ~$10-30/month

## Troubleshooting

### Common Issues

1. **Terraform State Lock**: If deployment fails, check for state locks
2. **IAM Permissions**: Ensure AWS credentials have sufficient permissions
3. **VPC Limits**: Check AWS account VPC limits
4. **Lambda Timeout**: Increase timeout for long-running functions

### Debug Commands

```bash
# Check AWS credentials
aws sts get-caller-identity

# Validate Terraform
terraform validate

# Check plan
terraform plan -detailed-exitcode

# View logs
aws logs describe-log-groups
```

## Development Workflow

### Local Development

1. Use LocalStack for local AWS service testing
2. Test Lambda functions locally with SAM CLI
3. Use Docker Compose for local container testing

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Deploy Infrastructure
  run: |
    cd terraform
    ./deploy.sh plan -e ${{ github.ref_name }}
    ./deploy.sh apply -e ${{ github.ref_name }}
```

## Contributing

1. **Fork the repository**
2. **Create a feature branch**
3. **Make changes**
4. **Test with `terraform plan`**
5. **Submit a pull request**

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review AWS documentation
3. Open an issue in the repository

## License

This project is licensed under the MIT License.
