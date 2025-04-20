from flask import Flask, request, jsonify
import os
import uuid
import json
import time
import requests
import redis
import threading
from datetime import datetime

app = Flask(__name__)

# Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
GROKX_API_KEY = os.environ.get('GROKX_API_KEY', '')
GROKX_API_URL = os.environ.get('GROKX_API_URL', 'https://api.x.ai/v1/chat/completions')

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
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

# In-memory document storage (replace with a database in production)
documents = {}

# Process queue
processing_threads = {}

def call_grokx_api(text):
    """
    Call the GrokX API to summarize text
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
        'model': 'grok-2-latest',  # Specify the model you want to use
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

def process_document(document_id):
    """
    Background thread to process document summarization
    """
    try:
        # Get the document
        if document_id not in documents:
            update_status(document_id, 'error', error_message='Document not found')
            return
        
        document = documents[document_id]
        text = document.get('original_text', '')
        
        if not text:
            update_status(document_id, 'error', error_message='No text found to summarize')
            return
        
        # Update status to processing
        update_status(document_id, 'processing')
        
        # Call GrokX API to summarize the text
        summary = call_grokx_api(text)
        
        # Update document with result
        documents[document_id]['summary'] = summary
        documents[document_id]['updated_at'] = datetime.utcnow().isoformat()
        
        # Update status to completed
        update_status(document_id, 'completed')
        
    except Exception as e:
        print(f"Error processing document {document_id}: {str(e)}")
        update_status(document_id, 'error', error_message=str(e))
    
    finally:
        # Remove from processing threads
        if document_id in processing_threads:
            del processing_threads[document_id]

def update_status(document_id, status, error_message=None):
    """
    Update the status in both storage systems
    """
    try:
        # Update Redis
        redis_client.set(f"summarize_status:{document_id}", status)
        
        # Update in-memory document
        if document_id in documents:
            documents[document_id]['status'] = status
            documents[document_id]['updated_at'] = datetime.utcnow().isoformat()
            
            if error_message and status == 'error':
                documents[document_id]['error_message'] = error_message
    
    except Exception as e:
        print(f"Error updating status for {document_id}: {str(e)}")

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
        if status == 'processing':
            return jsonify({
                'status': 'already_processing',
                'message': f'Document with ID {document_id} is already being processed'
            }), 200
        
        # Initialize status
        redis_client.set(f"summarize_status:{document_id}", "processing")
        
        # Store document
        timestamp = datetime.utcnow().isoformat()
        documents[document_id] = {
            'document_id': document_id,
            'original_text': text,
            'status': 'processing',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # Start background processing thread
        thread = threading.Thread(target=process_document, args=(document_id,))
        thread.daemon = True  # Daemonize thread to not block shutdown
        thread.start()
        
        # Store thread reference
        processing_threads[document_id] = thread
        
        return jsonify({
            'status': 'ok',
            'message': 'Summarization started'
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
            # Check in-memory storage if not in Redis
            if document_id in documents:
                status = documents[document_id].get('status', 'unknown')
                # Update Redis cache
                redis_client.set(f"summarize_status:{document_id}", status)
            else:
                return jsonify({'error': 'Document not found'}), 404
        
        return jsonify({'status': status}), 200
    
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/result/<document_id>', methods=['GET'])
def get_result(document_id):
    try:
        # Get status from Redis
        status = redis_client.get(f"summarize_status:{document_id}")
        
        # If status is completed, get the result
        if status == 'completed':
            if document_id in documents:
                return jsonify({
                    'document_id': document_id,
                    'summary': documents[document_id].get('summary', ''),
                    'status': 'completed'
                }), 200
        elif status == 'error':
            if document_id in documents:
                return jsonify({
                    'document_id': document_id,
                    'error': documents[document_id].get('error_message', 'An error occurred'),
                    'status': 'error'
                }), 200
        elif status == 'processing':
            return jsonify({
                'document_id': document_id,
                'status': 'processing',
                'message': 'Document is still being processed'
            }), 200
        
        # Document not found or status unknown
        return jsonify({'error': 'Result not found or not ready'}), 404
    
    except Exception as e:
        print(f"Error retrieving result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Print API information
    print(f"Starting Summarization Service on port {port}")
    print("API Endpoints:")
    print("  POST /summarize - Submit text for summarization")
    print("  GET /check-status/<document_id> - Check processing status")
    print("  GET /result/<document_id> - Get the summarization result")
    print("  GET /health - Service health check")
    
    # Start Flask application
    app.run(host='0.0.0.0', port=port)