# Healthcare Voice Agent with MCP Insurance API - Technical Documentation

## Overview
The Healthcare Voice Agent is an AI-powered voice-based system for automating healthcare appointment scheduling. It combines speech recognition, natural language processing, and insurance verification APIs to create an intelligent conversational interface for patients scheduling medical appointments.

## System Architecture
### Core Components
#### 1. Session Management (Session class)
Manages conversation state and data persistence throughout the appointment scheduling process.

**Key Features:**
- Unique session ID generation using UUID
- Conversation history tracking with timestamps
- API call logging with success/failure metrics
- Completion percentage calculation
- Comprehensive session data export to JSON

**Data Tracked:**
- Patient demographics (name, DOB, phone, state)
- Insurance information (payer, member ID, policy details)
- Appointment preferences (date, time, provider)
- Conversation turns with role-based messaging
- API call metadata (request, response, duration)

#### 2. Audio Processing (Audio class)
Handles all speech recognition and text-to-speech operations.

**Speech Recognition:**
- Google Speech Recognition API integration
- Dynamic ambient noise calibration
- Configurable energy thresholds (default: 300)
- Timeout handling (15 seconds)
- Multi-attempt recognition with fallback strategies

**Text-to-Speech:**
- Primary: Google TTS (gTTS) with high-quality audio
- Fallback: pyttsx3 for offline capability
- Speech rate optimization (165 WPM for healthcare)
- Voice gender preference
- Intelligent number-to-digit conversion

**Audio Configuration:**
python
- pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
- recognizer.energy_threshold = 300
- recognizer.pause_threshold = 0.8
- recognizer.phrase_time_limit = 10
  
#### 3. MCP Insurance API Client (MCPInsuranceAPI class)
Interfaces with insurance verification services using JSON-RPC 2.0 protocol.

**Supported Operations:**
- **Discovery API:** Identifies patient's insurance payer and policy information
- **Eligibility API:** Verifies coverage and extracts co-pay/deductible details

**API Payload Structure:**\
json{\
  "jsonrpc": "2.0",\
  "id": "discovery_20250930_143022",\
  "method": "tools/call",\
  "params": {\
    "patientFirstName": "John",\
    "patientLastName": "Doe",\
    "patientDateOfBirth": "1990-01-15",\
    "patientState": "California"\
  }\
}

**Response Processing:**
- Automatic data extraction using regex patterns
- Structured information parsing (payer names, member IDs, financial details)
- Error handling with detailed logging
- Duration tracking for performance monitoring

#### 4. LLM Integration (IntelligentLLM class)
Manages conversation flow using a language model API.

**Configuration:**\
python\
{\
  "max_tokens": 500,\
  "temperature": 0.2,  # Low for consistent healthcare responses\
  "top_p": 0.9\
}

**Prompt Engineering:**
- Healthcare-specific conversation flow guidance
- Session state awareness
- API result interpretation instructions
- JSON-structured response requirements

**Response Format:**\
json{\
  "response": "Natural language response to patient",\
  "extract": {"field_name": "extracted_value"},\
  "api_call": "discovery|eligibility|none",\
  "api_data": {"relevant": "data"},\
  "done": false\
}

#### 5. Main Agent (HealthcareVoiceAgent class)
Orchestrates all components to manage the complete conversation lifecycle.

**Conversation Flow**
Standard Appointment Scheduling Sequence

**Greeting:** Welcome message and request for patient name

**Demographics Collection:**\
  - Full name
  - Phone number
  - Reason for visit
  - Date of birth
  - State of residence

**Insurance Discovery:** Trigger API when name + DOB + state available\
**Provider Information:** Collect provider name\
**Eligibility Check:** Verify coverage with provider details\
**Insurance Announcement:** Present payer, policy ID, co-pay information\
**Appointment Scheduling:** Get preferred date and time\
**Confirmation:** Generate 5-digit alphanumeric code\
**Closing:** Thank patient and end call

**Data Flow Diagram**
User Speech → Audio.listen() → Speech Recognition\
                                      ↓\
LLM Processing ← Session Data ← Transcribed Text\
      ↓\
Decision: API Call Needed?\
      ↓\
  Yes → MCP API Call → Store Results → LLM Announcement\
      ↓\
  No → Direct Response\
      ↓\
Audio.speak() → TTS → Patient Hears Response

