# A2A Medical Triage Service - Test Utilities

Test scripts and utilities for validating the A2A Medical Triage Service, including external API connectivity testing and TBAC (Task-Based Access Control) authorization testing.

## Overview

This repository contains two essential testing utilities:

1. **Triage API Connection Test** (`triage_util.py`) - Validates connectivity and flow with the external medical triage API
2. **TBAC Authorization Module** (`identity_client_util.py`) - Standalone TBAC implementation for testing bidirectional agent authorization

## Files

### 1. `triage_util.py`

A comprehensive test script that validates the entire triage API workflow from authentication through assessment completion.

### 2. `identity_client_util.py`

A standalone TBAC implementation for testing agent-to-agent authorization without running the full service.

## Triage API Connection Test

### Purpose

This script tests the complete medical triage API integration flow:
1. OAuth token acquisition
2. Survey creation with demographics
3. Message exchange with the triage AI
4. Conversation flow simulation
5. Summary retrieval

### Features

- **Complete Flow Testing**: Tests every step of the triage process
- **Detailed Output**: Color-coded status messages with clear success/failure indicators
- **Error Diagnostics**: Detailed error messages for troubleshooting
- **Two Test Modes**:
  - Full test flow (default)
  - Quick token-only test

### Usage

#### Full Test Flow
```bash
python triage_util.py
```

This runs the complete test sequence:
- Configuration validation
- Token acquisition
- Survey creation (with a sample test case)
- Initial symptom message
- Multi-turn conversation simulation
- Summary retrieval

#### Token-Only Test
```bash
python triage_util.py token
```

Quick test that only validates token acquisition - useful for checking credentials.

### Expected Output

Successful run shows:
```
============================================================
TRIAGE API CONNECTION TEST
============================================================
1. Checking configuration...
   ✅ App ID: abcd1234...
   ✅ Instance ID: inst-xyz
   ✅ Token URL: https://api.triage.example.com/oauth/token
   ✅ Base URL: https://api.triage.example.com/v1

2. Testing token acquisition...
   → POST https://api.triage.example.com/oauth/token
   ← Status: 200
   ✅ Token acquired: ey........
   ℹ️  Token expires in: 3600 seconds

3. Testing survey creation...
   → POST https://api.triage.example.com/v1/surveys
   → Demographics: 64yo female
   ← Status: 200
   ✅ Survey created: survey-uuid-12345

[... continued output ...]

✅ API CONNECTION TEST COMPLETED
============================================================
```

### Test Scenario

The default test simulates a diabetes symptom assessment:
- **Patient**: 33-year-old male
- **Symptoms**: Fatigue, excessive thirst, frequent urination, unexplained weight loss
- **Expected Flow**: Multiple follow-up questions about symptom severity and duration

### Configuration Requirements

Required environment variables:
```bash
TRIAGE_APP_ID=your_app_id
TRIAGE_APP_KEY=your_app_key
TRIAGE_INSTANCE_ID=your_instance_id
TRIAGE_TOKEN_URL=https://api.triage.example.com/oauth/token
TRIAGE_BASE_URL=https://api.triage.example.com/v1
```

## TBAC Authorization Module

### Purpose

Tests bidirectional Task-Based Access Control (TBAC) authorization between agents without running the full A2A service.

### Features

- **Bidirectional Authorization**: Tests both client-to-A2A and A2A-to-client authorization
- **Standalone Testing**: Can be run independently of the main service
- **Detailed Logging**: Step-by-step authorization process output
- **Graceful Degradation**: Works with missing credentials (bypasses TBAC)

### Authorization Flow

1. **Client → A2A Authorization**:
   - Client agent requests access token for A2A service
   - A2A service validates the client's token
   
2. **A2A → Client Authorization**:
   - A2A service requests access token for client agent
   - Client agent validates the A2A service's token

### Usage

#### As a Module
```python
from identity_client import TBAC

# Create TBAC instance
tbac_handler = TBAC()

# Test bidirectional authorization
if tbac_handler.authorize_bidirectional():
    print("✅ Full bidirectional authorization successful")
else:
    print("❌ Authorization failed")

# Check individual directions
if tbac_handler.is_client_authorized():
    print("Client can send messages to A2A")
    
if tbac_handler.is_a2a_authorized():
    print("A2A can send responses to client")
```

#### Standalone Test
```python
# Run directly for testing
python identity_client.py
```

### Configuration Requirements

