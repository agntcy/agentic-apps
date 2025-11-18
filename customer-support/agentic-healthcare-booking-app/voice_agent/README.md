# Healthcare Voice + A2A + MCP Agent

A voice-enabled healthcare appointment scheduling agent that integrates Agent-to-Agent (A2A) protocol for medical triage, Model Context Protocol (MCP) for insurance verification, and a conversational AI system for natural patient interactions.

## Overview

This system provides an end-to-end voice-based healthcare appointment scheduling experience with:

- **Voice Interface**: Natural speech recognition and text-to-speech responses
- **Medical Triage**: Integrated A2A protocol for structured health assessments
- **Insurance Integration**: MCP-based discovery and eligibility verification
- **Session Management**: Complete conversation logging and state management
- **Multi-Protocol Architecture**: Seamless integration of A2A, MCP, and LLM services

## Features

### Voice Interaction
- Real-time speech recognition using Google Speech API
- Text-to-speech responses with gTTS and pygame
- Automatic ambient noise adjustment
- Fallback to text-based console mode

### Medical Triage (A2A Protocol)
- Agent-to-agent communication for structured health assessments
- Dynamic question flow based on patient responses
- Task state management (submitted, working, input-required, completed)
- Structured result extraction with urgency levels and specialist recommendations

### Insurance Services (MCP Protocol)
- **Discovery**: Locate patient insurance using demographics
- **Eligibility**: Verify benefits and copays
- Automatic payer and policy ID extraction
- Support for multiple insurance data formats

### Conversation Flow
1. Patient identification (name, phone)
2. Reason for visit assessment
3. Medical triage (if symptoms reported)
4. Insurance discovery (DOB, state)
5. Provider selection
6. Benefits eligibility verification
7. Appointment scheduling with confirmation

### Session Management
- Comprehensive conversation logging
- Real-time data extraction and validation
- Session persistence to JSON files
- Interaction timestamps and state snapshots

## Installation

### Prerequisites

- Python 3.8+
- Microphone for voice input 
- Audio output device for TTS

### Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
```
requests
python-dotenv
SpeechRecognition
pygame
gTTS
pyaudio  # Required for microphone input
```

### Audio Setup

**macOS/Linux:**
```bash
# Install PortAudio for microphone support
brew install portaudio  # macOS
sudo apt-get install portaudio19-dev  # Ubuntu/Debian
```

## Configuration

Create a `.env` file in the project root:

```env
# LLM Configuration (JWT-based endpoint)
JWT_TOKEN=your_jwt_token_here
ENDPOINT_URL=https://your-llm-endpoint.com/v1/chat/completions
PROJECT_ID=your_project_id
CONNECTION_ID=your_connection_id

# Insurance MCP Server
MCP_URL=https://your-mcp-server.com/mcp
X_INF_API_KEY=your_insurance_api_key

# A2A Triage Service
A2A_SERVICE_URL=http://localhost:8887
A2A_MESSAGE_URL=http://localhost:8887
A2A_API_KEY=your_a2a_api_key
```

### Configuration Details

**LLM Service**: JWT-authenticated endpoint for conversation management and intent extraction

**MCP Server**: Insurance verification service supporting:
- `insurance_discovery`: Find insurance by patient demographics
- `benefits_eligibility`: Verify coverage and copays

**A2A Service**: Medical triage agent service implementing the A2A protocol specification

## Usage

### Voice Mode

The agent will automatically use voice if audio dependencies are installed:

```
Agent: Hello! I'm your healthcare appointment assistant...
Listening...
You: [speak your response]
```

### Console Mode

If audio is unavailable, the system falls back to text input:

```
Agent: Hello! I'm your healthcare appointment assistant...
You: John Smith
```

### Ending a Session

Say or type any of:
- "bye"
- "goodbye"
- "end"
- "quit"

## API Integration Details

### A2A Protocol Implementation

The agent implements the Agent-to-Agent Communication Protocol for medical triage:

**Message Format:**
```json
{
  "jsonrpc": "2.0",
  "id": "unique-id",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "patient response"}],
      "taskId": "task-id",
      "contextId": "context-id"
    },
    "configuration": {
      "acceptedOutputModes": ["text/plain", "application/json"],
      "blocking": true
    }
  }
}
```

