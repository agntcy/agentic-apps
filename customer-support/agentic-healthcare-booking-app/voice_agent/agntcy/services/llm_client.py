# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json,os
import requests
from http import HTTPStatus
from ioa_observe.sdk.decorators import tool
from agntcy.models.session import Session

class LLMClient:
    def __init__(self, jwt_token, endpoint_url, project_id, connection_id):
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {jwt_token}'
        }
        self.endpoint_url = endpoint_url
        self.project_id = project_id
        self.connection_id = connection_id
        print("LLM: Initialized with JWT endpoint")
    
    @tool(name="llm_tool")
    async def process(self, user_input, session):
        print(f"LLM: Processing: '{user_input[:50]}...'")
        
        if session.in_triage_mode:
            prompt = f"""You are in TRIAGE MODE. The user is answering medical assessment questions.

Current triage task: {session.triage_task_id}
User response to triage question: "{user_input}"

Respond with:
{{
    "response": "I understand your answer. Let me continue the medical assessment.",
    "extract": {{}},
    "need_triage": false,
    "call_discovery": false,
    "call_eligibility": false,
    "done": false,
    "continue_triage": true
}}"""
        else:
            prompt = f"""You are a healthcare appointment scheduler with this specific flow:

1. Ask name, phone
2. Ask reason for visit
3. If medical symptoms → start triage (use default demographics)
4. After triage → collect DOB (for insurance), state → call discovery → announce insurance found
5. Collect provider → call eligibility → announce payer, policy ID, copay
6. Schedule appointment → confirmation code → end

Current session data: {json.dumps(session.data)}
Triage complete: {session.triage_complete}
Triage results: {json.dumps(session.triage_results)}
User input: "{user_input}"

EXTRACTION RULES:
- Extract name as "name"
- Extract phone as "phone" 
- Extract medical reason as "reason"
- Extract date of birth as "date_of_birth" (MM/DD/YYYY format)
- Extract US state as "state"
- Extract provider name as "provider_name"
- Extract appointment date as "preferred_date"

JSON response:
{{
    "response": "what to say to user",
    "extract": {{"field": "value"}},
    "need_triage": true/false,
    "call_discovery": true/false,
    "call_eligibility": true/false,
    "done": true/false
}}"""
        
        payload = {
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ],
            "project_id": self.project_id,
            "connection_id": self.connection_id,
            "max_tokens": 400,
            "temperature": 0.2
        }
        
        def _request():
            return requests.post(self.endpoint_url, headers=self.headers, json=payload, timeout=30)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            if 'choices' in data and data['choices']:
                content = data['choices'][0]['message']['content']
                
                try:
                    if content.startswith('```json'):
                        content = content[7:]
                    if content.endswith('```'):
                        content = content[:-3]
                    
                    result = json.loads(content.strip())
                    print("LLM: Response parsed")
                    return result
                except:
                    pass
        
        return {
            "response": "I understand. Please continue.",
            "extract": {},
            "need_triage": False,
            "call_discovery": False,
            "call_eligibility": False,
            "done": False
        }