**Configuration Requirements**\
Environment Variables\
Create a .env file with the following variables:  \
bash  \
LLM API Configuration  \
JWT_TOKEN=your_jwt_token_here  \
ENDPOINT_URL=https://your-llm-endpoint.com \
PROJECT_ID=your_project_id  \
CONNECTION_ID=your_connection_id  

Insurance API Configuration  
MCP_URL=https://your-mcp-server.com \
X_INF_API_KEY=your_insurance_api_key  

**Python Dependencies**\
bash  \
pip install requests  \
pip install SpeechRecognition  \
pip install gTTS  \
pip install pygame  \
pip install pyttsx3  \ 
pip install python-dotenv  

**System Requirements**  
- Operating System: Windows, macOS, or Linux  
- Python: 3.8 or higher  
- Microphone: Required for speech input  
- Audio Output: Required for TTS playback  
- Internet: Required for speech recognition and API calls  

**Error Handling**
**Speech Recognition Errors**
| Error Type | Handling Strategy |  
| --- | --- |
| TIMEOUT | Request patient to speak again |
| UNCLEAR | Ask for slower, clearer speech |
| NETWORK_ERROR | Retry with network issue notification |
| ERROR | Generic error handling with retry |

**Consecutive Error Management:**
- Maximum 3 consecutive errors before escalation
- Progressive response messaging
- Graceful conversation termination if threshold exceeded

**API Error Handling**
- Timeout: 45-second timeout with timeout-specific messaging
- Connection Errors: Network failure detection and logging
- HTTP Errors: Status code extraction and error reporting
- Malformed Responses: Validation and fallback processing

**LLM Error Handling**
- JSON Parse Errors: Regex-based extraction fallback
- Empty Responses: Intelligent fallback message generation
- Invalid API Call Types: Validation and default to "none"

**Data Formats**
- Date of Birth Formatting
  The system automatically converts various DOB formats to YYYY-MM-DD:  \
  MM/DD/YYYY → YYYY-MM-DD  \
  MM-DD-YYYY → YYYY-MM-DD

- Confirmation Code  
  Format: 5-character alphanumeric (e.g., A3X9K)  
  
#### Run the agent
asyncio.run(main())

**Programmatic Integration**\
python\
from healthcare_voice_agent import HealthcareVoiceAgent\

agent = HealthcareVoiceAgent(\
    jwt_token="your_token",\
    endpoint_url="your_endpoint",\
    project_id="your_project",\
    connection_id="your_connection",\
    mcp_url="your_mcp_url",\
    insurance_api_key="your_api_key"\
)

await agent.start_intelligent_conversation()

**Logging**\
Log Levels  \
- INFO: Standard operational messages
- WARNING: Non-critical issues (TTS fallback, cleanup issues)
- ERROR: API failures, speech recognition errors

Log Format\
2025-09-30 14:30:22 - module_name - LEVEL - message

**Console Output Features**
- Microphone status indicators
- LLM processing notifications
- API call initiation markers
- Success confirmations
- Error notifications
- Session completion statistics

**Security Considerations**
- API Key Protection: Partial display in logs (key[:8]...key[-4:])
- Session Data: Stored locally in JSON format
- Patient Privacy: All data stored locally, not transmitted except to configured APIs
- Audio Processing: Speech processed in real-time, no permanent audio storage

**Performance Optimization**\
Speech Recognition:
- Dynamic energy threshold adjustment
- Ambient noise calibration on startup
- Multi-attempt recognition strategy

API Calls:
- 45-second timeout to prevent hanging
- Async execution to prevent blocking
- Duration tracking for performance monitoring

TTS Optimization:
- Pygame mixer for low-latency audio
- Number-to-digit conversion for clarity
- Protected pattern recognition (times, measurements)

**Troubleshooting**  \
Common Issues  \
**Microphone not detected:**\
python # Check available microphones  \
import speech_recognition as sr  \
print(sr.Microphone.list_microphone_names())  

**TTS not working:**  \
Check pygame mixer initialization  \
Verify audio output device  \
Ensure no other applications blocking audio  

**API timeouts:**  \
Increase timeout values in call_insurance_api()  \
Check network connectivity  \
Verify API endpoint availability  

**LLM JSON parsing errors:**  \
Review prompt engineering  \
Check temperature settings (lower = more consistent)  \
Validate response format requirements  
