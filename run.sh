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

# Start the services
echo "Starting Summarization Service..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to start..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "Summarization Service is now running!"
    echo ""
    echo "API endpoints:"
    echo "  POST http://localhost:5000/summarize"
    echo "  GET  http://localhost:5000/check-status/{document_id}"
    echo "  GET  http://localhost:5000/result/{document_id}"
    echo "  GET  http://localhost:5000/health"
    echo ""
    echo "To check logs:"
    echo "  docker-compose logs -f app"
    echo ""
    echo "To stop the service:"
    echo "  docker-compose down"
else
    echo "Error: Failed to start services. Check logs with 'docker-compose logs'"
    exit 1
fi