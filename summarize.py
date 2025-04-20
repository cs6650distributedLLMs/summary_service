import json
import os
import uuid
import boto3
import redis
import requests
import time
from datetime import datetime

# Initialize AWS services
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

# Initialize Redis connection
redis_client = redis.Redis(
    host=os.environ['REDIS_HOST'],
    port=int(os.environ['REDIS_PORT']),
    password=os.environ.get('REDIS_PASSWORD', None),
    ssl=True if os.environ.get('REDIS_SSL', 'false').lower() == 'true' else False,
    decode_responses=True
)

# GrokX API configuration
# Get API credentials from environment variables
GROKX_API_URL = os.environ.get("GROK_API_URL", "https://api.x.ai/v1/chat/completions")
GROKX_API_KEY = os.environ.get("GROK_API_KEY")

def lambda_handler(event, context):
    """
    Main Lambda handler function that processes API Gateway events
    """
    # Get HTTP method and path
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    
    # Route to appropriate handler based on the path
    if http_method == 'POST' and path == '/summarize':
        return handle_summarize_request(event)
    elif http_method == 'GET' and path.startswith('/check-status/'):
        document_id = path.split('/')[-1]
        return handle_check_status(document_id)
    elif http_method == 'GET' and path.startswith('/result/'):
        document_id = path.split('/')[-1]
        return handle_get_result(document_id)
    elif http_method == 'GET' and path == '/health':
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'healthy'})
        }
    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Not found'})
        }

def handle_summarize_request(event):
    """
    Handle the initial summarization request
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate input
        if 'document_id' not in body or 'text' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameters (document_id or text)'})
            }
        
        document_id = body['document_id']
        text = body['text']
        
        # Check if document already exists
        status = redis_client.get(f"summarize_status:{document_id}")
        if status:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'already_processing',
                    'message': f'Document with ID {document_id} is already being processed'
                })
            }
        
        # Initialize status in Redis
        redis_client.set(f"summarize_status:{document_id}", "processing")
        
        # Store the original text and metadata in DynamoDB
        timestamp = datetime.utcnow().isoformat()
        table.put_item(
            Item={
                'document_id': document_id,
                'original_text': text,
                'status': 'processing',
                'created_at': timestamp,
                'updated_at': timestamp
            }
        )
        
        # Invoke the processing Lambda asynchronously
        lambda_client.invoke(
            FunctionName=os.environ['PROCESSOR_LAMBDA_NAME'],
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps({
                'document_id': document_id
            })
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'ok',
                'message': 'Summarization started'
            })
        }
    
    except Exception as e:
        print(f"Error in summarize request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_check_status(document_id):
    """
    Handle status check requests
    """
    try:
        # Get status from Redis for fast lookup
        status = redis_client.get(f"summarize_status:{document_id}")
        
        if not status:
            # Check DynamoDB if not in Redis
            response = table.get_item(
                Key={'document_id': document_id}
            )
            
            if 'Item' in response:
                status = response['Item'].get('status', 'unknown')
                # Update Redis cache
                redis_client.set(f"summarize_status:{document_id}", status)
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': 'Document not found'})
                }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': status})
        }
    
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_get_result(document_id):
    """
    Handle result retrieval requests
    """
    try:
        # Get status from Redis
        status = redis_client.get(f"summarize_status:{document_id}")
        
        # If status is completed, get the result from DynamoDB
        if status == 'completed':
            response = table.get_item(
                Key={'document_id': document_id}
            )
            
            if 'Item' in response:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'document_id': document_id,
                        'summary': response['Item'].get('summary', ''),
                        'status': 'completed'
                    })
                }
        elif status == 'error':
            response = table.get_item(
                Key={'document_id': document_id}
            )
            if 'Item' in response:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'document_id': document_id,
                        'error': response['Item'].get('error_message', 'An error occurred'),
                        'status': 'error'
                    })
                }
        elif status == 'processing':
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'document_id': document_id,
                    'status': 'processing',
                    'message': 'Document is still being processed'
                })
            }
        
        # Document not found or status unknown
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Result not found or not ready'})
        }
    
    except Exception as e:
        print(f"Error retrieving result: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }