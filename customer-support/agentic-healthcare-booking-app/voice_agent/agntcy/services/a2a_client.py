# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time,os
import requests
import uuid
from http import HTTPStatus
from ioa_observe.sdk import Observe
from ioa_observe.sdk.decorators import tool
from ioa_observe.sdk.tracing import session_start
from ioa_observe.sdk.instrumentations.a2a import A2AInstrumentor
from dotenv import load_dotenv
load_dotenv()

class A2AClient:
    def __init__(self):
        self.base_url = os.getenv('A2A_SERVICE_URL', 'http://localhost:8887')
        self.message_url = os.getenv('A2A_MESSAGE_URL', self.base_url)
        self.api_key = os.getenv('A2A_API_KEY')
        self.agent_id = f"client_{uuid.uuid4().hex[:8]}"
        self.agent_card = None
        api_endpoint = os.getenv('OTLP_ENDPOINT', 'http://localhost:4318')
        Observe.init("A2A_Client", api_endpoint=api_endpoint)
        A2AInstrumentor().instrument()
        
        print(f"A2A-CLIENT: Initialized as {self.agent_id}")
        print(f"A2A-CLIENT: Discovery URL: {self.base_url}")
        print(f"A2A-CLIENT: Message URL: {self.message_url}")
        print(f"A2A-CLIENT: API Key: {'Set' if self.api_key else 'Not set'}")
    
    def _timed_request(self, method, url, description, **kwargs):
        start_time = time.time()
        timestamp = time.strftime("%H:%M:%S", time.localtime(start_time))
        print(f"A2A-CLIENT: [{timestamp}] >>> {method} {description}")
        print(f"A2A-CLIENT: URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, **kwargs)
            else:
                response = requests.post(url, **kwargs)
            
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            print(f"A2A-CLIENT: [{end_timestamp}] <<< {response.status_code} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            
            if response.status_code != HTTPStatus.OK:
                print(f"A2A-CLIENT: Error response: {response.text[:200]}")
            else:
                print(f"A2A-CLIENT: Success - response length: {len(response.text)} chars")
            
            return response, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            print(f"A2A-CLIENT: [{end_timestamp}] <<< ERROR: {e} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            return None, elapsed
    
    async def discover_agent(self):
        try:
            def _request():
                return self._timed_request('GET', f"{self.base_url}/.well-known/agent-card.json", 
                                         "Agent Discovery", timeout=30)
            
            loop = asyncio.get_event_loop()
            response, elapsed = await loop.run_in_executor(None, _request)
            
            if response and response.status_code == HTTPStatus.OK:
                self.agent_card = response.json()
                print(f"A2A-CLIENT: Discovered agent: {self.agent_card['name']}")
                return True
            else:
                if response:
                    print(f"A2A-CLIENT: Discovery failed: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"A2A-CLIENT: Discovery error: {e}")
            return False
    
    @tool(name="a2a_message_tool")
    async def send_message(self, message_parts, task_id=None, context_id=None):
        message = {
            "role": "user",
            "parts": message_parts,
            "messageId": str(uuid.uuid4()),
            "kind": "message"
        }
        
        if task_id:
            message["taskId"] = task_id
        if context_id:
            message["contextId"] = context_id
        session_start()
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": message,
                "configuration": {
                    "acceptedOutputModes": ["text/plain", "application/json"],
                    "blocking": True
                }
            }
        }
        
        # Log the message being sent
        message_text = ""
        for part in message_parts:
            if part.get('kind') == 'text':
                message_text = part.get('text', '')
                break
        print(f"A2A-CLIENT: Sending message: '{message_text[:100]}...'")
        
        try:
            def _request():
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers['X-Shared-Key'] = self.api_key
                
                description = f"Send Message"
                if task_id:
                    description += f" (Task: {task_id})"
                
                return self._timed_request('POST', self.message_url, description,
                                         json=payload, headers=headers, timeout=60)
            
            loop = asyncio.get_event_loop()
            response, elapsed = await loop.run_in_executor(None, _request)
            
            if response and response.status_code == HTTPStatus.OK:
                data = response.json()
                if 'result' in data:
                    result = data['result']
                    state = result['status']['state']
                    task_id = result.get('id', task_id)
                    
                    print(f"A2A-CLIENT: Task {task_id} state: {state}")
                    
                    # Log agent response if present
                    if result['status'].get('message'):
                        agent_response = ""
                        for part in result['status']['message'].get('parts', []):
                            if part.get('kind') == 'text':
                                agent_response = part.get('text', '')
                                break
                        if agent_response:
                            print(f"A2A-CLIENT: Agent response: '{agent_response[:100]}...'")
                    
                    # Log artifacts if present (final results)
                    if result.get('artifacts'):
                        print(f"A2A-CLIENT: Task completed with {len(result['artifacts'])} artifact(s)")
                    
                    return result
                elif 'error' in data:
                    print(f"A2A-CLIENT: Server error: {data['error']}")
                    return None
            else:
                if response:
                    print(f"A2A-CLIENT: HTTP error {response.status_code}: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"A2A-CLIENT: Request failed: {e}")
            return None