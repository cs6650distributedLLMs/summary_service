from flask import Flask, request, jsonify
import os
import uuid
import json
import time
import boto3
import redis
from datetime import datetime

app = Flask(__name__)

# Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')

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
    print("Redis connection successful")
except Exception as e:
    print(f"Warning: Redis connection failed: {str(e)}")
    print("Using in-memory storage instead")
    # Mock redis with an in-memory dictionary for environments without Redis
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        def set(self, key, value):
            self.data[key] = value
            return True
        
        def get(self, key):
            return self.data.get(key)
        
        def exists(self, key):
            return key in self.data
    
    redis_client = MockRedis()

# Initialize AWS SQS client
try:
    sqs_client = boto3.client('sqs', region_name=AWS_REGION)
    print(f"SQS client initialized for region {AWS_REGION}")
except Exception as e:
    print(f"Warning: SQS client initialization failed: {str(e)}")
    print("Using mock SQS client")
    
    # Mock SQS client for environments without AWS access
    class MockSQS:
        def __init__(self):
            self.messages = []
        
        def send_message(self, QueueUrl, MessageBody):
            self.messages.append(MessageBody)
            print(f"Message added to mock queue: {MessageBody[:100]}...")
            # Process the message locally
            try:
                body = json.loads(MessageBody)
                document_id = body.get('document_id')
                # Set status to queued
                redis_client.set(f"summarize_status:{document_id}", "queued")
                
                # For local processing, set a fake delay and status
                import threading
                def simulate_processing():
                    time.sleep(5)  # Simulate queue delay
                    redis_client.set(f"summarize_status:{document_id}", "processing")
                    time.sleep(10)  # Simulate processing time
                    
                    # Simulate completion without actually calling the API
                    redis_client.set(f"summarize_status:{document_id}", "completed")
                    redis_client.set(f"summarize_result:{document_id}", 
                                    "This is a simulated summary. In production, this would be the actual text summary from the X.AI API.")
                
                thread = threading.Thread(target=simulate_processing)
                thread.daemon = True
                thread.start()
            except Exception as ex:
                print(f"Error in mock processing: {str(ex)}")
            
            return {'MessageId': str(uuid.uuid4())}
    
    sqs_client = MockSQS()

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        # Parse request body
        body = request.json
        
        # Validate input
        if 'document_id' not in body or 'text' not in body:
            return jsonify({
                'error': 'Missing required parameters (document_id or text)'
            }), 400
        
        document_id = body['document_id']
        text = body['text']
        
        # Check if document already exists and is being processed
        status = redis_client.get(f"summarize_status:{document_id}")
        if status and status in ['processing', 'queued']:
            return jsonify({
                'status': status,
                'message': f'Document with ID {document_id} is already {status}'
            }), 200
        
        # Initialize status
        redis_client.set(f"summarize_status:{document_id}", "queued")
        
        # Store original text in Redis
        redis_client.set(f"summarize_text:{document_id}", text)
        
        # Add to Redis processing queue
        redis_client.rpush("summarize_queue", document_id)
        
        return jsonify({
            'status': 'queued',
            'message': 'Summarization queued',
            'document_id': document_id
        }), 200
    
    except Exception as e:
        print(f"Error in summarize request: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/check-status/<document_id>', methods=['GET'])
def check_status(document_id):
    try:
        # Get status from Redis for fast lookup
        status = redis_client.get(f"summarize_status:{document_id}")
        
        if not status:
            return jsonify({'error': 'Document not found'}), 404
        
        response = {
            'status': status,
            'document_id': document_id
        }
        
        # Add queue position if queued
        if status == 'queued':
            response['message'] = 'Document is in queue for processing'
        elif status == 'processing':
            response['message'] = 'Document is being processed'
        elif status == 'completed':
            response['message'] = 'Document processing is complete'
        elif status == 'error':
            error_message = redis_client.get(f"summarize_error:{document_id}")
            response['error'] = error_message if error_message else 'An unknown error occurred'
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/result/<document_id>', methods=['GET'])
def get_result(document_id):
    try:
        # Get status from Redis
        status = redis_client.get(f"summarize_status:{document_id}")
        
        if not status:
            return jsonify({'error': 'Document not found'}), 404
        
        # If status is completed, get the result
        if status == 'completed':
            summary = redis_client.get(f"summarize_result:{document_id}")
            
            if not summary:
                return jsonify({
                    'error': 'Summary not found even though status is completed',
                    'status': 'error'
                }), 500
            
            return jsonify({
                'document_id': document_id,
                'summary': summary,
                'status': 'completed'
            }), 200
        elif status == 'error':
            error_message = redis_client.get(f"summarize_error:{document_id}")
            return jsonify({
                'document_id': document_id,
                'error': error_message if error_message else 'An unknown error occurred',
                'status': 'error'
            }), 200
        else:
            return jsonify({
                'document_id': document_id,
                'status': status,
                'message': f'Document is still in {status} state'
            }), 200
    
    except Exception as e:
        print(f"Error retrieving result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    try:
        # Check Redis connection
        redis_status = 'up' if redis_client.ping() else 'down'
    except:
        redis_status = 'down'
    
    # Check SQS connection (simplified)
    sqs_status = 'up' if SQS_QUEUE_URL else 'mock' if isinstance(sqs_client, MockSQS) else 'unconfigured'
    
    return jsonify({
        'status': 'healthy',
        'redis': redis_status,
        'sqs': sqs_status,
        'timestamp': datetime.utcnow().isoformat()
    }), 200

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Print API information
    print(f"Starting Summarization API Service on port {port}")
    print("API Endpoints:")
    print("  POST /summarize - Submit text for summarization")
    print("  GET /check-status/<document_id> - Check processing status")
    print("  GET /result/<document_id> - Get the summarization result")
    print("  GET /health - Service health check")
    
    # Start Flask application
    app.run(host='0.0.0.0', port=port)