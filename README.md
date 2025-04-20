# Text Summarization Service

A serverless, scalable service for summarizing text using GrokX AI, built with AWS Lambda, API Gateway, DynamoDB, and ElastiCache.

## Architecture

This service follows an asynchronous processing pattern:

1. **API Gateway** serves as the entry point for all requests
2. **Lambda Functions**:
   - **API Handler**: Handles web requests and initiates summarization
   - **Processor**: Performs the actual summarization asynchronously
3. **DynamoDB**: Stores document text and summaries
4. **ElastiCache Redis**: Stores document processing status for fast lookups

## API Endpoints

- `POST /summarize` - Submit text for summarization
- `GET /check-status/{document_id}` - Check processing status
- `GET /result/{document_id}` - Get the summarization result
- `GET /health` - Service health check

## Setup and Deployment

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform installed
- Python 3.8+
- GrokX API key

### Environment Variables

Set the following environment variables before deployment:

```bash
export GROKX_API_KEY="your-grokx-api-key"
export VPC_ID="vpc-xxxxxxxx"
export SUBNET_IDS="subnet-xxxxxxxx,subnet-yyyyyyyy"
```

### Deployment

1. Clone this repository
2. Navigate to the repository directory
3. Run the deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
- Create Lambda deployment packages
- Initialize Terraform
- Deploy all required infrastructure
- Output the API URL

## Client Usage

A sample client is provided to demonstrate API usage:

```bash
# Check service health
python client.py --api-url https://your-api-url --action health

# Submit text for summarization
python client.py --api-url https://your-api-url --action summarize --text-file sample.txt --poll

# Check status
python client.py --api-url https://your-api-url --action status --document-id <your-document-id>

# Get result
python client.py --api-url https://your-api-url --action result --document-id <your-document-id>
```

## Integration with App Controller

To integrate with your existing app controller:

1. Submit text for summarization:

```
POST https://your-api-url/summarize
Content-Type: application/json

{
  "document_id": "your-document-id",
  "text": "Text to summarize..."
}
```

2. Poll for status:

```
GET https://your-api-url/check-status/your-document-id
```

3. Retrieve summary when status is "completed":

```
GET https://your-api-url/result/your-document-id
```

## Security Considerations

- The Lambda functions run within a VPC for network isolation
- API keys should be managed securely (consider using AWS Secrets Manager)
- In production, restrict security group rules to specific CIDR blocks

## Cost Optimization

- Lambda functions use minimal resources (256MB/512MB RAM)
- DynamoDB uses on-demand pricing for cost efficiency
- ElastiCache uses a t3.micro instance to minimize costs

## Monitoring and Maintenance

- CloudWatch Logs are enabled for all Lambda functions
- Consider setting up CloudWatch Alarms for error rates and duration metrics
- Regularly update dependencies and the GrokX API integration

## Limitations

- Maximum document size is limited by Lambda payload size (10MB)
- Long-running summarizations are limited by Lambda timeout (5 minutes max)