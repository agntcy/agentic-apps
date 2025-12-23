# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import requests
import json
import base64
import time
from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()

class DirectTriageClient:
    def __init__(self):
        self.app_id = os.getenv('TRIAGE_APP_ID')
        self.app_key = os.getenv('TRIAGE_APP_KEY')
        self.instance_id = os.getenv('TRIAGE_INSTANCE_ID')
        self.token_url = os.getenv('TRIAGE_TOKEN_URL')
        self.base_url = os.getenv('TRIAGE_BASE_URL')
        
        self.token = None
        self.survey_id = None
        
        print(f"Base URL: {self.base_url}")
        print(f"Token URL: {self.token_url}")
    
    def _timed_request(self, method, url, description, **kwargs):
        start_time = time.time()
        timestamp = time.strftime("%H:%M:%S", time.localtime(start_time))
        print(f"\n[{timestamp}] >>> {method} {description}")
        print(f"URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, **kwargs)
            elif method == 'POST':
                response = requests.post(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            
            print(f"[{end_timestamp}] <<< {response.status_code} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            
            if response.status_code == HTTPStatus.OK:
                try:
                    data = response.json()
                    print(f"Response: {json.dumps(data, indent=2)}")
                except:
                    print(f"Response: {response.text}")
            else:
                print(f"Error: {response.text}")
            
            return response, elapsed
            
        except Exception as e:
            elapsed = time.time() - start_time
            end_timestamp = time.strftime("%H:%M:%S", time.localtime())
            elapsed_ms = elapsed * 1000
            print(f"[{end_timestamp}] <<< ERROR: {e} | {elapsed:.3f}s ({elapsed_ms:.0f}ms)")
            return None, elapsed
    
    def get_token(self):
        print("GETTING ACCESS TOKEN")
        
        creds = base64.b64encode(f"{self.app_id}:{self.app_key}".encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
            "instance-id": self.instance_id
        }
        payload = {"grant_type": "client_credentials"}
        
        response, elapsed = self._timed_request(
            'POST', self.token_url, "Get OAuth Token",
            headers=headers, json=payload, timeout=30
        )
        
        if response and response.status_code == HTTPStatus.OK:
            self.token = response.json()['access_token']
            print(f"Token obtained: {self.token[:20]}...")
            return True
        
        print("Failed to get token")
        return False
    
    def create_survey(self, age, sex):
        print(f"CREATING SURVEY - Age: {age}, Sex: {sex}")
        
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"sex": sex.lower(), "age": {"value": age, "unit": "year"}}
        
        response, elapsed = self._timed_request(
            'POST', f"{self.base_url}/surveys", "Create Survey",
            headers=headers, json=payload, timeout=30
        )
        
        if response and response.status_code == HTTPStatus.OK:
            self.survey_id = response.json()['survey_id']
            print(f"Survey created: {self.survey_id}")
            return True
        
        print("Failed to create survey")
        return False
    
    def send_message(self, message):
        print(f"SENDING MESSAGE: {message}")
        
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"user_message": message}
        
        response, elapsed = self._timed_request(
            'POST', f"{self.base_url}/surveys/{self.survey_id}/messages", "Send Message",
            headers=headers, json=payload, timeout=30
        )
        
        if response and response.status_code == HTTPStatus.OK:
            data = response.json()
            state = data.get('survey_state', 'unknown')
            agent_response = data.get('assistant_message', '')
            
            print(f"\nSurvey State: {state}")
            print(f"Agent Response:")
            print(agent_response)
            
            return state, agent_response
        
        print("Failed to send message")
        return None, None
    
    def get_summary(self):
        print("GETTING FINAL SUMMARY")
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response, elapsed = self._timed_request(
            'GET', f"{self.base_url}/surveys/{self.survey_id}/summary", "Get Summary",
            headers=headers, timeout=30
        )
        
        if response and response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"Summary obtained:")
            print(f"Urgency: {data.get('urgency', 'Unknown')}")
            print(f"Doctor Type: {data.get('doctor_type', 'Unknown')}")
            print(f"Notes: {data.get('notes', 'None')}")
            return data
        
        print("Failed to get summary")
        return None

def run_interactive_triage():
    client = DirectTriageClient()
    
    # Step 1: Get token
    if not client.get_token():
        return
    
    # Step 2: Get demographics
    print("SETUP - Enter Demographics")
    
    try:
        age = int(input("Enter age: "))
        sex = input("Enter sex (male/female): ").lower()
        
        if sex not in ['male', 'female']:
            print("Invalid sex, defaulting to male")
            sex = 'male'
            
    except ValueError:
        print("Invalid age, defaulting to 30")
        age = 30
        sex = 'male'
    
    # Step 3: Create survey
    if not client.create_survey(age, sex):
        return
    
    # Step 4: Interactive conversation
    print("INTERACTIVE TRIAGE CONVERSATION")
    
    current_state = None
    
    while True:
        user_input = input("\nYour message: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Ending conversation...")
            break
        
        if not user_input:
            continue
        
        state, agent_response = client.send_message(user_input)
        
        if state is None:
            print("Error sending message. Try again or type 'quit'.")
            continue
        
        current_state = state
        
        if state == 'present_result':
            print("TRIAGE ASSESSMENT COMPLETED!")
            
            # Get final summary
            summary = client.get_summary()
            
            print("\nConversation complete. Type 'quit' to exit or continue chatting.")
        elif state in ['failed', 'error']:
            print(f"\nTriage ended with state: {state}")
            break

if __name__ == "__main__":
    print("Direct External API Triage Client")
    
    run_interactive_triage()