**Task States:**
- `submitted`: Initial task creation
- `working`: Agent processing
- `input-required`: Waiting for patient response
- `completed`: Triage finished with results
- `failed`: Error occurred
- `canceled`: Task terminated

### MCP Insurance Tools

**Discovery Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "insurance_discovery",
    "arguments": {
      "patientDateOfBirth": "1990-01-15",
      "patientFirstName": "John",
      "patientLastName": "Smith",
      "patientState": "California"
    }
  }
}
```

**Eligibility Tool:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "benefits_eligibility",
    "arguments": {
      "patientFirstName": "John",
      "patientLastName": "Smith",
      "patientDateOfBirth": "1990-01-15",
      "subscriberId": "ABC123456",
      "payerName": "Blue Cross",
      "providerFirstName": "Jane",
      "providerLastName": "Doe",
      "providerNpi": "1234567890"
    }
  }
}
```

## Session Logs

Sessions are automatically saved to `sessions/` directory:

**File Format:** `session_YYYYMMDD_HHMMSS_{session_id}.json`

**Contents:**
```json
{
  "session_id": "abc12345",
  "start_time": "2025-10-01T10:00:00",
  "end_time": "2025-10-01T10:15:00",
  "duration_minutes": 15.0,
  "final_data": {
    "name": "John Smith",
    "phone": "555-1234",
    "reason": "headache",
    "date_of_birth": "01/15/1990",
    "state": "California",
    "payer": "Blue Cross",
    "member_id": "ABC123456",
    "provider_name": "Dr. Jane Doe"
  },
  "triage_complete": true,
  "triage_results": {
    "urgency_level": "standard",
    "doctor_type": "neurologist"
  },
  "conversation_log": [...]
}
```

## Error Handling

### Audio Failures
- Automatic fallback to console mode
- Retry logic for unclear speech (max 3 consecutive errors)
- Timeout handling for silent periods

### API Failures
- Graceful degradation if insurance lookup fails
- Fallback responses if triage service unavailable
- Request timeout limits (30-60 seconds)

### Session Recovery
- State preservation across errors
- Conversation log maintained through failures
- Automatic session saving on completion or error

## Development

### Key Classes

- `HealthcareAgent`: Main orchestrator
- `AudioSystem`: Voice I/O management
- `A2AClient`: A2A protocol implementation
- `InsuranceClient`: MCP insurance integration
- `LLMClient`: Conversation AI client
- `Session`: State and logging management

### Extending the Agent

**Add New Data Fields:**
```python
# In LLM prompt, add extraction rule:
"Extract field_name as 'field_name'"

# In session data handling:
if result.get("extract"):
    self.session.data['field_name'] = result['extract']['field_name']
```

**Add New MCP Tools:**
```python
async def call_new_tool(self, **kwargs):
    payload = {
        "method": "tools/call",
        "params": {
            "name": "new_tool_name",
            "arguments": kwargs
        }
    }
    response = await self._make_request(payload)
    return self._parse_response(response)
```

## Troubleshooting

### Audio Issues

**Problem**: `No module named 'pyaudio'`
```bash
# Install platform-specific dependencies first
pip install pyaudio
```

**Problem**: Microphone not detected
```bash
# Test microphone access
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
```

### API Connection Issues

**Problem**: A2A discovery fails
- Verify `A2A_SERVICE_URL` is accessible
- Check if agent-card.json endpoint exists
- Confirm `A2A_API_KEY` is correct

**Problem**: Insurance lookup returns no results
- Verify date format: MM/DD/YYYY or YYYY-MM-DD
- Check state name capitalization
- Ensure MCP server is running

### LLM Issues

**Problem**: JSON parsing errors
- LLM may return malformed JSON
- Check `temperature` setting (lower = more consistent)
- Verify prompt includes clear JSON structure

## Performance Notes

- **Speech Recognition Latency**: 1-3 seconds per utterance
- **TTS Generation**: 500ms - 2 seconds depending on text length
- **A2A Triage**: 5-10 seconds per question
- **Insurance Lookup**: 3-10 seconds per API call
- **Total Session Duration**: Typically 5-15 minutes

## Security Considerations

- API keys stored in `.env` (never commit)
- JWT tokens expire and require rotation
- Patient data stored locally in session files
