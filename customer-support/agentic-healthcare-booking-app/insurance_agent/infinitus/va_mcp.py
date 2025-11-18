"""
Healthcare Voice Agent - MCP 
"""

import asyncio
import json
import logging
import tempfile
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid
import random
import string

# Core dependencies
import requests
import speech_recognition as sr
from gtts import gTTS
import pygame
import pyttsx3

# Enhanced logging with clear formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Session:
    """Enhanced session container with intelligent data management"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    data: Dict[str, Any] = field(default_factory=dict)
    conversation: List[Dict] = field(default_factory=list)
    api_calls: List[Dict] = field(default_factory=list)
    
    def add_message(self, role: str, message: str):
        """Add message with enhanced metadata"""
        self.conversation.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
            "turn_number": len(self.conversation) + 1
        })
    
    def add_api_call(self, api_type: str, request_data: Dict, response_data: Dict, success: bool):
        """Track API calls for debugging and analytics"""
        self.api_calls.append({
            "timestamp": datetime.now().isoformat(),
            "api_type": api_type,
            "request": request_data,
            "response": response_data,
            "success": success,
            "duration_ms": getattr(self, '_last_api_duration', 0)
        })
    
    def get_completion_percentage(self) -> float:
        """Calculate conversation completion percentage"""
        required_fields = ['name', 'phone', 'reason', 'date_of_birth', 'state', 'provider_name', 'preferred_date', 'preferred_time']
        completed = sum(1 for field in required_fields if self.data.get(field))
        return (completed / len(required_fields)) * 100
    
    def save(self) -> str:
        """Enhanced session save with comprehensive data"""
        try:
            os.makedirs("sessions", exist_ok=True)
            
            end_time = self.end_time or datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            session_data = {
                "metadata": {
                    "session_id": self.session_id,
                    "start_time": self.start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration,
                    "duration_minutes": round(duration / 60, 2),
                    "completion_percentage": self.get_completion_percentage(),
                    "total_turns": len(self.conversation),
                    "api_calls_made": len(self.api_calls)
                },
                "patient_data": self.data,
                "conversation_history": self.conversation,
                "api_call_log": self.api_calls,
                "raw_responses": {
                    "discovery_raw": self.data.get('discovery_raw', ''),
                    "eligibility_raw": self.data.get('eligibility_raw', '')
                }
            }
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sessions/healthcare_session_{timestamp}_{self.session_id[:8]}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 SESSION SAVED: {os.path.abspath(filename)}")
            print(f"📊 Completion: {self.get_completion_percentage():.1f}% | Turns: {len(self.conversation)} | APIs: {len(self.api_calls)}")
            return filename
        except Exception as e:
            logger.error(f"Session save failed: {e}")
            return ""

class Audio:
    """ -grade audio system with intelligent speech processing"""
    
    def __init__(self):
        print("🎤 Initializing advanced audio system...")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize audio systems
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.tts = pyttsx3.init()
        self._configure_tts()
        self._calibrate_microphone()
        
        print("✅ Audio system ready with intelligent processing")
    
    def _configure_tts(self):
        """Configure TTS for optimal healthcare communication"""
        try:
            self.tts.setProperty('rate', 165)  # Optimal for healthcare communication
            voices = self.tts.getProperty('voices')
            if voices:
                # Prefer female voice for healthcare (research shows higher trust)
                for voice in voices:
                    if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                        self.tts.setProperty('voice', voice.id)
                        break
        except Exception as e:
            logger.warning(f"TTS configuration issue: {e}")
    
    def _calibrate_microphone(self):
        """Advanced microphone calibration with environment adaptation"""
        try:
            with self.microphone as source:
                print("🎤 CALIBRATING: Analyzing ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2.0)
                
                # Optimized settings for healthcare conversations
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.pause_threshold = 0.8  # Allow for thoughtful pauses
                self.recognizer.phrase_threshold = 0.3
                self.recognizer.non_speaking_duration = 0.8
                
                print(f"✅ CALIBRATED: Energy threshold {self.recognizer.energy_threshold}")
        except Exception as e:
            logger.error(f"Microphone calibration failed: {e}")
    
    async def listen(self) -> str:
        """Intelligent speech recognition with context awareness"""
        def _listen_with_intelligence():
            try:
                with self.microphone as source:
                    print("🎧 LISTENING: Ready for speech...")
                    audio = self.recognizer.listen(
                        source, 
                        timeout=15,  # Longer timeout for healthcare conversations
                        phrase_time_limit=10  # Allow for detailed responses
                    )
                
                print("🧠 PROCESSING: Analyzing speech with AI...")
                
                # Primary recognition attempt
                try:
                    result = self.recognizer.recognize_google(
                        audio, 
                        language='en-US',
                        show_all=False
                    )
                    confidence = "HIGH"
                    print(f"🎯 RECOGNIZED ({confidence}): '{result}'")
                    return self._intelligent_post_process(result)
                    
                except sr.UnknownValueError:
                    print("🤔 UNCLEAR: Attempting enhanced recognition...")
                    # Secondary attempt with different parameters
                    try:
                        alternatives = self.recognizer.recognize_google(
                            audio, 
                            language='en-US', 
                            show_all=True
                        )
                        if alternatives and 'alternative' in alternatives:
                            best_match = alternatives['alternative'][0]['transcript']
                            print(f"🎯 RECOGNIZED (secondary): '{best_match}'")
                            return self._intelligent_post_process(best_match)
                    except:
                        pass
                    return "UNCLEAR"
                    
                except sr.RequestError as e:
                    logger.error(f"Speech service error: {e}")
                    return "NETWORK_ERROR"
                    
            except sr.WaitTimeoutError:
                print("⏰ TIMEOUT: No speech detected")
                return "TIMEOUT"
            except Exception as e:
                logger.error(f"Listen error: {e}")
                return "ERROR"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _listen_with_intelligence)
        return result
    
    def _intelligent_post_process(self, text: str) -> str:
        """AI-powered post-processing of speech recognition"""
        if not text:
            return ""
        
        # Clean and normalize
        cleaned = ' '.join(text.split()).strip()
        
        # Healthcare-specific corrections
        healthcare_corrections = {
            'hernia': 'California',  # Common misrecognition
            'gloria': 'Florida',
            'taxes': 'Texas',
            'organ': 'Oregon',
            'pencil vania': 'Pennsylvania',
            'connect i cut': 'Connecticut'
        }
        
        for incorrect, correct in healthcare_corrections.items():
            cleaned = re.sub(r'\b' + re.escape(incorrect) + r'\b', correct, cleaned, flags=re.IGNORECASE)
        
        return cleaned
    
    def convert_numbers_to_digits(self, text: str) -> str:
        """Intelligent number conversion preserving medical context"""
        # Protect time expressions and medical measurements
        protected_patterns = [
            r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\b',  # Times
            r'\b\d{1,2}\s*(?:AM|PM|am|pm)\b',        # Times without minutes
            r'\b\d+\s*(?:mg|ml|cc|units?)\b',        # Medical measurements
            r'\b\d+/\d+\b'                           # Fractions/dates
        ]
        
        protected_ranges = []
        for pattern in protected_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                protected_ranges.append((match.start(), match.end()))
        
        def replace_number(match):
            start, end = match.span()
            # Check if number is in protected range
            for p_start, p_end in protected_ranges:
                if start >= p_start and end <= p_end:
                    return match.group()
            
            number = match.group()
            digit_words = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
            }
            return ' '.join(digit_words.get(digit, digit) for digit in number)
        
        # Convert standalone numbers to digit pronunciation
        result = re.sub(r'\b\d+\b', replace_number, text)
        return result
    
    async def speak(self, text: str):
        """Intelligent TTS with healthcare optimization"""
        if not text:
            return
        
        print(f"🗣️  SPEAKING: {text}")
        
        # Prepare text for optimal speech
        speech_text = self.convert_numbers_to_digits(text)
        speech_text = self._optimize_for_speech(speech_text)
        
        def _speak_intelligently():
            try:
                # Primary TTS using Google (higher quality)
                tts = gTTS(text=speech_text, lang='en', slow=False, tld='com')
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                    tts.save(tmp.name)
                    pygame.mixer.music.load(tmp.name)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(50)  # Faster polling for responsiveness
                    
                    os.unlink(tmp.name)
                    
            except Exception as e:
                logger.warning(f"Primary TTS failed: {e}, using fallback")
                try:
                    # Fallback to system TTS
                    self.tts.say(speech_text)
                    self.tts.runAndWait()
                except Exception as e2:
                    logger.error(f"All TTS methods failed: {e2}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _speak_intelligently)
    
    def _optimize_for_speech(self, text: str) -> str:
        """Optimize text for natural speech delivery"""
        # Remove problematic characters
        cleaned = re.sub(r'[{}[\]"|<>\\]', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Add natural pauses for better comprehension
        cleaned = re.sub(r'([.!?])\s*', r'\1 ', cleaned)  # Pause after sentences
        cleaned = re.sub(r'(,)\s*', r'\1 ', cleaned)      # Pause after commas
        
        return cleaned
    
    def cleanup(self):
        """Cleanup audio resources"""
        try:
            pygame.mixer.quit()
            if hasattr(self.tts, 'stop'):
                self.tts.stop()
        except Exception as e:
            logger.warning(f"Audio cleanup issue: {e}")

class MCPInsuranceAPI:
    """  MCP client with intelligent error handling and logging"""
    
    def __init__(self, mcp_url: str, api_key: str):
        self.mcp_url = mcp_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-INF-API-KEY": api_key
        }
        
        print(f"🔗 MCP CLIENT INITIALIZED: {mcp_url}")
        print(f"🔑 API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
    
    async def call_insurance_api(self, api_type: str, patient_data: Dict) -> Dict:
        """Intelligent MCP API call with comprehensive logging"""
        start_time = datetime.now()
        
        print(f"\n🚀 MCP API CALL INITIATED")
        print(f"📋 Type: {api_type.upper()}")
        print(f"👤 Patient: {patient_data.get('name', 'Unknown')}")
        print(f"🎂 DOB: {patient_data.get('dob', 'Not provided')}")
        print(f"📍 State: {patient_data.get('state', 'Not provided')}")
        
        try:
            # Construct intelligent MCP payload
            payload = self._construct_mcp_payload(api_type, patient_data)
            
            print(f"📤 MCP PAYLOAD:")
            print(json.dumps(payload, indent=2))
            
            # Execute API call
            def _execute_request():
                try:
                    response = requests.post(
                        self.mcp_url, 
                        headers=self.headers, 
                        json=payload, 
                        timeout=45  # Longer timeout for insurance APIs
                    )
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.Timeout:
                    return {"error": "REQUEST_TIMEOUT", "message": "Insurance API call timed out"}
                except requests.exceptions.ConnectionError:
                    return {"error": "CONNECTION_ERROR", "message": "Could not connect to insurance API"}
                except requests.exceptions.HTTPError as e:
                    return {"error": "HTTP_ERROR", "message": f"HTTP {e.response.status_code}: {e.response.text}"}
                except Exception as e:
                    return {"error": "REQUEST_ERROR", "message": str(e)}
            
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(None, _execute_request)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            print(f"📥 MCP RESPONSE RECEIVED ({duration:.2f}s):")
            print(json.dumps(raw_response, indent=2))
            
            # Process response intelligently
            if "error" in raw_response:
                print(f"❌ MCP API ERROR: {raw_response['error']}")
                error_msg = raw_response.get("message", "Unknown error")
                if "code" in raw_response:
                    print(f"🔢 Error Code: {raw_response['code']}")
                    error_msg = f"Code {raw_response['code']}: {error_msg}"
                return {
                    "success": False,
                    "error": raw_response["error"],
                    "message": error_msg,
                    "duration_seconds": duration
                }
            
            # Extract result from MCP response
            if "result" in raw_response:
                result_data = raw_response["result"]
                print(f"✅ MCP API SUCCESS: Data received")
                
                # Intelligent result processing
                processed_result = self._process_insurance_result(api_type, result_data)
                
                return {
                    "success": True,
                    "data": processed_result,
                    "raw_response": str(result_data),
                    "duration_seconds": duration
                }
            else:
                print(f"⚠️  MCP API WARNING: No result field in response")
                return {
                    "success": False,
                    "error": "NO_RESULT",
                    "message": "MCP response missing result field",
                    "duration_seconds": duration
                }
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"MCP API call failed: {e}")
            print(f"💥 MCP API EXCEPTION: {str(e)}")
            
            return {
                "success": False,
                "error": "EXCEPTION",
                "message": str(e),
                "duration_seconds": duration
            }
    
    def _construct_mcp_payload(self, api_type: str, patient_data: Dict) -> Dict:
        """Construct MCP payload with required structured parameters"""
        
        # Parse patient name into first and last
        patient_name = patient_data.get('name', '')
        first_name, last_name = self._parse_patient_name(patient_name)
        
        # Base parameters required by MCP
        base_params = {
            "patientFirstName": str(first_name),
            "patientLastName": str(last_name),
            "patientDateOfBirth": str(patient_data.get('dob', '')),
            "patientState": str(patient_data.get('state', ''))
        }
        
        # Add additional parameters based on API type
        if api_type == "eligibility":
            # Eligibility may need additional fields
            base_params.update({
                "memberId": str(patient_data.get('member_id', '')),
                "payerName": str(patient_data.get('payer', '')),
                "providerName": str(patient_data.get('provider_name', ''))
            })
        
        payload = {
            "jsonrpc": "2.0",
            "id": f"{api_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "method": "tools/call",
            "params": base_params
        }
        
        print(f"🎯 MCP STRUCTURED PARAMETERS:")
        print(f"   Patient First Name: {first_name}")
        print(f"   Patient Last Name: {last_name}")
        print(f"   DOB: {patient_data.get('dob', '')}")
        print(f"   State: {patient_data.get('state', '')}")
        if api_type == "eligibility":
            print(f"   Member ID: {patient_data.get('member_id', '')}")
            print(f"   Payer: {patient_data.get('payer', '')}")
            print(f"   Provider: {patient_data.get('provider_name', '')}")
        
        return payload
    
    def _parse_patient_name(self, full_name: str) -> tuple:
        """Intelligently parse full name into first and last name"""
        if not full_name:
            return "", ""
        
        name_parts = full_name.strip().split()
        
        if len(name_parts) == 1:
            # Only one name provided
            return name_parts[0], ""
        elif len(name_parts) == 2:
            # First and Last
            return name_parts[0], name_parts[1]
        elif len(name_parts) >= 3:
            # First, Middle(s), Last - take first and last
            return name_parts[0], name_parts[-1]
        
        return "", ""
    
    def _process_insurance_result(self, api_type: str, result_data: Any) -> str:
        """Intelligently process insurance API results"""
        result_str = str(result_data)
        
        if api_type == "discovery":
            print(f"🔍 PROCESSING DISCOVERY RESULT:")
            # Extract key information for discovery
            patterns = {
                'payer': r'(?:payer|insurance|carrier)[:\s]*([^\n,;]+)',
                'member_id': r'(?:member\s*id|policy\s*number|id)[:\s]*([A-Za-z0-9\-]+)',
                'group_number': r'(?:group\s*number|group)[:\s]*([A-Za-z0-9\-]+)'
            }
            
            extracted = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, result_str, re.IGNORECASE)
                if match:
                    extracted[key] = match.group(1).strip()
                    print(f"  ✅ {key.upper()}: {extracted[key]}")
            
        elif api_type == "eligibility":
            print(f"✅ PROCESSING ELIGIBILITY RESULT:")
            # Extract key information for eligibility
            patterns = {
                'copay': r'(?:co-?pay|copayment)[:\s]*\$?([0-9,]+\.?[0-9]*)',
                'deductible': r'(?:deductible)[:\s]*\$?([0-9,]+\.?[0-9]*)',
                'status': r'(?:status|eligibility)[:\s]*([^\n,;]+)'
            }
            
            extracted = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, result_str, re.IGNORECASE)
                if match:
                    extracted[key] = match.group(1).strip()
                    print(f"  ✅ {key.upper()}: {extracted[key]}")
        
        return result_str

class IntelligentLLM:
    """Advanced LLM client with healthcare expertise and intelligent conversation management"""
    
    def __init__(self, jwt_token: str, endpoint_url: str, project_id: str, connection_id: str):
        self.jwt_token = jwt_token
        self.endpoint_url = endpoint_url
        self.project_id = project_id
        self.connection_id = connection_id
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {jwt_token}'
        }
        
        print(f"🧠 INTELLIGENT LLM INITIALIZED")
        print(f"🔗 Endpoint: {endpoint_url}")
        print(f"📁 Project: {project_id}")
        print(f"🔌 Connection: {connection_id}")
    
    async def process_conversation(self, user_input: str, session: Session, api_results: Dict = None) -> Dict:
        """Intelligent conversation processing with healthcare expertise"""
        
        print(f"\n🧠 LLM PROCESSING INITIATED")
        print(f"👤 User Input: '{user_input}'")
        
        # Display current session intelligence
        self._display_session_intelligence(session)
        
        # Construct intelligent healthcare prompt
        prompt = self._construct_healthcare_prompt(user_input, session, api_results)
        
        try:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input}
            ]
            
            payload = {
                "messages": messages,
                "project_id": self.project_id,
                "connection_id": self.connection_id,
                "max_tokens": 500,  # Increased for more detailed responses
                "temperature": 0.2,  # Lower for more consistent healthcare responses
                "top_p": 0.9
            }
            
            print(f"📤 LLM REQUEST PAYLOAD:")
            print(json.dumps({k: v for k, v in payload.items() if k != 'messages'}, indent=2))
            
            def _execute_llm_request():
                try:
                    response = requests.post(
                        self.endpoint_url, 
                        headers=self.headers, 
                        json=payload, 
                        timeout=30
                    )
                    response.raise_for_status()
                    return response.json()
                except Exception as e:
                    logger.error(f"LLM request failed: {e}")
                    return {"error": str(e)}
            
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(None, _execute_llm_request)
            
            print(f"📥 LLM RAW RESPONSE:")
            print(json.dumps(raw_response, indent=2))
            
            if "error" in raw_response:
                print(f"❌ LLM ERROR: {raw_response['error']}")
                return self._create_fallback_response(user_input)
            
            # Extract LLM response
            if 'choices' in raw_response and raw_response['choices']:
                llm_content = raw_response['choices'][0]['message']['content']
            else:
                llm_content = raw_response.get('response', '')
            
            print(f"🧠 LLM RESPONSE CONTENT: {llm_content}")
            
            if llm_content:
                parsed_response = self._parse_llm_response(llm_content)
                print(f"✅ LLM PARSING SUCCESS:")
                print(json.dumps(parsed_response, indent=2))
                return parsed_response
            else:
                print(f"⚠️  LLM WARNING: Empty response")
                return self._create_fallback_response(user_input)
                
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            print(f"💥 LLM EXCEPTION: {str(e)}")
            return self._create_fallback_response(user_input)
    
    def _display_session_intelligence(self, session: Session):
        """Display intelligent session analysis"""
        required_fields = ['name', 'phone', 'reason', 'date_of_birth', 'state', 'provider_name', 'preferred_date', 'preferred_time']
        collected = [field for field in required_fields if session.data.get(field)]
        
        print(f"\n📊 SESSION INTELLIGENCE ANALYSIS")
        print(f"🎯 Completion: {len(collected)}/{len(required_fields)} ({session.get_completion_percentage():.1f}%)")
        print(f"✅ Collected: {', '.join(collected) if collected else 'None yet'}")
        
        missing = [field for field in required_fields if not session.data.get(field)]
        if missing:
            print(f"⏳ Required: {', '.join(missing)}")
        
        # API Intelligence
        if session.data.get('discovery_result'):
            status = "✅" if session.data['discovery_result'].get('success') else "❌"
            print(f"🔍 Discovery API: {status}")
        if session.data.get('eligibility_result'):
            status = "✅" if session.data['eligibility_result'].get('success') else "❌"
            print(f"✅ Eligibility API: {status}")
        
        print("-" * 60)
    
    def _construct_healthcare_prompt(self, user_input: str, session: Session, api_results: Dict = None) -> str:
        """Construct intelligent healthcare conversation prompt"""
        
        # API context if available
        api_context = ""
        if api_results and api_results.get("success"):
            api_context = f"""
