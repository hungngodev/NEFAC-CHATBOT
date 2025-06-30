#!/bin/bash

# Setup script for LocalStack development environment

set -e

echo "🚀 Setting up LocalStack development environment..."

# Check if we're in the backend directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: This script must be run from the backend directory"
    exit 1
fi

# Install AWS dependencies
echo "📦 Installing AWS dependencies..."
poetry add boto3 botocore moto

# Install ML dependencies for Lambda functions
echo "🧠 Installing ML dependencies for Lambda functions..."
poetry add spacy scikit-learn numpy

# Download spaCy model for Lambda functions
echo "📥 Downloading spaCy model..."
poetry run python -m spacy download en_core_web_sm

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p lambda_functions
mkdir -p lambda_layers

# Make test script executable
chmod +x test_localstack.py

echo "✅ LocalStack setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Start LocalStack: docker-compose up localstack"
echo "2. Test the setup: python test_localstack.py"
echo "3. Deploy Lambda functions: python -c 'from lambda_utils import deploy_text_processor; deploy_text_processor()'"
echo ""
echo "🔗 LocalStack will be available at: http://localhost:4566"
echo "🔗 LocalStack Web UI: http://localhost:4566/_localstack/health" 