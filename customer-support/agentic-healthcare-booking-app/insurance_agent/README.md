# Insurance Agent

Automated insurance discovery and eligibility checking system that integrates with healthcare providers through the Infinitus system's API.

## Overview

The Insurance Agent module provides real-time insurance discovery and eligibility verification capabilities for healthcare booking workflows. It leverages AI-powered automation to streamline the traditionally manual process of verifying patient insurance coverage and benefits.

## Key Features

- **Insurance Discovery**: Automatically identifies patient insurance providers and policy information
- **Eligibility Verification**: Real-time benefits checking including copays, deductibles, and coverage status
- **MCP Integration**: Model Context Protocol server for seamless agent-to-agent communication
- **Voice Agent Integration**: Direct integration with voice-based patient interaction systems

## Architecture

This insurance agent operates through two primary components:

1. **Infinitus API Integration** (`/infinitus`): Core insurance verification engine powered by Infinitus
2. **MCP Client** (`va_mcp.py`): Standardized communication interface for other agents

## How It Works
Voice Agent → MCP Server → Infinitus API → Insurance Provider

### Workflow

1. **Data Collection**: Voice agent gathers patient demographics (name, DOB, state)
2. **Discovery Request**: MCP server calls Infinitus discovery API to identify insurance provider
3. **Eligibility Check**: With provider information, system verifies active coverage and benefits
4. **Response Processing**: Results are parsed and returned to voice agent for patient communication

## Components

### `/infinitus`
Core insurance verification implementation using Infinitus API. Includes MCP server for voice agent integration.

**Key Files:**
- `va_mcp.py` - MCP client implementation for insurance API calls
- `README.md` - Detailed technical documentation

## Use Cases

- **Appointment Scheduling**: Verify insurance before booking appointments
- **Pre-Visit Verification**: Confirm coverage and benefits prior to patient arrival
- **Financial Counseling**: Provide accurate cost estimates based on real-time benefits
- **Prior Authorization**: Gather necessary insurance information for authorization requests

## Integration

The insurance agent is designed to work seamlessly with:

- **Voice Agent**: Real-time insurance verification during phone conversations
- **Triage Agent**: Insurance validation as part of medical assessment workflow
- **Healthcare Booking Systems**: Direct integration with scheduling platforms

## Technologies

- **Infinitus API**: AI-powered insurance verification platform
- **Model Context Protocol (MCP)**: Standardized agent communication
- **JSON-RPC 2.0**: Request/response protocol for MCP operations
- **Python**: Core implementation language

## Getting Started

See the detailed technical documentation in `/infinitus/README.md` for:
- API credentials setup
- MCP server configuration
- Testing and deployment
- Troubleshooting guides

## Security & Compliance

- Secure API key management via environment variables
- No persistent storage of PHI (Protected Health Information)
- Encrypted communication channels

## Support

For implementation details and API-specific documentation, refer to:
- `/infinitus/README.md` - Technical implementation guide
- [Infinitus Documentation](https://www.infinitus.ai/product)
- [MCP Protocol Specification](https://modelcontextprotocol.io)

