import json
import os
import boto3
import redis
import requests
import time
from datetime import datetime

# Initialize AWS services
dynamodb = boto3.resource('dynamodb')
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
GROKX_API_KEY = os.environ['GROKX_API_KEY']
GROKX_API_URL = os.environ['GROKX_API_URL']

def lambda_handler(event, context):
    """
    Processor Lambda handler for asynchronous text summarization
    """
    try:
        document_id = event['document_id']
        
        # Get the document from DynamoDB
        response = table.get_item(
            Key={'document_id': document_id}
        )
        
        if 'Item' not in response:
            update_status(document_id, 'error', error_message='Document not found')
            return
        
        item = response['Item']
        text = item.get('original_text', '')
        
        if not text:
            update_status(document_id, 'error', error_message='No text found to summarize')
            return
        
        # Call GrokX API to summarize the text
        summary = call_grokx_api(text)
        
        # Update DynamoDB with the result
        timestamp = datetime.utcnow().isoformat()
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression="SET summary = :summary, status = :status, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':summary': summary,
                ':status': 'completed',
                ':updated_at': timestamp
            }
        )
        
        # Update Redis status
        redis_client.set(f"summarize_status:{document_id}", "completed")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'status': 'completed'})
        }
    
    except Exception as e:
        print(f"Error in processor: {str(e)}")
        
        if 'document_id' in event:
            update_status(event['document_id'], 'error', error_message=str(e))
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def call_grokx_api(text):
    """
    Call the GrokX API to summarize text
    
    This function makes the actual API call to the LLM service
    Implements retry logic for resilience
    """
    max_retries = 3
    retry_delay = 2  # seconds
    
    headers = {
        'Authorization': f'Bearer {GROKX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Prepare the prompt for the LLM
    prompt = f"""Please summarize the following text concisely while preserving the key information:

{text}

Summary:"""
    
    payload = {
        'model': 'grok-1',  # Specify the model you want to use
        'messages': [
            {'role': 'system', 'content': 'You are a helpful assistant that specializes in summarizing documents.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.3,  # Lower temperature for more focused summaries
        'max_tokens': 1000   # Adjust based on your summarization needs
    }
    
    # Implement retry logic
    for attempt in range(max_retries):
        try:
            response = requests.post(
                GROKX_API_URL,
                headers=headers,
                json=payload,
                timeout=30  # 30-second timeout
            )
            
            response.raise_for_status()  # Raise exception for 4xx/5xx responses
            response_data = response.json()
            
            # Extract the summary from the response
            # Adjust this based on the actual GrokX API response format
            if 'choices' in response_data and len(response_data['choices']) > 0:
                summary = response_data['choices'][0]['message']['content']
                return summary
            else:
                raise Exception("Unexpected API response format")
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"API request failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            else:
                raise Exception(f"Failed to call GrokX API after {max_retries} attempts: {str(e)}")
    
    raise Exception("Failed to get summary from GrokX API")

def update_status(document_id, status, error_message=None):
    """
    Update the status in both DynamoDB and Redis
    """
    try:
        # Update Redis first (fast)
        redis_client.set(f"summarize_status:{document_id}", status)
        
        # Update DynamoDB
        timestamp = datetime.utcnow().isoformat()
        update_expression = "SET status = :status, updated_at = :updated_at"
        expression_values = {
            ':status': status,
            ':updated_at': timestamp
        }
        
        if error_message and status == 'error':
            update_expression += ", error_message = :error_message"
            expression_values[':error_message'] = error_message
        
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
    
    except Exception as e:
        print(f"Error updating status: {str(e)}")
        # We don't want to raise here since this is already error handling