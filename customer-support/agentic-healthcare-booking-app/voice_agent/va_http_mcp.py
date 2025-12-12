"""
Healthcare Voice Agent - HTTP Partner Triage + MCP Insurance + Voice Processing
"""
import asyncio
import json
import logging
import os
import re
import base64
import tempfile
from datetime import datetime
from http import HTTPStatus
from typing import Dict, Optional
import uuid
import random
import string

import requests
import speech_recognition as sr
from gtts import gTTS
import pygame
import pyttsx3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURATION

def load_config():
    """Load configuration from environment"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    # Required configs
    config = {
        'jwt_token': os.getenv('JWT_TOKEN'),
        'endpoint_url': os.getenv('ENDPOINT_URL'),
        'project_id': os.getenv('PROJECT_ID'),
        'connection_id': os.getenv('CONNECTION_ID'),
        'mcp_url': os.getenv('MCP_URL'),
        'insurance_api_key': os.getenv('X_INF_API_KEY'),
        
        # Optional triage configs
        'triage_app_id': os.getenv('TRIAGE_APP_ID'),
        'triage_app_key': os.getenv('TRIAGE_APP_KEY'),
        'triage_instance_id': os.getenv('TRIAGE_INSTANCE_ID'),
        'triage_token_url': os.getenv('TRIAGE_TOKEN_URL'),
        'triage_base_url': os.getenv('TRIAGE_BASE_URL')
    }
    
    # Check required
    required = ['jwt_token', 'endpoint_url', 'project_id', 'connection_id', 'mcp_url', 'insurance_api_key']
    missing = [k for k in required if not config[k]]
    
    if missing:
        print(f"❌ Missing required configs: {missing}")
        return None
    
    # Check triage availability
    triage_required = ['triage_app_id', 'triage_app_key', 'triage_instance_id', 'triage_token_url', 'triage_base_url']
    config['triage_available'] = all(config[k] for k in triage_required)
    
    print(f"✅ Config loaded. Triage: {'Available' if config['triage_available'] else 'Disabled'}")
    return config

# SIMPLE SESSION TRACKING

class Session:
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.data = {}
        self.conversation = []
        self.triage_complete = False
        self.triage_data = {}
    
    def add_message(self, role: str, message: str):
        self.conversation.append({
            "role": role,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
    
    def save(self):
        try:
            os.makedirs("sessions", exist_ok=True)
            filename = f"sessions/session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.id}.json"
            
            with open(filename, 'w') as f:
                json.dump({
                    "session_id": self.id,
                    "data": self.data,
                    "conversation": self.conversation,
                    "triage_complete": self.triage_complete,
                    "triage_data": self.triage_data
                }, f, indent=2)
            
            print(f"💾 Session saved: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Save failed: {e}")
            return ""

# SIMPLE AUDIO WITH ENHANCED LOGGING

class SimpleAudio:
    def __init__(self):
        print("🎤 Initializing audio system...")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize pygame with better settings for faster audio
        pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=1024)
        pygame.mixer.init()
        
        # Calibrate microphone
        print("🎤 Calibrating microphone...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        
        # Optimize recognition settings
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8
        
        print("✅ Audio system ready and optimized")
    
    async def listen(self) -> str:
        print("🎧 LISTENING: Waiting for speech...")
        
        def _listen():
            try:
                with self.microphone as source:
                    print("🎧 Audio capture started...")
                    audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=8)
                
                print("🧠 PROCESSING: Sending to Google Speech API...")
                result = self.recognizer.recognize_google(audio, language='en-US')
                print(f"✅ RECOGNIZED: '{result}'")
                return result.strip()
                
            except sr.UnknownValueError:
                print("❌ UNCLEAR: Could not understand audio")
                return "UNCLEAR"
            except sr.WaitTimeoutError:
                print("⏰ TIMEOUT: No speech detected")
                return "TIMEOUT"
            except sr.RequestError as e:
                print(f"❌ NETWORK ERROR: {e}")
                return "ERROR"
            except Exception as e:
                print(f"❌ LISTEN ERROR: {e}")
                return "ERROR"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _listen)
        print(f"🎧 LISTEN RESULT: {result}")
        return result
    
    async def speak(self, text: str):
        if not text:
            return
        
        print(f"🗣️ SPEAKING: {text}")
        start_time = datetime.now()
        
        def _speak():
            try:
                print("🔊 TTS: Generating audio with gTTS...")
                tts = gTTS(text=text, lang='en', slow=False)
                
                print("🔊 TTS: Saving audio file...")
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                    tts.save(tmp.name)
                    
                    print("🔊 TTS: Loading audio into pygame...")
                    pygame.mixer.music.load(tmp.name)
                    
                    print("🔊 TTS: Starting playback...")
                    pygame.mixer.music.play()
                    
                    # Wait for playback to finish with reduced wait time
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(50)  # Reduced from 100ms to 50ms
                    
                    print("🔊 TTS: Playback complete, cleaning up...")
                    os.unlink(tmp.name)
                    
            except Exception as e:
                print(f"❌ TTS ERROR: {e}")
                print("🔊 TTS: Attempting fallback to pyttsx3...")
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.setProperty('rate', 180)  # Faster speech
                    engine.say(text)
                    engine.runAndWait()
                    print("✅ TTS: Fallback successful")
                except Exception as e2:
                    print(f"❌ TTS FALLBACK ERROR: {e2}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _speak)
        
        duration = (datetime.now() - start_time).total_seconds()
        print(f"✅ SPEAKING COMPLETE: {duration:.2f}s")

# HTTP TRIAGE CLIENT

class TriageClient:
    def __init__(self, app_id: str, app_key: str, instance_id: str, token_url: str, base_url: str):
        self.app_id = app_id
        self.app_key = app_key
        self.instance_id = instance_id
        self.token_url = token_url
        self.base_url = base_url
        print(f"🔗 TRIAGE CLIENT: Initialized with instance_id: {instance_id}")
    
    async def get_token(self) -> str:
        """Get access token with instance-id"""
        print("🔑 TRIAGE: Getting access token...")
        print(f"🔑 TRIAGE: Token URL: {self.token_url}")
        print(f"🔑 TRIAGE: App ID: {self.app_id}")
        print(f"🔑 TRIAGE: Instance ID: {self.instance_id}")
        
        creds = base64.b64encode(f"{self.app_id}:{self.app_key}".encode()).decode()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {creds}",
            "instance-id": self.instance_id  # CRITICAL!
        }
        
        payload = {"grant_type": "client_credentials"}
        
        print(f"🔑 TRIAGE: Request headers (without auth): {{'Content-Type': 'application/json', 'instance-id': '{self.instance_id}'}}")
        print(f"🔑 TRIAGE: Request payload: {payload}")
        
        def _request():
            return requests.post(
                self.token_url,
                headers=headers,
                json=payload,
                timeout=30
            )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        print(f"🔑 TRIAGE: Response status: {response.status_code}")
        print(f"🔑 TRIAGE: Response headers: {dict(response.headers)}")
        
        if response.status_code == HTTPStatus.OK:
            token_data = response.json()
            print(f"🔑 TRIAGE: Response data keys: {list(token_data.keys())}")
            token = token_data['access_token']
            print(f"✅ TRIAGE: Token received: {token[:20]}...")
            return token
        else:
            print(f"❌ TRIAGE: Token failed with response: {response.text}")
            raise Exception(f"Token failed: {response.status_code}")
    
    async def create_survey(self, token: str, age: int = 30, sex: str = "male") -> str:
        """Create survey"""
        print(f"🆕 TRIAGE: Creating survey for {age}yo {sex}...")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "sex": sex.lower(),
            "age": {"value": age, "unit": "year"}
        }
        
        url = f"{self.base_url}/surveys"
        print(f"🆕 TRIAGE: Survey URL: {url}")
        print(f"🆕 TRIAGE: Survey payload: {payload}")
        
        def _request():
            return requests.post(url, headers=headers, json=payload, timeout=30)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        print(f"🆕 TRIAGE: Survey response status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            survey_data = response.json()
            print(f"🆕 TRIAGE: Survey response data: {survey_data}")
            survey_id = survey_data['survey_id']
            print(f"✅ TRIAGE: Survey created: {survey_id}")
            return survey_id
        else:
            print(f"❌ TRIAGE: Survey failed with response: {response.text}")
            raise Exception(f"Survey failed: {response.status_code}")
    
    async def send_message(self, token: str, survey_id: str, message: str) -> Dict:
        """Send message to triage"""
        print(f"💬 TRIAGE: Sending message to survey {survey_id}")
        print(f"💬 TRIAGE: Message: '{message}'")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {"user_message": message}
        url = f"{self.base_url}/surveys/{survey_id}/messages"
        
        print(f"💬 TRIAGE: Message URL: {url}")
        print(f"💬 TRIAGE: Message payload: {payload}")
        
        def _request():
            return requests.post(url, headers=headers, json=payload, timeout=30)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        print(f"💬 TRIAGE: Message response status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"💬 TRIAGE: Message response data: {data}")
            
            assistant_msg = data.get('assistant_message', '')
            survey_state = data.get('survey_state', 'active')
            
            print(f"✅ TRIAGE: Assistant response: '{assistant_msg}'")
            print(f"✅ TRIAGE: Survey state: {survey_state}")
            
            return {
                "success": True,
                "response": assistant_msg,
                "state": survey_state
            }
        else:
            print(f"❌ TRIAGE: Message failed with response: {response.text}")
            return {"success": False, "response": "Sorry, technical issue."}
    
    async def get_summary(self, token: str, survey_id: str) -> Dict:
        """Get triage summary"""
        print(f"📋 TRIAGE: Getting summary for survey {survey_id}")
        
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/surveys/{survey_id}/summary"
        
        print(f"📋 TRIAGE: Summary URL: {url}")
        
        def _request():
            return requests.get(url, headers=headers, timeout=30)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        print(f"📋 TRIAGE: Summary response status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"📋 TRIAGE: Summary response data: {data}")
            
            # Parse summary
            urgency = "low"
            doctor = "general practitioner"
            
            # Extract urgency
            print("📋 TRIAGE: Parsing urgency level...")
            for key in ['urgency', 'severity', 'priority']:
                if key in data:
                    val = str(data[key]).lower()
                    print(f"📋 TRIAGE: Found {key}: {val}")
                    if val in ['high', 'urgent', 'emergency']:
                        urgency = "high"
                    elif val in ['medium', 'moderate']:
                        urgency = "medium"
                    break
            
            # Extract doctor type
            print("📋 TRIAGE: Parsing doctor recommendation...")
            for key in ['doctor_type', 'specialist', 'recommendation']:
                if key in data:
                    doctor = str(data[key])
                    print(f"📋 TRIAGE: Found {key}: {doctor}")
                    break
            
            notes = str(data.get('notes', ''))
            
            result = {
                "success": True,
                "urgency_level": urgency,
                "doctor_type": doctor,
                "notes": notes
            }
            
            print(f"✅ TRIAGE: Parsed summary: {result}")
            return result
        else:
            print(f"❌ TRIAGE: Summary failed with response: {response.text}")
            return {"success": False}

# MCP INSURANCE CLIENT WITH ENHANCED LOGGING

class InsuranceClient:
    def __init__(self, mcp_url: str, api_key: str):
        self.mcp_url = mcp_url
        self.headers = {
            "Content-Type": "application/json",
            "X-INF-API-KEY": api_key
        }
        print(f"🔗 INSURANCE CLIENT: Initialized with MCP URL: {mcp_url}")
        print(f"🔗 INSURANCE CLIENT: API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
    
    def _split_name(self, full_name: str) -> tuple:
        """Split name into first, last"""
        if not full_name:
            return "", ""
        
        parts = full_name.strip().split()
        if len(parts) == 1:
            result = (parts[0], "")
        elif len(parts) == 2:
            result = (parts[0], parts[1])
        else:
            result = (parts[0], " ".join(parts[1:]))
        
        print(f"👤 INSURANCE: Split name '{full_name}' → First: '{result[0]}', Last: '{result[1]}'")
        return result
    
    def _format_dob(self, dob: str) -> str:
        """Format DOB to YYYY-MM-DD"""
        if not dob:
            return ""
        
        # MM/DD/YYYY
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', dob):
            month, day, year = dob.split('/')
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Already YYYY-MM-DD
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', dob):
            return dob
        
        return dob
    
    async def discovery(self, name: str, dob: str, state: str) -> Dict:
        """Call discovery API"""
        first_name, last_name = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "insurance_discovery",
                "arguments": {
                    "patientDateOfBirth": formatted_dob,
                    "patientFirstName": first_name,
                    "patientLastName": last_name,
                    "patientState": state
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
                
                # Extract payer and member ID
                payer = ""
                member_id = ""
                
                # Find payer
                for pattern in [r'payer[:\s]*([^\n,;]+)', r'insurance[:\s]*([^\n,;]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        payer = match.group(1).strip().title()
                        break
                
                # Find member ID
                for pattern in [r'member\s*id[:\s]*([a-za-z0-9\-]+)', r'policy[:\s]*([a-za-z0-9\-]+)']:
                    match = re.search(pattern, result_text.lower())
                    if match:
                        member_id = match.group(1).strip().upper()
                        break
                
                return {
                    "success": True,
                    "payer": payer,
                    "member_id": member_id,
                    "raw": result_text
                }
        
        return {"success": False, "error": "Discovery failed"}
    
    async def eligibility(self, name: str, dob: str, subscriber_id: str, 
                         payer_name: str, provider_name: str) -> Dict:
        """Call eligibility API"""
        first_name, last_name = self._split_name(name)
        formatted_dob = self._format_dob(dob)
        
        # Split provider name
        provider_clean = re.sub(r'\b(Dr\.?|MD|DO)\b', '', provider_name, flags=re.IGNORECASE).strip()
        provider_first, provider_last = self._split_name(provider_clean)
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"eligibility_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": {
                "name": "benefits_eligibility",
                "arguments": {
                    "patientFirstName": first_name,
                    "patientLastName": last_name,
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
                
                # Extract copay
                copay = ""
                copay_match = re.search(r'co-?pay[:\s]*\$?([0-9,]+)', result_text.lower())
                if copay_match:
                    copay = copay_match.group(1)
                
                return {
                    "success": True,
                    "copay": copay,
                    "raw": result_text
                }
        
        return {"success": False, "error": "Eligibility failed"}

# LLM CLIENT WITH ENHANCED LOGGING

class LLMClient:
    def __init__(self, jwt_token: str, endpoint_url: str, project_id: str, connection_id: str):
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {jwt_token}'
        }
        self.endpoint_url = endpoint_url
        self.project_id = project_id
        self.connection_id = connection_id
        
        print(f"🧠 LLM CLIENT: Initialized")
        print(f"🧠 LLM CLIENT: Endpoint: {endpoint_url}")
        print(f"🧠 LLM CLIENT: Project ID: {project_id}")
        print(f"🧠 LLM CLIENT: Connection ID: {connection_id}")
    
    async def process(self, user_input: str, session: Session) -> Dict:
        """Process user input and return action"""
        
        print(f"\n🧠 LLM: Processing user input: '{user_input}'")
        print(f"🧠 LLM: Current session data keys: {list(session.data.keys())}")
        print(f"🧠 LLM: Session data: {session.data}")
        
        prompt = f"""You are a healthcare appointment scheduler.

