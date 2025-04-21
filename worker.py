import os
import json
import time
import boto3
import redis
import requests
import logging
import signal
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('xai-worker')

# Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')
XAI_API_KEY = os.environ.get('GROKX_API_KEY', '')
XAI_API_URL = os.environ.get('GROKX_API_URL', 'https://api.x.ai/v1/chat/completions')
POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', 5))
MAX_VISIBILITY_TIMEOUT = int(os.environ.get('MAX_VISIBILITY_TIMEOUT', 300))  # 5 minutes

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        ssl=REDIS_SSL,
        decode_responses=True
    )
    redis_client.ping()  # Test connection
    logger.info("Redis connection successful")
except Exception as e:
    logger.error(f"Redis connection failed: {str(e)}")
    sys.exit(1)

# Initialize AWS SQS client
try:
    sqs_client = boto3.client('sqs', region_name=AWS_REGION)
    logger.info(f"SQS client initialized for region {AWS_REGION}")
except Exception as e:
    logger.error(f"SQS client initialization failed: {str(e)}")
    sys.exit(1)

def update_status(document_id, status, error_message=None):
    """
    Update the status of a document in Redis
    """
    try:
        # Update status
        redis_client.set(f"summarize_status:{document_id}", status)
        
        # Update error message if provided
        if error_message and status == 'error':
            redis_client.set(f"summarize_error:{document_id}", error_message)
            logger.error(f"Document {document_id}: {error_message}")
    
    except Exception as e:
        logger.error(f"Error updating status for {document_id}: {str(e)}")

def call_xai_api(text):
    """
    Call the X.AI API to summarize text
    """
    max_retries = 3
    retry_delay = 2  # seconds
    
    headers = {
        'Authorization': f'Bearer {XAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Prepare the prompt for the LLM
    prompt = f"""Please summarize the following text concisely while preserving the key information:

{text}

Summary:"""
    
    payload = {
        'model': 'grok-2-latest',
        'messages': [
            {'role': 'system', 'content': 'You are a helpful assistant that specializes in summarizing documents.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,  # Lower temperature for more focused summaries
        'max_tokens': 1000   # Adjust based on your summarization needs
    }
    
    logger.info(f"Calling X.AI API with {len(text)} characters of text")
    
    # Implement retry logic
    for attempt in range(max_retries):
        try:
            response = requests.post(
                XAI_API_URL,
                headers=headers,
                json=payload,
                timeout=60  # Longer timeout for large documents
            )
            
            # Log response status
            logger.info(f"API response status: {response.status_code}")
            
            # Raise exception for 4xx/5xx responses
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Extract the summary from the response
            if 'choices' in response_data and len(response_data['choices']) > 0:
                summary = response_data['choices'][0]['message']['content']
                logger.info(f"Summary generated successfully ({len(summary)} characters)")
                return summary
            else:
                logger.error(f"Unexpected API response format: {json.dumps(response_data)[:500]}")
                raise Exception("Unexpected API response format")
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"API request failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                
                # Log detailed error information
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text[:1000]}")
                
                # Exponential backoff
                backoff_time = retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
            else:
                # Log detailed error on final attempt
                error_msg = f"Failed to call X.AI API after {max_retries} attempts: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f"\nResponse body: {e.response.text[:1000]}"
                logger.error(error_msg)
                raise Exception(f"Failed to call X.AI API after {max_retries} attempts: {str(e)}")
    
    raise Exception("Failed to get summary from X.AI API")

def process_message(message):
    """
    Process a message from the SQS queue
    """
    try:
        # Parse the message body
        body = json.loads(message['Body'])
        document_id = body.get('document_id')
        text = body.get('text')
        
        logger.info(f"Processing document: {document_id}")
        
        if not text:
            # Try to get text from Redis
            text = redis_client.get(f"summarize_text:{document_id}")
            
            if not text:
                error_message = "No text found to summarize"
                update_status(document_id, 'error', error_message)
                return False
        
        # Update status to processing
        update_status(document_id, 'processing')
        
        # Call X.AI API to summarize the text
        try:
            summary = call_xai_api(text)
            
            # Store the result in Redis
            redis_client.set(f"summarize_result:{document_id}", summary)
            
            # Update status to completed
            update_status(document_id, 'completed')
            
            logger.info(f"Document {document_id} processed successfully")
            return True
            
        except Exception as e:
            error_message = str(e)
            update_status(document_id, 'error', error_message)
            logger.error(f"Error processing document {document_id}: {error_message}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return False

# Replace the process_queue function with this version that uses Redis instead of SQS
def process_queue():
    """
    Main function to process messages from a Redis-based queue instead of SQS
    """
    logger.info("Starting to poll Redis queue for documents")
    
    while True:
        try:
            # Check for documents in the Redis queue
            document_id = redis_client.lpop("summarize_queue")
            
            if document_id:
                logger.info(f"Found document to process: {document_id}")
                
                # Get the text from Redis
                text = redis_client.get(f"summarize_text:{document_id}")
                
                if text:
                    try:
                        # Update status to processing
                        update_status(document_id, 'processing')
                        
                        # Process the document
                        summary = call_xai_api(text)
                        
                        # Store the result
                        redis_client.set(f"summarize_result:{document_id}", summary)
                        
                        # Update status to completed
                        update_status(document_id, 'completed')
                        
                        logger.info(f"Document {document_id} processed successfully")
                    except Exception as e:
                        error_message = str(e)
                        update_status(document_id, 'error', error_message)
                        logger.error(f"Error processing document {document_id}: {error_message}")
                else:
                    logger.error(f"No text found for document {document_id}")
                    update_status(document_id, 'error', 'No text found to summarize')
            else:
                # No documents in queue, wait before checking again
                time.sleep(POLLING_INTERVAL)
                
        except Exception as e:
            logger.error(f"Error in queue processing: {str(e)}")
            time.sleep(POLLING_INTERVAL)

def handle_shutdown(sig, frame):
    """
    Handle shutdown gracefully
    """
    logger.info("Shutdown signal received, exiting...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Log worker information
    logger.info("X.AI Summarization Worker")
    logger.info(f"SQS Queue: {SQS_QUEUE_URL}")
    logger.info(f"X.AI API URL: {XAI_API_URL}")
    
    # Validate required configuration
    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable is required")
        sys.exit(1)
        
    if not XAI_API_KEY:
        logger.error("GROKX_API_KEY environment variable is required")
        sys.exit(1)
    
    # Start processing the queue
    process_queue()