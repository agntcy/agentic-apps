#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import requests
import json
import uuid
import time
from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()

class InteractiveA2AClient:
    def __init__(self):
        self.base_url = os.getenv('A2A_SERVICE_URL', 'http://localhost:8887')
        self.message_url = os.getenv('A2A_MESSAGE_URL', self.base_url)
        self.api_key = os.getenv('A2A_API_KEY')
        self.task_id = None
        self.context_id = None
        print(f"Discovery URL: {self.base_url}")
        print(f"Message URL: {self.message_url}")
        print(f"API Key: {'Set' if self.api_key else 'Not set'}")
    
    def timed_request(self, method, url, **kwargs):
        start_time = time.time()
        timestamp = time.strftime("%H:%M:%S", time.localtime(start_time))
        print(f"\n[{timestamp}] >>> {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, **kwargs)
            else:
                response = requests.post(url, **kwargs)
            
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            print(f"[{end_timestamp}] <<< {response.status_code} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            return response, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            print(f"[{end_timestamp}] <<< ERROR: {e} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            return None, elapsed
    
    def discover_agent(self):
        print("DISCOVERING AGENT")
        
        response, elapsed = self.timed_request('GET', f"{self.base_url}/.well-known/agent-card.json", timeout=10)
        
        if response and response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"Agent Name: {data.get('name', 'Unknown')}")
            print(f"Description: {data.get('description', 'No description')}")
            return True
        else:
            if response:
                print(f"Error: {response.text}")
            return False
    
    def send_message(self, text):

        print(f"SENDING MESSAGE: {text}")
        
        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
            "messageId": str(uuid.uuid4()),
            "kind": "message"
        }
        
        if self.task_id:
            message["taskId"] = self.task_id
        if self.context_id:
            message["contextId"] = self.context_id
        
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {"message": message}
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers['X-Shared-Key'] = self.api_key
        
        print(f"Request payload: {json.dumps(payload, indent=2)}")
        
        response, elapsed = self.timed_request('POST', self.message_url, 
                                             json=payload, headers=headers, timeout=30)
        
        if response and response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if 'result' in data:
                result = data['result']
                
                # Store task info for subsequent messages
                if not self.task_id:
                    self.task_id = result.get('id')
                    self.context_id = result.get('contextId')
                
                state = result['status']['state']
                print(f"\nTask ID: {self.task_id}")
                print(f"State: {state}")
                
                # Extract agent's response
                if result['status'].get('message'):
                    agent_response = ""
                    for part in result['status']['message'].get('parts', []):
                        if part.get('kind') == 'text':
                            agent_response = part.get('text', '')
                            break
                    
                    print(f"\nAgent Response:")
                    print("-" * 30)
                    print(agent_response)
                    print("-" * 30)
                
                # Check for artifacts (final results)
                if result.get('artifacts'):
                    print(f"\nArtifacts (Results):")
                    for artifact in result['artifacts']:
                        print(json.dumps(artifact, indent=2))
                
                return state
            else:
                print(f"Error in response: {data}")
                return None
        else:
            if response:
                print(f"HTTP Error: {response.text}")
            return None

def run_interactive_chat():
    client = InteractiveA2AClient()
    
    # Discover agent first
    if not client.discover_agent():
        print("Failed to discover agent. Exiting.")
        return
    
    print(" TRIAGE CHAT")
    
    current_state = None
    
    while True:
        print(f"\nCurrent state: {current_state or 'Not started'}")
        user_input = input("\nYour message: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        current_state = client.send_message(user_input)
        
        if current_state == 'present_result':
            print("TRIAGE COMPLETED!")
            print("The assessment is complete. Type another message to continue or 'quit' to exit.")
        elif current_state in ['failed', 'canceled']:
            print(f"TRIAGE {current_state.upper()}")
            break
        elif current_state is None:
            print("Error occurred. Try again or type 'quit' to exit.")

if __name__ == "__main__":
    run_interactive_chat()