Current session data: {json.dumps(session.data)}
User input: "{user_input}"

Flow:
1. Get name, phone, reason
2. If reason is medical (pain, symptoms, illness) → set need_triage=true
3. After triage → get DOB, state → call discovery
4. Get provider → call eligibility  
5. Schedule appointment

Respond with JSON:
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
        
        print(f"🧠 LLM: Request payload prepared")
        print(f"🧠 LLM: System prompt length: {len(prompt)} chars")
        
        def _request():
            start_time = datetime.now()
            print(f"🧠 LLM: Sending request to {self.endpoint_url}")
            response = requests.post(self.endpoint_url, headers=self.headers, json=payload, timeout=30)
            duration = (datetime.now() - start_time).total_seconds()
            print(f"🧠 LLM: Request took {duration:.2f}s")
            return response
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _request)
        
        print(f"🧠 LLM: Response status: {response.status_code}")
        
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            print(f"🧠 LLM: Response data keys: {list(data.keys())}")
            
            if 'choices' in data and data['choices']:
                content = data['choices'][0]['message']['content']
                print(f"🧠 LLM: Raw response content: {content}")
                
                # Parse JSON
                try:
                    if content.startswith('```json'):
                        content = content[7:]
                    if content.endswith('```'):
                        content = content[:-3]
                    
                    result = json.loads(content.strip())
                    print(f"🧠 LLM: Parsed JSON successfully")
                    print(f"🧠 LLM: Response: '{result.get('response', '')}'")
                    print(f"🧠 LLM: Extract: {result.get('extract', {})}")
                    print(f"🧠 LLM: Need triage: {result.get('need_triage', False)}")
                    print(f"🧠 LLM: Call discovery: {result.get('call_discovery', False)}")
                    print(f"🧠 LLM: Call eligibility: {result.get('call_eligibility', False)}")
                    print(f"🧠 LLM: Done: {result.get('done', False)}")
                    
                    return result
                except Exception as e:
                    print(f"❌ LLM: JSON parse error: {e}")
                    print(f"❌ LLM: Content was: {content}")
            else:
                print(f"❌ LLM: No choices in response")
        else:
            print(f"❌ LLM: Request failed with response: {response.text}")
        
        # Fallback
        fallback = {
            "response": "I understand. Please continue.",
            "extract": {},
            "need_triage": False,
            "call_discovery": False,
            "call_eligibility": False,
            "done": False
        }
        print(f"🧠 LLM: Using fallback response")
        return fallback