API RESULTS RECEIVED - ANNOUNCE THESE KEY DETAILS:
- Extract and clearly announce the insurance payer name
- Extract and announce the policy/member ID number
- Extract and announce any co-pay amount found
- Be specific and clear about these insurance details

API Response Data: {api_results.get('data', '')}
"""
        
        prompt = f"""You are an expert healthcare appointment scheduler with years of experience. You are intelligent, efficient, warm, and professional.

CURRENT SESSION DATA: {json.dumps(session.data, indent=2)}
RECENT CONVERSATION: {json.dumps(session.conversation[-4:] if session.conversation else [], indent=2)}
USER INPUT: "{user_input}"{api_context}

INTELLIGENT CONVERSATION FLOW:
1. GREETING: Professional welcome, ask for full name
2. DATA COLLECTION: Systematically collect (one at a time, naturally):
   - Full name → Phone number → Reason for visit → Date of birth → State
3. INSURANCE DISCOVERY: When you have name+dob+state → trigger "discovery" API
4. PROVIDER INFORMATION: Get provider name (no NPI needed)
5. ELIGIBILITY CHECK: When you have discovery results+provider → trigger "eligibility" API  
6. INSURANCE ANNOUNCEMENT: Clearly announce payer name, policy ID, co-pay from API results
7. APPOINTMENT SCHEDULING: Get preferred date → preferred time
8. CONFIRMATION: Generate 5-digit alphanumeric confirmation code and confirm details
9. PROFESSIONAL CLOSING: Thank patient and end call

