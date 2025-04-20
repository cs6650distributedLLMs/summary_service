#!/bin/bash
set -e

# Configuration
PROJECT_NAME="doc-summarizer"
AWS_REGION="us-west-2"
ENVIRONMENT="dev"

# Check for required environment variables
if [ -z "$GROKX_API_KEY" ]; then
  echo "Error: GROKX_API_KEY environment variable is required"
  exit 1
fi

if [ -z "$VPC_ID" ]; then
  echo "Error: VPC_ID environment variable is required"
  exit 1
fi

if [ -z "$SUBNET_IDS" ]; then
  echo "Error: SUBNET_IDS environment variable is required (comma-separated list)"
  exit 1
fi

# Create build directory
mkdir -p build
cd build

# Create directories for Lambda functions
mkdir -p api_handler
mkdir -p processor

# Create requirements file
cat > requirements.txt <<EOF
boto3==1.28.38
redis==4.6.0
requests==2.31.0
EOF

# Set up virtual environment
echo "Setting up virtual environment..."
python -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy Lambda code
echo "Copying Lambda function code..."
cp ../summarize.py api_handler/
cp ../processor.py processor/

# Package API handler Lambda
echo "Packaging API handler Lambda..."
cd api_handler
pip install -r ../requirements.txt -t ./
zip -r ../api_handler.zip ./*
cd ..

# Package processor Lambda
echo "Packaging processor Lambda..."
cd processor
pip install -r ../requirements.txt -t ./
zip -r ../processor.zip ./*
cd ..

# Prepare Terraform configuration
echo "Creating Terraform configuration..."

# Create terraform.tfvars file
cat > terraform.tfvars <<EOF
aws_region = "$AWS_REGION"
project_name = "$PROJECT_NAME"
environment = "$ENVIRONMENT"
vpc_id = "$VPC_ID"
subnet_ids = [${SUBNET_IDS//,/,}]
api_handler_zip_path = "api_handler.zip"
processor_zip_path = "processor.zip"
grokx_api_key = "$GROKX_API_KEY"
grokx_api_url = "https://api.grokx.ai/v1/chat/completions"
EOF

# Copy Terraform files
cp ../terraform/main.tf .
cp ../terraform/variables.tf .

# Initialize Terraform
echo "Initializing Terraform..."
terraform init

# Create execution plan
echo "Creating Terraform execution plan..."
terraform plan -out=tfplan

# Apply Terraform configuration
echo "Deploying infrastructure (you'll be prompted to confirm)..."
terraform apply tfplan

# Get API URL from Terraform output
API_URL=$(terraform output -raw api_url)

echo "Deployment completed successfully!"
echo "API URL: $API_URL"
echo ""
echo "You can use the following endpoints:"
echo "  - POST $API_URL/summarize"
echo "  - GET $API_URL/check-status/{document_id}"
echo "  - GET $API_URL/result/{document_id}"
echo "  - GET $API_URL/health"