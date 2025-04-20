# Summarization Service

A containerized service for summarizing text using large language models. This service complements the OCR service by providing text summarization capabilities through a simple REST API.

## Features

- **Asynchronous Processing**: Submit text for summarization and retrieve results when ready
- **Status Tracking**: Monitor the status of summarization jobs
- **Simple REST API**: Easy integration with existing applications
- **Docker-based**: Runs in containers for easy deployment and scaling
- **No IAM Required**: Works without AWS permissions or roles

## Architecture

This service uses a container-based architecture:
![Slide1](https://github.com/user-attachments/assets/8263deb4-c9c0-4a88-83c2-02b4e7653522)

1. **Application Container** (Flask):
   - Handles API requests
   - Processes text using LLM APIs
   - Manages document state

2. **Redis Container**:
   - Tracks processing status
   - Provides fast status lookups
   - Persists data between restarts

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/summarize` | POST | Submit text for summarization |
| `/check-status/{document_id}` | GET | Check processing status |
| `/result/{document_id}` | GET | Get the summarization result |
| `/health` | GET | Service health check |

## Setup and Deployment

### Prerequisites

- Docker and Docker Compose
- LLM API key (from xAI or other provider)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/cs6650distributedLLMs/summary_service.git
   cd summary_service
   ```

2. Set your API key:
   ```bash
   export GROKX_API_KEY=your-api-key-here
   ```

3. Start the service:
   ```bash
   ./run.sh
   ```

## Usage

### Using the Client Script

The included `client.py` script provides a simple way to interact with the API:

```bash
# Check service health
python client.py --action health

# Summarize text from a file
python client.py --action summarize --text-file document.txt --poll

# Summarize text from stdin
cat document.txt | python client.py --action summarize --poll

# Check status of a job
python client.py --action status --document-id your-document-id

# Get the result of a completed job
python client.py --action result --document-id your-document-id
```

### API Examples

Submit text for summarization:
```bash
curl -X POST http://localhost:5001/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc123",
    "text": "Text to summarize goes here..."
  }'
```

Check status:
```bash
curl http://localhost:5001/check-status/doc123
```

Get result:
```bash
curl http://localhost:5001/result/doc123
```

## Integration with OCR Service

Use IP add: ```35.81.24.90```

## Troubleshooting

- **View logs**: `docker-compose logs -f app`
- **Restart the service**: `docker-compose down && docker-compose up -d`
- **Check Redis**: `docker exec -it summary_service-redis-1 redis-cli`

## License

MIT
