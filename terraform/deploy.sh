#!/bin/bash

# Terraform deployment script for NEFAC infrastructure
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists terraform; then
        print_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    if ! command_exists aws; then
        print_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to validate Terraform configuration
validate_terraform() {
    print_status "Validating Terraform configuration..."
    
    if ! terraform validate; then
        print_error "Terraform validation failed"
        exit 1
    fi
    
    print_success "Terraform configuration is valid"
}

# Function to initialize Terraform
init_terraform() {
    print_status "Initializing Terraform..."
    
    if ! terraform init; then
        print_error "Terraform initialization failed"
        exit 1
    fi
    
    print_success "Terraform initialized successfully"
}

# Function to plan Terraform changes
plan_terraform() {
    print_status "Planning Terraform changes..."
    
    if ! terraform plan -out=tfplan; then
        print_error "Terraform plan failed"
        exit 1
    fi
    
    print_success "Terraform plan completed successfully"
}

# Function to apply Terraform changes
apply_terraform() {
    print_status "Applying Terraform changes..."
    
    if ! terraform apply tfplan; then
        print_error "Terraform apply failed"
        exit 1
    fi
    
    print_success "Terraform apply completed successfully"
}

# Function to show outputs
show_outputs() {
    print_status "Showing Terraform outputs..."
    
    terraform output
}

# Function to create Lambda deployment package
create_lambda_package() {
    print_status "Creating Lambda deployment package..."
    
    cd ../backend
    
    # Check if lambda_functions directory exists
    if [ ! -d "lambda_functions" ]; then
        print_warning "lambda_functions directory not found. Creating basic structure..."
        mkdir -p lambda_functions
        echo "# Placeholder for Lambda functions" > lambda_functions/README.md
    fi
    
    # Create deployment package
    if [ -f "lambda_functions/text_processor.py" ]; then
        cd lambda_functions
        zip -r text_processor.zip text_processor.py
        cd ..
        print_success "Lambda deployment package created"
    else
        print_warning "text_processor.py not found. Please create it before deploying."
    fi
    
    cd ../terraform
}

# Function to cleanup
cleanup() {
    print_status "Cleaning up..."
    rm -f tfplan
    print_success "Cleanup completed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  init      - Initialize Terraform"
    echo "  plan      - Plan Terraform changes"
    echo "  apply     - Apply Terraform changes"
    echo "  destroy   - Destroy infrastructure"
    echo "  output    - Show Terraform outputs"
    echo "  package   - Create Lambda deployment package"
    echo "  full      - Run full deployment (init, plan, apply)"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV  - Set environment (dev, staging, prod)"
    echo "  -r, --region REGION    - Set AWS region"
    echo "  -h, --help             - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 init"
    echo "  $0 plan"
    echo "  $0 apply"
    echo "  $0 full -e dev -r us-east-1"
}

# Parse command line arguments
ENVIRONMENT="dev"
REGION="us-east-1"
COMMAND=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        init|plan|apply|destroy|output|package|full)
            COMMAND="$1"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if command is provided
if [ -z "$COMMAND" ]; then
    print_error "No command specified"
    show_usage
    exit 1
fi

# Set environment variables
export TF_VAR_environment="$ENVIRONMENT"
export TF_VAR_aws_region="$REGION"

print_status "Environment: $ENVIRONMENT"
print_status "Region: $REGION"

# Execute command
case $COMMAND in
    init)
        check_prerequisites
        init_terraform
        ;;
    plan)
        check_prerequisites
        validate_terraform
        plan_terraform
        ;;
    apply)
        check_prerequisites
        validate_terraform
        apply_terraform
        show_outputs
        cleanup
        ;;
    destroy)
        check_prerequisites
        print_warning "This will destroy all infrastructure. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            terraform destroy -auto-approve
            cleanup
        else
            print_status "Destroy cancelled"
        fi
        ;;
    output)
        show_outputs
        ;;
    package)
        create_lambda_package
        ;;
    full)
        check_prerequisites
        create_lambda_package
        init_terraform
        validate_terraform
        plan_terraform
        apply_terraform
        show_outputs
        cleanup
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac

print_success "Command '$COMMAND' completed successfully" 