class HealthcareAgent:
    def __init__(self, config: Dict):
        self.session = Session()
        self.audio = SimpleAudio()
        self.llm = LLMClient(
            config['jwt_token'],
            config['endpoint_url'], 
            config['project_id'],
            config['connection_id']
        )
        self.insurance = InsuranceClient(config['mcp_url'], config['insurance_api_key'])
        
        # Triage client (optional)
        self.triage = None
        if config['triage_available']:
            self.triage = TriageClient(
                config['triage_app_id'],
                config['triage_app_key'],
                config['triage_instance_id'],
                config['triage_token_url'],
                config['triage_base_url']
            )
        
        print(f"🏥 Agent ready. Triage: {'✅' if self.triage else '❌'}")
    
    async def run_triage(self, chief_complaint: str):
        """Run HTTP triage session"""
        if not self.triage:
            print("⚠️  TRIAGE: Not available, using fallback")
            await self.audio.speak("I'll help you schedule an appointment with a healthcare provider.")
            return
        
        try:
            print(f"\n🩺 TRIAGE: Starting session with complaint: '{chief_complaint}'")
            
            # Get patient demographics
            age = 30
            sex = "male"
            
            print(f"🩺 TRIAGE: Extracting demographics from session data...")
            
            # Try to extract age from DOB
            if 'date_of_birth' in self.session.data:
                try:
                    dob = self.session.data['date_of_birth']
                    print(f"🩺 TRIAGE: Found DOB: {dob}")
                    if '-' in dob:
                        birth_year = int(dob.split('-')[0])
                        age = max(1, datetime.now().year - birth_year)
                        print(f"🩺 TRIAGE: Calculated age: {age}")
                except Exception as e:
                    print(f"🩺 TRIAGE: Age calculation error: {e}")
            
            # Basic sex inference
            name = self.session.data.get('name', '').lower()
            print(f"🩺 TRIAGE: Checking name for gender hints: '{name}'")
            if any(female in name for female in ['mary', 'sarah', 'jessica', 'jennifer', 'amanda']):
                sex = "female"
                print(f"🩺 TRIAGE: Inferred sex: female")
            
            print(f"🩺 TRIAGE: Final demographics - Age: {age}, Sex: {sex}")
            
            # Start triage
            print(f"🩺 TRIAGE: Getting access token...")
            token = await self.triage.get_token()
            
            print(f"🩺 TRIAGE: Creating survey...")
            survey_id = await self.triage.create_survey(token, age, sex)
            
            await self.audio.speak("I need to ask some medical questions to assess your condition.")
            
            # Send initial complaint
            print(f"🩺 TRIAGE: Sending initial complaint...")
            result = await self.triage.send_message(token, survey_id, chief_complaint)
            if result["success"] and result["response"]:
                await self.audio.speak(result["response"])
            
            # Continue conversation
            max_turns = 10
            print(f"🩺 TRIAGE: Starting conversation loop (max {max_turns} turns)...")
            
            for turn in range(max_turns):
                print(f"\n🩺 TRIAGE: Turn {turn + 1}/{max_turns}")
                
                # Check if done
                current_state = result.get("state", "").lower()
                print(f"🩺 TRIAGE: Current state: {current_state}")
                
                if current_state in ["completed", "finished", "done"]:
                    print(f"🩺 TRIAGE: Survey completed!")
                    break
                
                # Listen for response
                print(f"🩺 TRIAGE: Waiting for patient response...")
                user_input = await self.audio.listen()
                
                if user_input in ["UNCLEAR", "TIMEOUT", "ERROR"]:
                    print(f"🩺 TRIAGE: Speech issue: {user_input}")
                    await self.audio.speak("I didn't catch that. Please try again.")
                    continue
                
                print(f"👤 TRIAGE Patient: {user_input}")
                
                # Send to triage
                result = await self.triage.send_message(token, survey_id, user_input)
                if result["success"] and result["response"]:
                    await self.audio.speak(result["response"])
                
                # Check completion
                if result.get("state", "").lower() in ["completed", "finished", "done"]:
                    print(f"🩺 TRIAGE: Survey completed after turn {turn + 1}!")
                    break
            
            # Get summary
            print(f"🩺 TRIAGE: Getting final summary...")
            summary = await self.triage.get_summary(token, survey_id)
            
            if summary["success"]:
                self.session.triage_complete = True
                self.session.triage_data = summary
                
                urgency = summary["urgency_level"]
                doctor = summary["doctor_type"]
                
                print(f"✅ TRIAGE: Assessment complete!")
                print(f"   Urgency: {urgency}")
                print(f"   Doctor: {doctor}")
                print(f"   Notes: {summary.get('notes', '')}")
                
                await self.audio.speak(f"Based on the assessment, your condition appears to be {urgency} priority. I recommend seeing a {doctor}. Now let me help schedule this appointment.")
            else:
                print(f"❌ TRIAGE: Summary failed")
                await self.audio.speak("I've completed the medical assessment. Now let me help schedule your appointment.")
            
        except Exception as e:
            print(f"❌ TRIAGE: Error during session: {e}")
            await self.audio.speak("I'll help you schedule an appointment with a healthcare provider.")
    
    async def start(self):
        """Start conversation"""
        print(f"\n🎯 Starting conversation - Session {self.session.id}")
        
        # Greeting
        await self.audio.speak("Hello! I'm your healthcare appointment assistant. To get started, could you please tell me your full name?")
        self.session.add_message("assistant", "Hello! I'm your healthcare appointment assistant. To get started, could you please tell me your full name?")
        
        # Main loop
        turn = 0
        errors = 0
        
        while turn < 50 and errors < 3:
            turn += 1
            print(f"\n--- Turn {turn} ---")
            
            # Listen
            user_input = await self.audio.listen()
            
            if user_input in ["UNCLEAR", "TIMEOUT", "ERROR"]:
                errors += 1
                await self.audio.speak("I didn't catch that. Could you please repeat?")
                continue
            
            if not user_input:
                continue
            
            errors = 0
            print(f"👤 User: {user_input}")
            self.session.add_message("user", user_input)
            
            # Check for goodbye
            if any(phrase in user_input.lower() for phrase in ['bye', 'goodbye', 'end', 'hang up']):
                await self.audio.speak("Thank you for calling. Have a great day!")
                break
            
            # Process with LLM
            llm_result = await self.llm.process(user_input, self.session)
            
            # Update session data
            if llm_result.get("extract"):
                self.session.data.update(llm_result["extract"])
                print(f"📝 Updated: {llm_result['extract']}")
            
            # Handle triage
            if llm_result.get("need_triage") and not self.session.triage_complete:
                await self.run_triage(self.session.data.get('reason', user_input))
            
            # Handle discovery API
            if llm_result.get("call_discovery"):
                required_fields = ['name', 'date_of_birth', 'state']
                print(f"🔍 MAIN: Discovery API requested")
                print(f"🔍 MAIN: Checking required fields: {required_fields}")
                print(f"🔍 MAIN: Available fields: {list(self.session.data.keys())}")
                
                if all(k in self.session.data for k in required_fields):
                    print("🔍 MAIN: All required fields present, calling discovery API...")
                    discovery_result = await self.insurance.discovery(
                        self.session.data['name'],
                        self.session.data['date_of_birth'], 
                        self.session.data['state']
                    )
                    
                    if discovery_result["success"]:
                        self.session.data['payer'] = discovery_result['payer']
                        self.session.data['member_id'] = discovery_result['member_id']
                        print(f"✅ MAIN: Discovery successful!")
                        print(f"   Payer: {discovery_result['payer']}")
                        print(f"   Member ID: {discovery_result['member_id']}")
                    else:
                        print(f"❌ MAIN: Discovery failed: {discovery_result.get('error', 'Unknown error')}")
                else:
                    missing = [k for k in required_fields if k not in self.session.data]
                    print(f"⚠️  MAIN: Discovery skipped - missing fields: {missing}")
            
            # Handle eligibility API  
            if llm_result.get("call_eligibility"):
                required_fields = ['name', 'date_of_birth', 'member_id', 'payer', 'provider_name']
                print(f"💳 MAIN: Eligibility API requested")
                print(f"💳 MAIN: Checking required fields: {required_fields}")
                print(f"💳 MAIN: Available fields: {list(self.session.data.keys())}")
                
                if all(k in self.session.data for k in required_fields):
                    print("💳 MAIN: All required fields present, calling eligibility API...")
                    eligibility_result = await self.insurance.eligibility(
                        self.session.data['name'],
                        self.session.data['date_of_birth'],
                        self.session.data['member_id'],
                        self.session.data['payer'],
                        self.session.data['provider_name']
                    )
                    
                    if eligibility_result["success"]:
                        copay = eligibility_result['copay']
                        print(f"✅ MAIN: Eligibility successful!")
                        print(f"   Copay: ${copay}")
                        
                        if copay:
                            await self.audio.speak(f"Great! I found your insurance. Your copay is ${copay}.")
                        else:
                            await self.audio.speak("I found your insurance information.")
                    else:
                        print(f"❌ MAIN: Eligibility failed: {eligibility_result.get('error', 'Unknown error')}")
                        await self.audio.speak("I had trouble verifying your insurance, but we can proceed with scheduling.")
                else:
                    missing = [k for k in required_fields if k not in self.session.data]
                    print(f"⚠️  MAIN: Eligibility skipped - missing fields: {missing}")
            
            # Speak response
            response = llm_result.get("response", "")
            if response:
                print(f"🏥 MAIN: Agent response: '{response}'")
                await self.audio.speak(response)
                self.session.add_message("assistant", response)
            
            # Check if done
            if llm_result.get("done"):
                print(f"🏁 MAIN: Conversation marked as done by LLM")
                # Generate confirmation if we have enough info
                if self.session.data.get('name') and self.session.data.get('preferred_date'):
                    confirmation = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                    print(f"🎫 MAIN: Generated confirmation code: {confirmation}")
                    await self.audio.speak(f"Perfect! Your appointment is confirmed. Your confirmation number is {confirmation}. Thank you!")
                
                break
            
            print(f"🔄 MAIN: Turn {turn} complete, continuing conversation...")
        
        # Save and end
        filename = self.session.save()
        print(f"\n🏁 Conversation ended. Saved: {filename}")
        print(f"📊 Collected data: {list(self.session.data.keys())}")

# MAIN

async def main():
    """Main entry point"""
    print("🏥 SIMPLE HEALTHCARE VOICE AGENT")
    print("🤖 HTTP Triage + MCP Insurance + Voice")
    print("=" * 50)
    
    config = load_config()
    if not config:
        return
    
    try:
        agent = HealthcareAgent(config)
        await agent.start()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())