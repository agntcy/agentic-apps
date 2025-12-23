# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Triage API Connection Test Script
Tests the full triage API flow: token -> survey -> messages -> summary
"""
import os
import base64
import json
import requests
import time
import sys
from datetime import datetime
from http import HTTPStatus
from dotenv import load_dotenv
load_dotenv()
app_id = os.getenv('TRIAGE_APP_ID')
app_key = os.getenv('TRIAGE_APP_KEY')
instance_id = os.getenv('TRIAGE_INSTANCE_ID')
token_url = os.getenv('TRIAGE_TOKEN_URL')
base_url = os.getenv('TRIAGE_BASE_URL')


def test_triage_api():
    """Test complete triage API flow"""
    print("=" * 60)
    print("TRIAGE API CONNECTION TEST")
    print("=" * 60)
    
    # Check configuration
    print("1. Checking configuration...")
    missing = []
    if not app_id: missing.append('TRIAGE_APP_ID')
    if not app_key: missing.append('TRIAGE_APP_KEY')
    if not instance_id: missing.append('TRIAGE_INSTANCE_ID')
    if not token_url: missing.append('TRIAGE_TOKEN_URL')
    if not base_url: missing.append('TRIAGE_BASE_URL')
    
    if missing:
        print(f"   ❌ Missing environment variables: {missing}")
        return False
    
    print(f"   ✅ App ID: {app_id[:10]}...")
    print(f"   ✅ Instance ID: {instance_id}")
    print(f"   ✅ Token URL: {token_url}")
    print(f"   ✅ Base URL: {base_url}")
    
    # Test 1: Get Token
    print("\n2. Testing token acquisition...")
    try:
        creds = base64.b64encode(f"{app_id}:{app_key}".encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
            "instance-id": instance_id
        }
        payload = {"grant_type": "client_credentials"}
        
        print(f"   → POST {token_url}")
        response = requests.post(token_url, headers=headers, json=payload, timeout=30)
        print(f"   ← Status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            token_data = response.json()
            token = token_data['access_token']
            print(f"   ✅ Token acquired: {token[:20]}...")
            
            # Check token expiry if available
            if 'expires_in' in token_data:
                print(f"   ℹ️  Token expires in: {token_data['expires_in']} seconds")
        else:
            print(f"   ❌ Token failed: {response.status_code}")
            print(f"   ❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Token request failed: {e}")
        return False
    
    # Test 2: Create Survey
    print("\n3. Testing survey creation...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "sex": "female",
            "age": {"value": 64, "unit": "year"}
        }
        
        print(f"   → POST {base_url}/surveys")
        print(f"   → Demographics: 64yo female")
        response = requests.post(f"{base_url}/surveys", headers=headers, json=payload, timeout=30)
        print(f"   ← Status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            survey_data = response.json()
            survey_id = survey_data['survey_id']
            print(f"   ✅ Survey created: {survey_id}")
        else:
            print(f"   ❌ Survey failed: {response.status_code}")
            print(f"   ❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Survey request failed: {e}")
        return False
    
    # Test 3: Send Initial Message
    print("\n4. Testing initial message...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"user_message": "I am 33 male, for the past few weeks I’ve been feeling very tired. I’m often extremely thirsty, I need to urinate much more than usual, and I’ve also lost some weight without trying."}
        
        print(f"   → POST {base_url}/surveys/{survey_id}/messages")
        print(f"   → Message: 'I am 33 male, for the past few weeks I’ve been feeling very tired. I’m often extremely thirsty, I need to urinate much more than usual, and I’ve also lost some weight without trying.'")
        response = requests.post(f"{base_url}/surveys/{survey_id}/messages", 
                               headers=headers, json=payload, timeout=30)
        print(f"   ← Status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            message_data = response.json()
            assistant_message = message_data.get('assistant_message', '')
            survey_state = message_data.get('survey_state', 'unknown')
            
            print(f"   ✅ Message sent successfully")
            print(f"   ✅ Survey state: {survey_state}")
            print(f"   ✅ Assistant response: '{assistant_message[:100]}...'")
            
        else:
            print(f"   ❌ Message failed: {response.status_code}")
            print(f"   ❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Message request failed: {e}")
        return False
    
    # Test 4: Continue Conversation (simulate a few turns)
    print("\n5. Testing conversation flow...")
    conversation_turns = [
        "These symptoms started a few weeks ago and they have been gradually getting worse.",
        "Loss of consciousness - no"
        "Cold and clammy skin - no"
        "Rapid breathing - no"
        "Bone pain - no"    
        "Shortness of breath - no"
        "Pale skin - no"
        "Yes"
        "No"
    ]
    
    for i, user_message in enumerate(conversation_turns, 1):
        try:
            print(f"   Turn {i}: '{user_message}'")
            payload = {"user_message": user_message}
            
            response = requests.post(f"{base_url}/surveys/{survey_id}/messages", 
                                   headers=headers, json=payload, timeout=30)
            
            if response.status_code == HTTPStatus.OK:
                message_data = response.json()
                assistant_message = message_data.get('assistant_message', '')
                survey_state = message_data.get('survey_state', 'unknown')
                
                print(f"   ← State: {survey_state}")
                print(f"   ← Response: '{assistant_message[:80]}...'")
                
                # Break if we reach certain states
                if survey_state in ['post_result', 'completed']:
                    print(f"   ℹ️  Survey reached terminal state: {survey_state}")
                    break
                    
            else:
                print(f"   ⚠️  Turn {i} failed: {response.status_code}")
                break
                
            # Small delay between messages
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Turn {i} failed: {e}")
            break
    
    # Test 5: Get Summary
    print("\n6. Testing summary retrieval...")
    try:
        print(f"   → GET {base_url}/surveys/{survey_id}/summary")
        response = requests.get(f"{base_url}/surveys/{survey_id}/summary", 
                              headers=headers, timeout=30)
        print(f"   ← Status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            summary_data = response.json()
            print(f"   ✅ Summary retrieved successfully")
            print(f"   ℹ️  Summary data:")
            
            # Pretty print the summary
            for key, value in summary_data.items():
                print(f"      {key}: {value}")
                
        else:
            print(f"   ⚠️  Summary failed: {response.status_code}")
            print(f"   ⚠️  Error: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Summary request failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ API CONNECTION TEST COMPLETED")
    print("=" * 60)
    return True

def test_token_only():
    """Quick token-only test"""
    print("QUICK TOKEN TEST")
    print("-" * 30)
    
    if not all([app_id, app_key, instance_id, token_url]):
        print("❌ Missing environment variables")
        return
    
    try:
        creds = base64.b64encode(f"{app_id}:{app_key}".encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
            "instance-id": instance_id
        }
        payload = {"grant_type": "client_credentials"}
        
        response = requests.post(token_url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == HTTPStatus.OK:
            token_data = response.json()
            token = token_data['access_token']
            print(f"✅ Token: {token[:30]}...")
            if 'expires_in' in token_data:
                print(f"⏰ Expires: {token_data['expires_in']}s")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"❌ Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "token":
        test_token_only()
    else:
        test_triage_api()