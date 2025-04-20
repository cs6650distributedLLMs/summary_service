#!/usr/bin/env python3
import requests
import json
import time
import uuid
import argparse
import sys

def summarize_text(api_url, document_id, text):
    """
    Submit a text for summarization
    """
    endpoint = f"{api_url}/summarize"
    
    payload = {
        "document_id": document_id,
        "text": text
    }
    
    response = requests.post(endpoint, json=payload)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    return response.json()

def check_status(api_url, document_id):
    """
    Check the status of a summarization job
    """
    endpoint = f"{api_url}/check-status/{document_id}"
    
    response = requests.get(endpoint)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    return response.json()

def get_result(api_url, document_id):
    """
    Get the summarization result
    """
    endpoint = f"{api_url}/result/{document_id}"
    
    response = requests.get(endpoint)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    return response.json()

def check_health(api_url):
    """
    Check if the service is healthy
    """
    endpoint = f"{api_url}/health"
    
    response = requests.get(endpoint)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False
    
    return True

def main():
    """
    Main function to demonstrate the usage of the summarization service
    """
    parser = argparse.ArgumentParser(description='Document Summarization Client')
    parser.add_argument('--api-url', default='http://localhost:5000', help='Base URL of the summarization API')
    parser.add_argument('--text-file', help='Path to a text file to summarize')
    parser.add_argument('--document-id', help='Document ID for checking status or getting results')
    parser.add_argument('--action', choices=['summarize', 'status', 'result', 'health'], 
                       required=True, help='Action to perform')
    parser.add_argument('--poll', action='store_true', 
                       help='Poll for results until completion (only with summarize action)')
    
    args = parser.parse_args()
    
    # Remove trailing slash from API URL if present
    api_url = args.api_url.rstrip('/')
    
    # Check health
    if args.action == 'health':
        if check_health(api_url):
            print("Service is healthy")
        else:
            print("Service is unhealthy")
        return
    
    # Check status
    if args.action == 'status':
        if not args.document_id:
            print("Error: document-id is required for status action")
            sys.exit(1)
        
        result = check_status(api_url, args.document_id)
        print(f"Status: {result['status']}")
        return
    
    # Get result
    if args.action == 'result':
        if not args.document_id:
            print("Error: document-id is required for result action")
            sys.exit(1)
        
        result = get_result(api_url, args.document_id)
        print(f"Status: {result['status']}")
        
        if result['status'] == 'completed':
            print("\nSummary:")
            print("=" * 80)
            print(result['summary'])
            print("=" * 80)
        elif result['status'] == 'error':
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        return
    
    # Summarize text
    if args.action == 'summarize':
        # Load text from file if provided
        if args.text_file:
            try:
                with open(args.text_file, 'r') as f:
                    text = f.read()
            except Exception as e:
                print(f"Error reading text file: {str(e)}")
                sys.exit(1)
        else:
            print("Enter or paste the text to summarize (press Ctrl+D when finished):")
            text = sys.stdin.read()
        
        # Generate document ID if not provided
        document_id = args.document_id or str(uuid.uuid4())
        
        print(f"Using document ID: {document_id}")
        
        # Submit text for summarization
        result = summarize_text(api_url, document_id, text)
        print(f"Summarization started: {result}")
        
        # Poll for results if requested
        if args.poll:
            print("Polling for results...")
            while True:
                status_result = check_status(api_url, document_id)
                status = status_result['status']
                
                print(f"Current status: {status}")
                
                if status == 'completed':
                    result = get_result(api_url, document_id)
                    print("\nSummary:")
                    print("=" * 80)
                    print(result['summary'])
                    print("=" * 80)
                    break
                elif status == 'error':
                    result = get_result(api_url, document_id)
                    print(f"Error: {result.get('error', 'Unknown error')}")
                    break
                
                time.sleep(5)  # Poll every 5 seconds
        else:
            print(f"You can check the status later with: python client.py --document-id {document_id} --action status")
            print(f"You can get the result later with: python client.py --document-id {document_id} --action result")
    
if __name__ == "__main__":
    main()