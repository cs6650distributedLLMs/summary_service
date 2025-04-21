#!/bin/bash

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "AWS credentials not configured or invalid. Please run 'aws configure' first."
    exit 1
fi

# Set default region if not specified
AWS_REGION=${AWS_REGION:-us-west-2}

# Create SQS queue
echo "Creating SQS queue for summarization service in region $AWS_REGION..."
QUEUE_NAME="summarization-queue"

# Create queue
QUEUE_URL=$(aws sqs create-queue \
    --queue-name $QUEUE_NAME \
    --attributes "VisibilityTimeout=300" \
    --region $AWS_REGION \
    --output json \
    | jq -r .QueueUrl)

if [ -z "$QUEUE_URL" ]; then
    echo "Failed to create SQS queue."
    exit 1
fi

echo "SQS queue created successfully!"
echo "Queue URL: $QUEUE_URL"
echo ""
echo "To use this queue with the summarization service, set the environment variable:"
echo "export SQS_QUEUE_URL=\"$QUEUE_URL\""
echo ""
echo "You can also add a dead-letter queue for better error handling:"
echo "aws sqs create-queue --queue-name \"$QUEUE_NAME-dlq\" --region $AWS_REGION"