# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Healthcare Voice + A2A + MCP Agent (Hosted A2A Service)
"""
import asyncio
import json
import os
import re
import uuid
import random
import string
import tempfile
import time
from datetime import datetime
from http import HTTPStatus
from typing import Dict, Optional, List, Any
from enum import Enum

import requests

from a2a.types import TaskState

# if need default chat mode - set this flag to False.
AUDIO_AVAILABLE = True

# Audio imports with fallback
try:
    import speech_recognition as sr
    import pygame
    from gtts import gTTS
except ImportError:
    AUDIO_AVAILABLE = False

# Load environment
def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        pass

load_env()

# Session Management
class Session:
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.data = {}
        self.triage_complete = False
        self.triage_attempts = 0
        self.conversation_log = []
        self.start_time = datetime.now()
        self.triage_task_id = None
        self.triage_context_id = None
        self.triage_results = {}
        self.in_triage_mode = False
    
    def add_interaction(self, role, message, extra_data=None):
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
            "session_data_snapshot": self.data.copy()
        }
        if extra_data:
            interaction["extra_data"] = extra_data
        self.conversation_log.append(interaction)
        print(f"SESSION-LOG: {role.upper()} - {message[:100]}...")
    
    def save_to_file(self):
        try:
            os.makedirs("sessions", exist_ok=True)
            filename = f"sessions/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.id}.json"
            
            session_data = {
                "session_id": self.id,
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_minutes": (datetime.now() - self.start_time).total_seconds() / 60,
                "final_data": self.data,
                "triage_complete": self.triage_complete,
                "triage_attempts": self.triage_attempts,
                "conversation_log": self.conversation_log,
                "data_fields_collected": list(self.data.keys()),
                "total_interactions": len(self.conversation_log)
            }
            
            with open(filename, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)
            
            print(f"SESSION: Saved complete session to {filename}")
            return filename
        except Exception as e:
            print(f"SESSION: Save failed: {e}")
            return None

# Audio System
class AudioSystem:
    def __init__(self):
        self.enabled = AUDIO_AVAILABLE
        self.tts_enabled = False
        self.speech_enabled = False
        
        if self.enabled:
            try:
                print("Initializing audio...")
                
                try:
                    self.recognizer = sr.Recognizer()
                    self.microphone = sr.Microphone()
                    with self.microphone as source:
                        self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    
                    self.recognizer.energy_threshold = 300
                    self.recognizer.dynamic_energy_threshold = True
                    self.recognizer.pause_threshold = 0.8
                    self.speech_enabled = True
                    print("Speech recognition ready")
                except Exception as e:
                    print(f"Speech recognition failed: {e}")
                    self.speech_enabled = False
                
                try:
                    pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
                    pygame.mixer.init()
                    self.tts_enabled = True
                    print("TTS system ready")
                except Exception as e:
                    print(f"TTS init failed: {e}")
                    self.tts_enabled = False
                    
            except Exception as e:
                print(f"Audio init failed: {e}")
                self.enabled = False
    
    async def listen(self, timeout=5):
        if not self.speech_enabled:
            return input("You: ").strip()
        
        print("Listening...")
        
        def _listen():
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=6)
                result = self.recognizer.recognize_google(audio, language='en-US')
                print(f"Recognized: '{result}'")
                return result.strip()
            except sr.UnknownValueError:
                return "UNCLEAR"
            except sr.WaitTimeoutError:
                return "TIMEOUT"
            except Exception:
                return "ERROR"
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _listen)
    
    async def speak(self, text):
        print(f"Agent: {text}")
        
        if not self.tts_enabled:
            print("TTS: Not enabled, skipping audio")
            return
        
        def _speak():
            try:
                tts = gTTS(text=text, lang='en', slow=False)
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    temp_file = tmp.name
                
                try:
                    tts.save(temp_file)
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    max_wait = 30
                    wait_count = 0
                    while pygame.mixer.music.get_busy() and wait_count < max_wait * 20:
                        pygame.time.wait(50)
                        wait_count += 1
                    
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.stop()
                        
                finally:
                    try:
                        os.unlink(temp_file)
                    except Exception:
                        pass
                        
                return True
                        
            except Exception as e:
                print(f"TTS error: {e}")
                return False
        
        if self.tts_enabled:
            try:
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, _speak), 
                    timeout=35
                )
            except Exception as e:
                print(f"TTS: Error: {e}")

# A2A Client for Hosted Service
class A2AClient:
    def __init__(self):
        self.base_url = os.getenv('A2A_SERVICE_URL', 'http://localhost:8887')
        self.message_url = os.getenv('A2A_MESSAGE_URL', self.base_url)
        self.api_key = os.getenv('A2A_API_KEY')
        self.agent_id = f"client_{uuid.uuid4().hex[:8]}"
        self.agent_card = None
        
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

# LLM Client
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

# Insurance Client
class InsuranceClient:
    def __init__(self, mcp_url, api_key):
        self.mcp_url = mcp_url
        self.headers = {"Content-Type": "application/json", "X-INF-API-KEY": api_key}
        print("INSURANCE: Client initialized")
    
    def _split_name(self, name):
        parts = name.strip().split()
        if len(parts) == 1:
            return parts[0], ""
        elif len(parts) == 2:
            return parts[0], parts[1]
        else:
            return parts[0], " ".join(parts[1:])
    
    def _format_dob(self, dob):
        if not dob:
            return ""
        
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', dob):
            month, day, year = dob.split('/')
            formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            return formatted
        
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', dob):
            return dob
        
        return dob
    
    async def discovery(self, name, dob, state):
        print(f"INSURANCE: Discovery - {name}, {dob}, {state}")
        first, last = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        formatted_state = state.strip().title() if state else ""
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "insurance_discovery",
                "arguments": {
                    "patientDateOfBirth": formatted_dob,
                    "patientFirstName": first,
                    "patientLastName": last,
                    "patientState": formatted_state
                }
            }
        }
        
        def _request():
            return requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=45)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            
            if "result" in data:
                result_text = str(data["result"])
                
                payer = ""
                member_id = ""
                
                for pattern in [r'payer[:\s]*([^\n,;]+)', r'insurance[:\s]*([^\n,;]+)', r'plan[:\s]*([^\n,;]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        payer = match.group(1).strip().title()
                        break
                
                for pattern in [r'member\s*id[:\s]*([a-za-z0-9\-]+)', r'subscriber\s*id[:\s]*([a-za-z0-9\-]+)', r'policy\s*id[:\s]*([a-za-z0-9\-]+)', r'policy[:\s]*([a-za-z0-9\-]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        member_id = match.group(1).strip().upper()
                        break
                
                return {"success": True, "payer": payer, "member_id": member_id}
        
        return {"success": False}
    
    async def eligibility(self, name, dob, subscriber_id, payer_name, provider_name):
        print(f"INSURANCE: Eligibility check")
        first, last = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        
        provider_clean = re.sub(r'\b(Dr\.?|MD|DO)\b', '', provider_name, flags=re.IGNORECASE).strip()
        provider_first, provider_last = self._split_name(provider_clean)
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"eligibility_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "benefits_eligibility",
                "arguments": {
                    "patientFirstName": first,
                    "patientLastName": last,
                    "patientDateOfBirth": formatted_dob,
                    "subscriberId": subscriber_id,
                    "payerName": payer_name,
                    "providerFirstName": provider_first,
                    "providerLastName": provider_last,
                    "providerNpi": "1234567890"
                }
            }
        }
        
        def _request():
            return requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=45)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            
            if "result" in data:
                result_text = str(data["result"])
                
                copay = ""
                copay_patterns = [r'co-?pay[:\s]*\$?([0-9,]+)', r'copayment[:\s]*\$?([0-9,]+)', r'patient\s+responsibility[:\s]*\$?([0-9,]+)']
                
                for pattern in copay_patterns:
                    copay_match = re.search(pattern, result_text.lower())
                    if copay_match:
                        copay = copay_match.group(1)
                        break
                
                return {"success": True, "copay": copay}
        
        return {"success": False}

# Healthcare Agent
class HealthcareAgent:
    def __init__(self):
        self.session = Session()
        self.audio = AudioSystem()
        
        # Initialize LLM client
        jwt_token = os.getenv('JWT_TOKEN')
        endpoint_url = os.getenv('ENDPOINT_URL')
        project_id = os.getenv('PROJECT_ID')
        connection_id = os.getenv('CONNECTION_ID')
        
        if not all([jwt_token, endpoint_url, project_id, connection_id]):
            raise Exception("Missing JWT config")
            
        self.llm = LLMClient(jwt_token, endpoint_url, project_id, connection_id)
        
        # Initialize insurance client
        mcp_url = os.getenv('MCP_URL')
        insurance_key = os.getenv('X_INF_API_KEY')
        if not mcp_url or not insurance_key:
            raise Exception("Missing insurance config")
            
        self.insurance = InsuranceClient(mcp_url, insurance_key)
        
        # Initialize A2A client
        self.a2a_client = None
        try:
            self.a2a_client = A2AClient()
        except:
            print("A2A client not available")
    
    async def start(self):
        print(f"Healthcare Agent starting - Session {self.session.id}")
        
        if self.a2a_client:
            await self.a2a_client.discover_agent()
        
        initial_message = "Hello! I'm your healthcare appointment assistant. Let's start by getting your basic information. What's your full name?"
        await self.audio.speak(initial_message)
        self.session.add_interaction("assistant", initial_message)
        
        turn = 0
        errors = 0
        
        while turn < 50 and errors < 3:
            turn += 1
            print(f"--- Turn {turn} ---")
            
            user_input = await self.audio.listen(timeout=5)
            
            if user_input in ["UNCLEAR", "TIMEOUT", "ERROR"]:
                errors += 1
                if user_input == "TIMEOUT":
                    await self.audio.speak("I'm still here. What would you like me to help you with?")
                else:
                    await self.audio.speak("I didn't catch that clearly. Could you please repeat?")
                continue
            
            if not user_input:
                continue
            
            errors = 0
            print(f"USER: {user_input}")
            self.session.add_interaction("user", user_input)
            
            if any(phrase in user_input.lower() for phrase in ['bye', 'goodbye', 'end', 'quit']):
                await self.audio.speak("Thank you for calling. Have a great day!")
                self.session.add_interaction("assistant", "Thank you for calling. Have a great day!")
                break
            
            if self.session.in_triage_mode:
                await self._handle_triage_conversation(user_input)
            else:
                result = await self.llm.process(user_input, self.session)
                
                if result.get("extract"):
                    for key, value in result["extract"].items():
                        if value:
                            self.session.data[key] = value
                            print(f"SESSION-UPDATE: Set {key} = {value}")
                
                if (result.get("need_triage") and not self.session.triage_complete and 
                    self.session.triage_attempts < 1 and self.a2a_client):
                    
                    print("TRIAGE: Starting integrated triage conversation")
                    await self._start_integrated_triage()
                    continue
                
                if result.get("call_discovery"):
                    required = ['name', 'date_of_birth', 'state']
                    if all(k in self.session.data and self.session.data[k] for k in required):
                        print("INSURANCE-DISCOVERY: Calling API...")
                        discovery = await self.insurance.discovery(
                            self.session.data['name'],
                            self.session.data['date_of_birth'],
                            self.session.data['state']
                        )
                        if discovery["success"]:
                            self.session.data['payer'] = discovery['payer']
                            self.session.data['member_id'] = discovery['member_id']
                            
                            insurance_message = f"Great! I found your insurance: {discovery['payer']}, Policy ID: {discovery['member_id']}."
                            await self.audio.speak(insurance_message)
                            self.session.add_interaction("assistant", insurance_message)
                        else:
                            fallback_msg = "I had some trouble finding your insurance, but we can proceed."
                            await self.audio.speak(fallback_msg)
                            self.session.add_interaction("assistant", fallback_msg)
                
                if result.get("call_eligibility"):
                    required = ['name', 'date_of_birth', 'member_id', 'payer', 'provider_name']
                    if all(k in self.session.data and self.session.data[k] for k in required):
                        print("INSURANCE-ELIGIBILITY: Calling API...")
                        eligibility = await self.insurance.eligibility(
                            self.session.data['name'],
                            self.session.data['date_of_birth'],
                            self.session.data['member_id'],
                            self.session.data['payer'],
                            self.session.data['provider_name']
                        )
                        if eligibility["success"] and eligibility.get('copay'):
                            eligibility_message = f"Perfect! Your insurance is verified. Payer: {self.session.data['payer']}, Policy ID: {self.session.data['member_id']}, Your copay will be ${eligibility['copay']}."
                            await self.audio.speak(eligibility_message)
                            self.session.add_interaction("assistant", eligibility_message)
                        else:
                            fallback_message = f"Your insurance {self.session.data['payer']} with Policy ID {self.session.data['member_id']} is on file. We can proceed with scheduling."
                            await self.audio.speak(fallback_message)
                            self.session.add_interaction("assistant", fallback_message)
                
                response = result.get("response", "")
                if response:
                    await self.audio.speak(response)
                    self.session.add_interaction("assistant", response)
                
                if result.get("done"):
                    confirmation = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    final_message = f"Excellent! Your appointment is confirmed. Confirmation number: {confirmation}. You'll receive an email confirmation shortly. Thank you for calling!"
                    await self.audio.speak(final_message)
                    self.session.add_interaction("assistant", final_message)
                    break
        
        print(f"Conversation ended. Final data: {self.session.data}")
        
        saved_file = self.session.save_to_file()
        if saved_file:
            print(f"Session saved to: {saved_file}")
    
    async def _start_integrated_triage(self):
        self.session.triage_attempts += 1
        self.session.in_triage_mode = True
        
        print("TRIAGE: Starting integrated triage conversation")
        
        triage_intro = "I need to do a quick medical assessment to better assist you. Let me ask you a few health-related questions."
        
        try:
            await self.audio.speak(triage_intro)
            self.session.add_interaction("assistant", triage_intro)
            
            age = 33
            sex = "female"
            complaint = self.session.data.get('reason', 'general health concern')
            
            message_parts = [{"kind": "text", "text": f"I am {age} years old, {sex}. {complaint}"}]
            result = await self.a2a_client.send_message(message_parts)
            
            if not result:
                print("TRIAGE: Failed to start - falling back to normal flow")
                await self._end_triage_mode("I'll help you schedule your appointment without the assessment.")
                return
            
            if result.get('kind') == 'task':
                self.session.triage_task_id = result['id']
                self.session.triage_context_id = result['contextId']
                
                print(f"TRIAGE: Started task {self.session.triage_task_id}")
                
                if result['status'].get('message'):
                    triage_question = self._extract_text_from_message(result['status']['message'])
                    if triage_question:
                        await self.audio.speak(triage_question)
                        self.session.add_interaction("assistant", triage_question)
                
        except Exception as e:
            print(f"TRIAGE: Error starting: {e}")
            await self._end_triage_mode("Let me help you schedule your appointment.")
    
    async def _handle_triage_conversation(self, user_input):
        print(f"TRIAGE: User response: {user_input}")
        
        try:
            message_parts = [{"kind": "text", "text": user_input}]
            result = await self.a2a_client.send_message(
                message_parts, 
                task_id=self.session.triage_task_id, 
                context_id=self.session.triage_context_id
            )
            
            if not result:
                print("TRIAGE: Failed to continue - ending triage")
                await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
                return
            
            task_state = result['status']['state']
            print(f"TRIAGE: A2A task state: {task_state}")
            
            if task_state == TaskState.completed:
                print("TRIAGE: Assessment COMPLETED - exiting A2A mode")
                
                if result.get('artifacts'):
                    artifact = result['artifacts'][0]
                    triage_data = self._extract_triage_results(artifact)
                    if triage_data:
                        self.session.triage_results.update(triage_data)
                        print(f"TRIAGE: Results extracted: {triage_data}")
                
                urgency = self.session.triage_results.get('urgency_level', 'standard')
                doctor_type = self.session.triage_results.get('doctor_type', 'general practitioner')
                
                completion_message = f"Thank you for the assessment. Based on your responses, I recommend seeing a {doctor_type}. Priority level: {urgency}. Now let's get you scheduled. I'll need your date of birth for insurance verification."
                
                await self._end_triage_mode()
                
                await self.audio.speak(completion_message)
                self.session.add_interaction("assistant", completion_message)
                
                return
                
            elif task_state == TaskState.input_required:
                if result['status'].get('message'):
                    next_question = self._extract_text_from_message(result['status']['message'])
                    if next_question:
                        await self.audio.speak(next_question)
                        self.session.add_interaction("assistant", next_question)
                else:
                    print("TRIAGE: No message in input-required state - ending triage")
                    await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
                
            elif task_state in [TaskState.failed, TaskState.canceled]:
                print(f"TRIAGE: Task ended with state: {task_state}")
                await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
                
        except Exception as e:
            print(f"TRIAGE: Error in conversation: {e}")
            await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
    
    async def _end_triage_mode(self, message=None):
        print("TRIAGE: Ending triage mode - cleaning up A2A connection")
        
        self.session.in_triage_mode = False
        self.session.triage_complete = True
        
        self.session.triage_task_id = None
        self.session.triage_context_id = None
        
        print("TRIAGE: Mode ended - returning to normal appointment flow")
        
        if message:
            await self.audio.speak(message)
            self.session.add_interaction("assistant", message)
    
    def _extract_text_from_message(self, message):
        if not message or not message.get('parts'):
            return None
        
        for part in message['parts']:
            if part.get('kind') == 'text':
                return part.get('text', '')
        
        return None
    
    def _extract_triage_results(self, artifact):
        if not artifact or not artifact.get('parts'):
            return {}
        
        for part in artifact['parts']:
            if part.get('kind') == 'data' and part.get('data'):
                return part['data']
        
        return {}

def run_agent():
    print("=" * 50)
    print("HEALTHCARE VOICE + A2A + MCP AGENT")
    print("=" * 50)
    
    jwt_required = ['JWT_TOKEN', 'ENDPOINT_URL', 'PROJECT_ID', 'CONNECTION_ID']
    insurance_required = ['MCP_URL', 'X_INF_API_KEY']
    a2a_required = ['A2A_SERVICE_URL', 'A2A_MESSAGE_URL', 'A2A_API_KEY']
    
    missing = []
    missing.extend([var for var in jwt_required if not os.getenv(var)])
    missing.extend([var for var in insurance_required if not os.getenv(var)])
    missing.extend([var for var in a2a_required if not os.getenv(var)])
    
    if missing:
        print(f"ERROR: Missing config: {missing}")
        return
    
    print("Configuration validated")
    print(f"A2A Service URL: {os.getenv('A2A_SERVICE_URL')}")
    print(f"A2A Message URL: {os.getenv('A2A_MESSAGE_URL')}")
    
    if AUDIO_AVAILABLE:
        print("Audio system available - Triage conversation integrated")
    else:
        print("Console mode only")
    
    async def start():
        try:
            agent = HealthcareAgent()
            await agent.start()
        except KeyboardInterrupt:
            print("\nAgent stopped by user")
        except Exception as e:
            print(f"Agent error: {e}")
    
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("\nShutting down...")

def main():
    run_agent()

if __name__ == "__main__":
    main()