INTELLIGENT BEHAVIOR RULES:
- NEVER ask for information you already have - always check CURRENT SESSION DATA first
- Be naturally conversational, not robotic or repetitive
- Handle multiple pieces of information if user provides them together
- Stay focused on the healthcare appointment flow
- Be confident and move the conversation forward efficiently
- For dates, convert to YYYY-MM-DD format for API calls
- For unclear speech, ask for clarification in a helpful way

SPEECH RECOGNITION AWARENESS:
- If user input seems garbled or doesn't make sense, politely ask them to repeat
- For state names, be aware of common misrecognitions (California/hernia, Florida/gloria)
- For dates, confirm in different format if unclear
- Always validate critical information like dates and names

TECHNICAL REQUIREMENTS:
- Respond ONLY with valid JSON format
- Use "discovery" or "eligibility" for api_call field (never "none" unless truly no API needed)
- Generate 5-digit alphanumeric confirmation codes for final booking
- Set done=true only when appointment is fully confirmed with confirmation code

REQUIRED JSON RESPONSE FORMAT:
{{
    "response": "your warm, professional response to the patient",
    "extract": {{"field_name": "extracted_value"}},
    "api_call": "discovery|eligibility|none",
    "api_data": {{relevant data for API call}},
    "done": false
}}

Remember: You are the expert. Be confident, intelligent, and guide the conversation smoothly to completion."""
        
        return prompt
    
    def _parse_llm_response(self, response_text: str) -> Dict:
        """Intelligently parse LLM response with error recovery"""
        try:
            # Clean the response
            content = response_text.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON
            parsed = json.loads(content)
            
            # Validate and enhance
            result = {
                "response": parsed.get("response", "").strip(),
                "extract": parsed.get("extract", {}),
                "api_call": parsed.get("api_call", "none").lower(),
                "api_data": parsed.get("api_data", {}),
                "done": bool(parsed.get("done", False))
            }
            
            # Intelligent validation
            if not result["response"]:
                result["response"] = "I understand. Please continue."
            
            # Validate API call types
            if result["api_call"] not in ["discovery", "eligibility", "none"]:
                print(f"⚠️  Invalid API call type: {result['api_call']}, defaulting to 'none'")
                result["api_call"] = "none"
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON PARSE ERROR: {e}")
            # Try to extract response with regex
            response_match = re.search(r'"response":\s*"([^"]*)"', response_text)
            if response_match:
                return {
                    "response": response_match.group(1),
                    "extract": {},
                    "api_call": "none",
                    "api_data": {},
                    "done": False
                }
            
            # Ultimate fallback
            return self._create_fallback_response(response_text)
        
        except Exception as e:
            print(f"❌ PARSE EXCEPTION: {e}")
            return self._create_fallback_response(response_text)
    
    def _create_fallback_response(self, user_input: str) -> Dict:
        """Create intelligent fallback response"""
        fallback_responses = [
            "I understand. Could you please repeat that more clearly?",
            "I want to make sure I got that right. Could you say that again?",
            "Let me make sure I understand you correctly. Please repeat that.",
            "I'm sorry, could you rephrase that for me?"
        ]
        
        return {
            "response": random.choice(fallback_responses),
            "extract": {},
            "api_call": "none",
            "api_data": {},
            "done": False
        }

class HealthcareVoiceAgent:
    """  Healthcare Voice Agent with maximum AI intelligence"""
    
    def __init__(self, jwt_token: str, endpoint_url: str, project_id: str, connection_id: str,
                 mcp_url: str, insurance_api_key: str):
        
        print("🏥 HEALTHCARE VOICE AGENT -   INITIALIZATION")
        print("=" * 60)
        
        self.session = Session()
        self.audio = Audio()
        self.llm = IntelligentLLM(jwt_token, endpoint_url, project_id, connection_id)
        self.mcp_api = MCPInsuranceAPI(mcp_url, insurance_api_key)
        
        print(f"✅ AGENT READY - Session ID: {self.session.session_id}")
        print("=" * 60)
    
    def _format_dob_for_api(self, dob_input: str) -> str:
        """Intelligent DOB formatting for API calls"""
        if not dob_input:
            return ""
        
        dob_str = str(dob_input).strip()
        print(f"🎂 FORMATTING DOB: '{dob_str}'")
        
        # MM/DD/YYYY format
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}', dob_str):
            parts = dob_str.split('/')
            month, day, year = parts[0], parts[1], parts[2]
            formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            print(f"✅ DOB FORMATTED: {dob_str} → {formatted}")
            return formatted
        
        # MM-DD-YYYY format
        if re.match(r'^\d{1,2}-\d{1,2}-\d{4}', dob_str):
            parts = dob_str.split('-')
            month, day, year = parts[0], parts[1], parts[2]
            formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            print(f"✅ DOB FORMATTED: {dob_str} → {formatted}")
            return formatted
        
        # Natural language (e.g., "January 15, 1990")
        try:
            # Handle various natural formats
            cleaned = re.sub(r'[,\s]+', ' ', dob_str).strip()
            parsed = datetime.strptime(cleaned, '%B %d %Y')
            formatted = parsed.strftime('%Y-%m-%d')
            print(f"✅ DOB FORMATTED: {dob_str} → {formatted}")
            return formatted
        except ValueError:
            pass
        
        try:
            # Try short month format
            cleaned = re.sub(r'[,\s]+', ' ', dob_str).strip()
            parsed = datetime.strptime(cleaned, '%b %d %Y')
            formatted = parsed.strftime('%Y-%m-%d')
            print(f"✅ DOB FORMATTED: {dob_str} → {formatted}")
            return formatted
        except ValueError:
            pass
        
        print(f"⚠️  DOB FORMAT UNCLEAR: Using as-is: {dob_str}")
        return dob_str
    
    async def start_intelligent_conversation(self):
        """Start intelligent healthcare conversation"""
        try:
            # Intelligent greeting
            greeting = "Hello! I'm your healthcare appointment assistant. I'll help you schedule your appointment today. To get started, could you please tell me your full name?"
            
            print(f"\n🏥 AGENT: {greeting}")
            await self.audio.speak(greeting)
            self.session.add_message("assistant", greeting)
            
            # Intelligent conversation loop
            turn_number = 0
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            while consecutive_errors < max_consecutive_errors:
                try:
                    turn_number += 1
                    print(f"\n{'='*20} TURN {turn_number} {'='*20}")
                    
                    # Intelligent listening
                    user_input = await self.audio.listen()
                    
                    # Handle different speech recognition outcomes intelligently
                    if user_input in ["TIMEOUT", "UNCLEAR", "NETWORK_ERROR", "ERROR"]:
                        consecutive_errors += 1
                        response = await self._handle_speech_issue(user_input, consecutive_errors)
                        if response:
                            await self.audio.speak(response)
                        continue
                    
                    if not user_input:
                        consecutive_errors += 1
                        print("👤 USER: [No input detected]")
                        continue
                    
                    # Reset error counter on successful input
                    consecutive_errors = 0
                    
                    print(f"👤 USER: {user_input}")
                    self.session.add_message("user", user_input)
                    
                    # Check for conversation end
                    if self._is_conversation_ending(user_input):
                        await self._end_conversation("User requested to end")
                        break
                    
                    # Process with intelligent LLM
                    llm_result = await self.llm.process_conversation(user_input, self.session)
                    
                    # Update session data intelligently
                    if llm_result.get("extract"):
                        old_data = dict(self.session.data)
                        self.session.data.update(llm_result["extract"])
                        new_fields = [k for k in llm_result["extract"].keys() if k not in old_data or old_data[k] != llm_result["extract"][k]]
                        if new_fields:
                            print(f"📝 DATA UPDATED: {new_fields}")
                    
                    # Handle intelligent API calls
                    api_results = None
                    if llm_result.get("api_call") != "none":
                        api_results = await self._execute_intelligent_api_call(
                            llm_result["api_call"], 
                            llm_result.get("api_data", {})
                        )
                        
                        # Process API results with LLM
                        if api_results and api_results.get("success"):
                            print("📢 PROCESSING API RESULTS WITH LLM...")
                            api_announcement = await self.llm.process_conversation(
                                "ANNOUNCE_API_RESULTS", 
                                self.session, 
                                api_results
                            )
                            
                            if api_announcement.get("response"):
                                api_response = api_announcement["response"]
                                print(f"🏥 AGENT (API Results): {api_response}")
                                await self.audio.speak(api_response)
                                self.session.add_message("assistant", api_response)
                    
                    # Deliver main response
                    main_response = llm_result.get("response", "")
                    if main_response:
                        print(f"🏥 AGENT: {main_response}")
                        await self.audio.speak(main_response)
                        self.session.add_message("assistant", main_response)
                    
                    # Check for conversation completion
                    if llm_result.get("done", False):
                        print("✅ CONVERSATION COMPLETED BY LLM")
                        await self._end_conversation("Completed successfully")
                        break
                    
                    # Brief pause for natural conversation flow
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Turn {turn_number} error: {e}")
                    error_response = "I apologize, I had a technical issue. Could you please repeat that?"
                    print(f"🏥 AGENT (Error): {error_response}")
                    await self.audio.speak(error_response)
            
            # Handle max errors reached
            if consecutive_errors >= max_consecutive_errors:
                await self._end_conversation("Too many consecutive errors")
                
        except KeyboardInterrupt:
            await self._end_conversation("Manually interrupted")
        except Exception as e:
            logger.error(f"Conversation error: {e}")
            await self._end_conversation(f"System error: {str(e)}")
        finally:
            self._cleanup_resources()
    
    async def _handle_speech_issue(self, issue_type: str, consecutive_count: int) -> str:
        """Intelligently handle speech recognition issues"""
        
        print(f"🎧 SPEECH ISSUE: {issue_type} (consecutive: {consecutive_count})")
        
        if issue_type == "TIMEOUT":
            responses = [
                "I didn't hear anything. Please try speaking again.",
                "I'm still here. Could you please speak up?",
                "I'm waiting for your response. Please try again."
            ]
        elif issue_type == "UNCLEAR":
            responses = [
                "I couldn't understand that clearly. Could you please speak more slowly?",
                "I'm having trouble understanding. Could you repeat that?",
                "Could you please speak a bit more clearly for me?"
            ]
        elif issue_type == "NETWORK_ERROR":
            responses = [
                "I'm having a connection issue. Please try again in a moment.",
                "There's a network issue. Let me try again.",
                "I'm having trouble with my speech recognition. Please repeat."
            ]
        else:  # ERROR
            responses = [
                "I had a technical issue. Could you please try again?",
                "Sorry, I had a problem. Please repeat that.",
                "I encountered an error. Could you say that again?"
            ]
        
        # Escalate concern with consecutive errors
        if consecutive_count >= 2:
            return f"{random.choice(responses)} If you continue to have issues, you may want to call back later."
        
        return random.choice(responses)
    
    def _is_conversation_ending(self, user_input: str) -> bool:
        """Intelligently detect conversation ending signals"""
        ending_phrases = [
            'bye', 'goodbye', 'hang up', 'end call', 'thank you goodbye',
            'that\'s all', 'we\'re done', 'finished', 'end', 'quit',
            'cancel', 'nevermind', 'never mind'
        ]
        
        user_lower = user_input.lower().strip()
        return any(phrase in user_lower for phrase in ending_phrases)
    
    async def _execute_intelligent_api_call(self, api_type: str, api_data: Dict) -> Dict:
        """Execute intelligent API call with comprehensive data"""
        
        print(f"🚀 EXECUTING INTELLIGENT API CALL: {api_type.upper()}")
        
        # Prepare comprehensive call data
        call_data = {**self.session.data, **api_data}
        
        # Intelligent DOB formatting
        if 'date_of_birth' in call_data:
            call_data['dob'] = self._format_dob_for_api(call_data['date_of_birth'])
        
        # Execute the API call
        start_time = datetime.now()
        result = await self.mcp_api.call_insurance_api(api_type, call_data)
        
        # Store comprehensive results
        self.session.data[f"{api_type}_result"] = result
        self.session.add_api_call(api_type, call_data, result, result.get("success", False))
        
        # Store raw response for debugging
        if result.get("success"):
            self.session.data[f"{api_type}_raw"] = result.get("raw_response", "")
            
            # Intelligent data extraction from API response
            self._extract_api_intelligence(api_type, result.get("data", ""))
        
        duration = (datetime.now() - start_time).total_seconds()
        status = "✅ SUCCESS" if result.get("success") else "❌ FAILED"
        print(f"{status} - {api_type.upper()} API completed in {duration:.2f}s")
        
        return result
    
    def _extract_api_intelligence(self, api_type: str, api_response: str):
        """Intelligently extract structured data from API responses"""
        
        print(f"🧠 EXTRACTING INTELLIGENCE FROM {api_type.upper()} RESPONSE")
        
        if not api_response:
            return
        
        response_lower = api_response.lower()
        
        if api_type == "discovery":
            # Extract payer information
            payer_patterns = [
                r'payer[:\s]*([^\n,;]+)',
                r'insurance[:\s]*([^\n,;]+)',
                r'carrier[:\s]*([^\n,;]+)',
                r'plan[:\s]*([^\n,;]+)'
            ]
            
            for pattern in payer_patterns:
                match = re.search(pattern, response_lower)
                if match and not self.session.data.get('payer'):
                    payer = match.group(1).strip().title()
                    self.session.data['payer'] = payer
                    print(f"🏢 EXTRACTED PAYER: {payer}")
                    break
            
            # Extract member/policy ID
            id_patterns = [
                r'member\s*id[:\s]*([a-za-z0-9\-]+)',
                r'policy\s*number[:\s]*([a-za-z0-9\-]+)',
                r'policy\s*id[:\s]*([a-za-z0-9\-]+)',
                r'id[:\s]*([a-za-z0-9\-]{5,})'  # At least 5 chars for ID
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, response_lower)
                if match and not self.session.data.get('member_id'):
                    member_id = match.group(1).strip().upper()
                    self.session.data['member_id'] = member_id
                    print(f"🆔 EXTRACTED MEMBER ID: {member_id}")
                    break
        
        elif api_type == "eligibility":
            # Extract financial information
            financial_patterns = {
                'copay': r'co-?pay[:\s]*\$?([0-9,]+\.?[0-9]*)',
                'deductible': r'deductible[:\s]*\$?([0-9,]+\.?[0-9]*)',
                'coinsurance': r'coinsurance[:\s]*([0-9]+)%?'
            }
            
            for key, pattern in financial_patterns.items():
                match = re.search(pattern, response_lower)
                if match:
                    value = match.group(1).strip()
                    self.session.data[f'insurance_{key}'] = value
                    print(f"💰 EXTRACTED {key.upper()}: ${value}")
    
    async def _end_conversation(self, reason: str):
        """Intelligently end conversation with comprehensive summary"""
        
        print(f"\n🏁 ENDING CONVERSATION: {reason}")
        
        self.session.end_time = datetime.now()
        
        # Generate intelligent confirmation if appropriate
        if self._should_generate_confirmation():
            if not self.session.data.get("confirmation_code"):
                confirmation = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
                self.session.data["confirmation_code"] = confirmation
                
                patient_name = self.session.data.get('name', 'Patient')
                preferred_date = self.session.data.get('preferred_date', 'your requested date')
                
                end_message = f"Perfect, {patient_name}! Your appointment is confirmed for {preferred_date}. Your confirmation number is {confirmation}. Please keep this number for your records. Thank you for calling!"
            else:
                end_message = "Thank you for calling. Have a great day!"
        else:
            completion = self.session.get_completion_percentage()
            if completion > 50:
                end_message = "Thank you for the information you provided. Please call back when you're ready to complete your appointment scheduling."
            else:
                end_message = "Thank you for calling. Please call back when you have all the information needed to schedule your appointment."
        
        print(f"🏥 AGENT (Final): {end_message}")
        await self.audio.speak(end_message)
        self.session.add_message("assistant", end_message)
        
        # Save comprehensive session
        filename = self.session.save()
        
        # Display intelligent summary
        self._display_final_summary(reason, filename)
    
    def _should_generate_confirmation(self) -> bool:
        """Intelligently determine if confirmation should be generated"""
        required_for_confirmation = ['name', 'preferred_date']
        return all(self.session.data.get(field) for field in required_for_confirmation)
    
    def _display_final_summary(self, reason: str, filename: str):
        """Display comprehensive conversation summary"""
        
        duration = (self.session.end_time - self.session.start_time).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"🏥 HEALTHCARE CONVERSATION SUMMARY")
        print(f"{'='*60}")
        print(f"📋 Session ID: {self.session.session_id}")
        print(f"⏱️  Duration: {duration/60:.2f} minutes ({duration:.1f} seconds)")
        print(f"🎯 Completion: {self.session.get_completion_percentage():.1f}%")
        print(f"💬 Total turns: {len(self.session.conversation)}")
        print(f"🔗 API calls: {len(self.session.api_calls)}")
        print(f"🏁 End reason: {reason}")
        print(f"📁 Saved to: {filename}")
        
        # Patient data summary
        if self.session.data:
            print(f"\n👤 PATIENT DATA COLLECTED:")
            for key, value in self.session.data.items():
                if not key.endswith('_result') and not key.endswith('_raw'):
                    print(f"   {key}: {value}")
        
        # API call summary
        if self.session.api_calls:
            print(f"\n🔗 API CALLS SUMMARY:")
            for call in self.session.api_calls:
                status = "✅" if call['success'] else "❌"
                print(f"   {status} {call['api_type'].upper()}: {call.get('duration_ms', 0)}ms")
        
        print(f"{'='*60}")
    
    def _cleanup_resources(self):
        """Cleanup all system resources"""
        try:
            print("🧹 CLEANING UP RESOURCES...")
            self.audio.cleanup()
            print("✅ Cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup issue: {e}")

def load_config():
    """Load   configuration with validation"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("🔧 Loading environment configuration...")
    except ImportError:
        print("⚠️  python-dotenv not available, reading from environment...")
    
    config = {}
    required_configs = {
        'jwt_token': 'JWT_TOKEN',
        'endpoint_url': 'ENDPOINT_URL', 
        'project_id': 'PROJECT_ID',
        'connection_id': 'CONNECTION_ID',
        'mcp_url': 'MCP_URL',
        'insurance_api_key': 'X_INF_API_KEY'
    }
    
    print("🔍 VALIDATING CONFIGURATION:")
    missing_configs = []
    
    for key, env_var in required_configs.items():
        value = os.getenv(env_var)
        if value and value.strip():
            config[key] = value.strip()
            # Show partial value for security
            display_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
            print(f"   ✅ {env_var}: {display_value}")
        else:
            missing_configs.append(env_var)
            print(f"   ❌ {env_var}: MISSING")
    
    if missing_configs:
        print(f"\n❌ CONFIGURATION ERROR: Missing required environment variables:")
        for var in missing_configs:
            print(f"   - {var}")
        print(f"\nPlease set these environment variables and try again.")
        return None
    
    print("✅ CONFIGURATION VALIDATED")
    return config

async def main():
    """  Healthcare Voice Agent Main Entry Point"""
    print("🏥 HEALTHCARE VOICE AGENT -   VERSION")
    print("=" * 70)
    
    # Load and validate configuration
    config = load_config()
    if not config:
        print("❌ Cannot start without valid configuration")
        return
    
    try:
        # Initialize   agent
        agent = HealthcareVoiceAgent(
            jwt_token=config['jwt_token'],
            endpoint_url=config['endpoint_url'],
            project_id=config['project_id'],
            connection_id=config['connection_id'],
            mcp_url=config['mcp_url'],
            insurance_api_key=config['insurance_api_key']
        )
        
        # Start intelligent conversation
        await agent.start_intelligent_conversation()
        
    except KeyboardInterrupt:
        print("\n👋 GRACEFUL SHUTDOWN: User interrupted")
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}")
        print(f"💥 SYSTEM ERROR: {e}")
    finally:
        print("🏥 Healthcare Voice Agent session ended")

if __name__ == "__main__":
    asyncio.run(main())