Required environment variables for TBAC:
```bash
# Client Agent Credentials
CLIENT_AGENT_API_KEY=client_api_key_here
CLIENT_AGENT_ID=client_agent_id_here

# A2A Service Credentials
A2A_SERVICE_API_KEY=a2a_api_key_here
A2A_SERVICE_ID=a2a_service_id_here
```

### Expected Output

Successful TBAC authorization:
```
TBAC SDKs initialized
TBAC: Getting client agent access token...
TBAC SUCCESS: client token obtained: ey.........
TBAC: Authorizing client token with A2A service...
TBAC SUCCESS: client agent authorized by A2A service
TBAC: A2A service getting access token...
TBAC SUCCESS: a2a token obtained: ey........
TBAC: Authorizing a2a token with client agent...
TBAC SUCCESS: A2A service authorized by client agent
```

### Methods

#### Core Methods

- `authorize_bidirectional()`: Performs full bidirectional authorization
- `authorize_client_to_a2a()`: Authorizes client to communicate with A2A service
- `authorize_a2a_to_client()`: Authorizes A2A service to communicate with client
- `is_fully_authorized()`: Checks if both directions are authorized
- `is_client_authorized()`: Checks client authorization status
- `is_a2a_authorized()`: Checks A2A service authorization status

## Installation

### Prerequisites

- Python 3.8+
- pip package manager

### Setup

1. Install required packages:
```bash
pip install requests python-dotenv identity-service-sdk
```

2. Create `.env` file:
```bash
# Triage API Configuration
TRIAGE_APP_ID=your_app_id
TRIAGE_APP_KEY=your_app_key
TRIAGE_INSTANCE_ID=your_instance_id
TRIAGE_TOKEN_URL=https://api.triage.example.com/oauth/token
TRIAGE_BASE_URL=https://api.triage.example.com/v1

# TBAC Configuration (optional)
CLIENT_AGENT_API_KEY=client_api_key
CLIENT_AGENT_ID=client_agent_id
A2A_SERVICE_API_KEY=a2a_api_key
A2A_SERVICE_ID=a2a_service_id
```

## Testing Workflow

### Recommended Test Sequence

1. **Test External API Connection**:
   ```bash
   python triage_util.py token  # Quick token test
   python triage_util.py         # Full flow test
   ```

2. **Test TBAC Authorization** (if using TBAC):
   ```bash
   python identity_client_util.py
   ```

3. **Start Main Service**:
   ```bash
   python main_service.py
   ```

## Troubleshooting

### Common Issues

#### Triage API Test Failures

| Error | Cause | Solution |
|-------|-------|----------|
| Missing environment variables | `.env` not configured | Create `.env` file with required variables |
| 401 Unauthorized | Invalid credentials | Check TRIAGE_APP_ID and TRIAGE_APP_KEY |
| Connection timeout | Network issues | Check firewall/proxy settings |
| 400 Bad Request | Invalid payload | Verify API version compatibility |

#### TBAC Authorization Failures

| Error | Cause | Solution |
|-------|-------|----------|
| TBAC Disabled | Missing credentials | Add all 4 TBAC environment variables |
| Token acquisition failed | Invalid API key | Verify CLIENT_AGENT_API_KEY and A2A_SERVICE_API_KEY |
| Authorization failed | Service not registered | Ensure both agents are registered with identity service |
| SDK initialization failed | Missing dependency | Install identity-service-sdk package |

### Debug Tips

1. **Enable Verbose Logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check Environment Variables**:
   ```bash
   python -c "import os; print(os.getenv('TRIAGE_APP_ID'))"
   ```

3. **Test Network Connectivity**:
   ```bash
   curl -I https://api.triage.example.com/health
   ```

## Integration with Main Service

These utilities are designed to work with the main A2A Medical Triage Service:

1. Use `triage_client.py` to validate external API connectivity before starting the service
2. Use `identity_client.py` to test TBAC configuration independently
3. The main service uses the same environment variables tested by these utilities

## Security Notes

- **Never commit credentials**: Keep `.env` file in `.gitignore`
- **Token Security**: Tokens are temporary and should not be stored
- **Test Data Only**: Use test demographics and symptoms in testing
- **TBAC Optional**: Service works without TBAC for development/testing

## Contributing

When adding new test scenarios:

1. Add to the `conversation_turns` array for new symptom flows
2. Create separate test functions for different demographics
3. Include error case testing
4. Document expected outcomes
