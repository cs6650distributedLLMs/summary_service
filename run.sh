#!/bin/bash

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check for GROKX API key
if [ -z "$GROKX_API_KEY" ]; then
    echo "Please set the GROKX_API_KEY environment variable:"
    echo "export GROKX_API_KEY=your-api-key"
    exit 1
fi

# Check for SQS Queue URL or use local mode
if [ -z "$SQS_QUEUE_URL" ]; then
    echo "SQS_QUEUE_URL not set. Using local mode without actual SQS."
    echo "For production, set the SQS_QUEUE_URL environment variable."
fi

# Create AWS credentials directory if it doesn't exist
if [ ! -d ~/.aws ]; then
    mkdir -p ~/.aws
fi

# Check for AWS credentials
if [ ! -f ~/.aws/credentials ] && [ ! -z "$SQS_QUEUE_URL" ]; then
    echo "AWS credentials not found. Setting up minimal credentials file."
    
    # Prompt for AWS credentials if needed
    read -p "Enter AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -p "Enter AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    read -p "Enter AWS Region [us-west-2]: " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-west-2}
    
    # Create credentials file
    cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
region = $AWS_REGION
EOF

    echo "AWS credentials created."
fi

# Set worker count
WORKER_COUNT=${WORKER_COUNT:-2}
echo "Starting $WORKER_COUNT worker containers"

# Start the services
echo "Starting Summarization Service..."
docker-compose up -d --scale worker=$WORKER_COUNT

# Wait for services to start
echo "Waiting for services to start..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "Summarization Service is now running!"
    echo ""
    echo "API endpoints:"
    echo "  POST http://localhost:5001/summarize"
    echo "  GET  http://localhost:5001/check-status/{document_id}"
    echo "  GET  http://localhost:5001/result/{document_id}"
    echo "  GET  http://localhost:5001/health"
    echo ""
    echo "To view logs:"
    echo "  API service:  docker-compose logs -f api"
    echo "  Worker:       docker-compose logs -f worker"
    echo "  All services: docker-compose logs -f"
    echo ""
    echo "To stop the service:"
    echo "  docker-compose down"
    echo ""
    echo "To scale workers up or down:"
    echo "  docker-compose up -d --scale worker=<count>"
else
    echo "Error: Failed to start services. Check logs with 'docker-compose logs'"
    exit 1
fi