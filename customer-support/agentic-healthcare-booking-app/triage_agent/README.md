# Triage Agent
A comprehensive medical triage system implementing two distinct agent architectures for intelligent healthcare assessment and symptom analysis.

## Overview
This repository contains two complementary medical triage agents designed to automate and enhance patient symptom assessment workflows:
- Infermedica Agent - API-based wrapper service utilizing Infermedica's medical knowledge base
- Medical Triage Agent - GPT-4o powered intelligent triage with advanced conversational capabilities

Both agents implement Agent-to-Agent (A2A) communication protocols for seamless integration into healthcare automation pipelines.

## Agent Architectures
### 1. Infermedica Agent
**Technology Stack:**
- Infermedica Medical API
- A2A Wrapper Service Architecture
- Agntcy Identity & Observability Integration

**Key Features:**
- A2A integration with Infermedica's medical knowledge base
- Structured symptom collection and analysis
- Evidence-based triage recommendations
- Comprehensive observability and monitoring
- A2A wrapper for RESTful API for easy integration

**Use Cases:**
- Structured symptom assessment
- Evidence-based triage routing
- Clinical decision support

**Architecture:**\
Patient Input → A2A Protocol → Infermedica Wrapper → Infermedica API → Triage Response

### 2. Medical Triage Agent
**Technology Stack:**
- OpenAI GPT-4o Language Model
- A2A Communication Protocol
- Advanced NLP and Conversation Management

**Key Features:**
- Natural language understanding
- Context-aware conversation flow
- Multi-turn dialogue management
- Intelligent question prioritization
- Dynamic symptom exploration

**Use Cases:**
- Conversational symptom intake
- Complex case assessment
- Multi-symptom analysis

**Architecture:**\
Patient Input → A2A Protocol → GPT-4o Intelligence\
                                      ↓\
                              Context Management\
                                      ↓\
                              Triage Response
                              
## Agent-to-Agent (A2A) Integration
Both agents implement standardized A2A protocols enabling:
- **Interoperability:** Seamless communication between agents
- **Workflow Orchestration:** Chain multiple agents for complex triage
- **Data Standardization:** Consistent input/output formats
- **Scalability:** Easy deployment across distributed systems

