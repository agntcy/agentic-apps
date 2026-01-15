# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
A2A Protocol Compliant Medical Triage Agent v2.0.0
"""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import pandas as pd
from dotenv import load_dotenv
import sys
from pathlib import Path

from a2a.types import JSONRPCErrorResponse, JSONParseError, InvalidRequestError, MethodNotFoundError, InvalidParamsError, InternalError, TaskNotFoundError, TaskNotCancelableError

# logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# A2A Protocol Enums and Data Classes
class TaskState(Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"
    UNKNOWN = "unknown"

@dataclass
class TextPart:
    kind: str = "text"
    text: str = ""
    metadata: Optional[Dict] = None

@dataclass
class FilePart:
    kind: str = "file"
    file: Dict = field(default_factory=dict)
    metadata: Optional[Dict] = None

@dataclass
class DataPart:
    kind: str = "data"
    data: Dict = field(default_factory=dict)
    metadata: Optional[Dict] = None

@dataclass
class A2AMessage:
    role: str  # "user" or "agent"
    parts: List[Union[TextPart, FilePart, DataPart]]
    messageId: str = field(default_factory=lambda: str(uuid.uuid4()))
    taskId: Optional[str] = None
    contextId: Optional[str] = None
    kind: str = "message"
    metadata: Optional[Dict] = None
    extensions: Optional[List[str]] = None
    referenceTaskIds: Optional[List[str]] = None

@dataclass
class TaskStatus:
    state: TaskState
    message: Optional[A2AMessage] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Artifact:
    artifactId: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    description: Optional[str] = None
    parts: List[Union[TextPart, FilePart, DataPart]] = field(default_factory=list)
    metadata: Optional[Dict] = None
    extensions: Optional[List[str]] = None

@dataclass
class A2ATask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contextId: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = field(default_factory=lambda: TaskStatus(TaskState.SUBMITTED))
    history: List[A2AMessage] = field(default_factory=list)
    artifacts: List[Artifact] = field(default_factory=list)
    metadata: Optional[Dict] = None
    kind: str = "task"
    
    # Medical triage specific data
    patient_name: str = ""
    patient_phone: str = ""
    chief_complaint: str = ""
    symptoms: List[str] = field(default_factory=list)
    symptom_duration: str = ""
    severity_score: int = 0
    answers: Dict[str, str] = field(default_factory=dict)
    urgency_level: str = ""
    recommendation: str = ""
    doctor_type: str = ""
    current_stage: str = "initial"

class AdvancedMedicalIntelligence:
    """Enhanced medical AI with dynamic questioning capabilities"""
    
    def __init__(self, openai_url: str, openai_api_key: str, openai_model: str = "gpt-4o"):
        self.openai_url = openai_url
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {openai_api_key}'
        }
        
        logger.info(f"🧠 Advanced Medical AI Initialized - Model: {openai_model}")

    async def generate_dynamic_questions(self, symptoms: List[str], previous_answers: Dict[str, str]) -> List[str]:
        """Generate intelligent follow-up questions based on symptoms and previous answers"""
        
        prompt = f"""You are an expert medical triage nurse with 20+ years of experience. Generate intelligent, medically relevant follow-up questions for triage assessment.

CURRENT SYMPTOMS: {', '.join(symptoms)}
PREVIOUS ANSWERS: {json.dumps(previous_answers, indent=2)}

TASK: Generate 2-3 specific, medically relevant follow-up questions that will help determine:
1. Urgency level (emergency, urgent, or routine care)
2. Appropriate medical specialty or recommendation
3. Additional symptoms or risk factors

GUIDELINES:
- Ask about red flag symptoms for the reported conditions
- Include questions about severity, progression, and associated symptoms
- Consider patient safety and appropriate care level
- Each question should be clear and answerable by a layperson
- Avoid overly technical medical terminology
- Focus on decision-critical information

REQUIRED JSON RESPONSE:
{{
    "questions": [
        "Clear, specific medical question 1?",
        "Clear, specific medical question 2?",
        "Clear, specific medical question 3?"
    ],
    "reasoning": "Brief explanation of why these questions are important for triage"
}}"""

        try:
            payload = {
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Generate dynamic triage questions for: {', '.join(symptoms)}"}
                ],
                "temperature": 0.1,
                "max_tokens": 600
            }
            
            response = requests.post(
                self.openai_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == HTTPStatus.OK:
                response_json = response.json()
                ai_content = response_json['choices'][0]['message']['content']
                
                # Parse JSON response
                content = ai_content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                return parsed.get("questions", [])
            else:
                logger.error(f"Failed to generate questions: {response.status_code}")
                return self._fallback_questions(symptoms)
                
        except Exception as e:
            logger.error(f"Exception generating questions: {e}")
            return self._fallback_questions(symptoms)

    def _fallback_questions(self, symptoms: List[str]) -> List[str]:
        """Fallback questions when AI generation fails"""
        if "chest pain" in ' '.join(symptoms).lower():
            return [
                "Is the pain sharp, crushing, or burning?",
                "Does the pain radiate to your arm, jaw, or back?",
                "Do you have shortness of breath or sweating?"
            ]
        elif "headache" in ' '.join(symptoms).lower():
            return [
                "Is the headache throbbing or constant?",
                "Do you have any visual changes or sensitivity to light?",
                "Have you had any recent head injuries?"
            ]
        else:
            return [
                "How would you describe the severity on a scale of 1-10?",
                "Have you experienced this type of symptom before?",
                "Do you have any other associated symptoms?"
            ]

    async def process_triage_assessment(self, task: A2ATask, user_input: str, context: str = "") -> Dict:
        """Process user input for medical triage with enhanced AI"""
        
        prompt = self._construct_triage_prompt(task, user_input, context)
        
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.1,
                "max_tokens": 800
            }
            
            response = requests.post(
                self.openai_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == HTTPStatus.OK:
                response_json = response.json()
                ai_content = response_json['choices'][0]['message']['content']
                return self._parse_triage_response(ai_content)
            else:
                logger.error(f"Triage assessment failed: {response.status_code}")
                return self._create_fallback_response(task.current_stage)
                
        except Exception as e:
            logger.error(f"Triage assessment exception: {e}")
            return self._create_fallback_response(task.current_stage)

    def _construct_triage_prompt(self, task: A2ATask, user_input: str, context: str) -> str:
        """Construct stage-specific prompts for triage assessment"""
        
        task_data = {
            "current_stage": task.current_stage,
            "symptoms": task.symptoms,
            "duration": task.symptom_duration,
            "severity": task.severity_score,
            "answers": task.answers,
            "conversation": [{"role": msg.role, "content": msg.parts[0].text if msg.parts else ""} 
                           for msg in task.history[-3:]]
        }
        
        if task.current_stage == "initial":
            return f"""You are an expert medical triage nurse. Analyze the user's chief complaint and extract symptoms.

TASK DATA: {json.dumps(task_data, indent=2)}
CONTEXT: {context}

GUIDELINES:
- Identify medical symptoms mentioned
- Determine if this requires medical triage
- Extract key information
- Be professional and empathetic

REQUIRED JSON RESPONSE:
{{
    "response": "your professional response to the patient",
    "is_medical": true/false,
    "symptoms_identified": ["symptom1", "symptom2"],
    "extract": {{"field_name": "value"}},
    "next_stage": "generic|complete",
    "medical_concern": true/false
}}"""
        
        elif task.current_stage == "generic":
            return f"""You are processing generic symptom assessment for duration and severity.

TASK DATA: {json.dumps(task_data, indent=2)}

GUIDELINES:
- Extract symptom duration (standardize format)
- Extract severity score (1-10 scale)
- Validate responses are reasonable

REQUIRED JSON RESPONSE:
{{
    "response": "your response acknowledging the information",
    "extract": {{"symptom_duration": "standardized_duration", "severity_score": number}},
    "next_stage": "specific",
    "duration_valid": true/false,
    "severity_valid": true/false
}}"""
        
        elif task.current_stage == "assessment":
            return f"""You are conducting FINAL MEDICAL URGENCY ASSESSMENT.

TASK DATA: {json.dumps(task_data, indent=2)}

URGENCY LEVELS:
- HIGH: Life-threatening, immediate 911 required
- MEDIUM: Urgent care needed, specialty referral
- LOW: Can see general practitioner

REQUIRED JSON RESPONSE:
{{
    "response": "your professional assessment and recommendation",
    "urgency_level": "low|medium|high",
    "doctor_type": "specific doctor type or 911",
    "recommendation": "detailed medical recommendation",
    "reasoning": "clinical reasoning for urgency level",
    "next_stage": "complete",
    "emergency_alert": true/false
}}"""
        
        return f"""Process this medical interaction professionally. Current stage: {task.current_stage}"""

    def _parse_triage_response(self, response_text: str) -> Dict:
        """Parse AI response with error recovery"""
        try:
            content = response_text.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            if "response" not in parsed:
                parsed["response"] = "I understand. Please continue."
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            response_match = re.search(r'"response":\s*"([^"]*)"', response_text)
            if response_match:
                return {
                    "response": response_match.group(1),
                    "extract": {},
                    "next_stage": "generic"
                }
            return self._create_fallback_response("generic")

    def _create_fallback_response(self, current_stage: str) -> Dict:
        """Create fallback responses for different stages"""
        fallbacks = {
            "initial": {
                "response": "I understand you have a medical concern. Could you tell me more about your symptoms?",
                "is_medical": True,
                "symptoms_identified": [],
                "extract": {},
                "next_stage": "generic"
            },
            "generic": {
                "response": "Thank you for that information. Let me ask you some specific questions.",
                "extract": {},
                "next_stage": "specific"
            },
            "specific": {
                "response": "I understand. Let me continue with the assessment.",
                "extract": {},
                "next_stage": "assessment"
            },
            "assessment": {
                "response": "Based on your symptoms, I recommend seeing a general practitioner.",
                "urgency_level": "low",
                "doctor_type": "general practitioner",
                "recommendation": "Schedule an appointment with your primary care physician",
                "next_stage": "complete"
            }
        }
        
        return fallbacks.get(current_stage, fallbacks["generic"])

class A2ATriageAgent:
    """A2A Protocol Compliant Medical Triage Agent"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.medical_ai = AdvancedMedicalIntelligence(
            openai_url=config['openai_url'],
            openai_api_key=config['openai_api_key'],
            openai_model=config.get('openai_model', 'gpt-4o')
        )
        
        # A2A Protocol storage
        self.tasks: Dict[str, A2ATask] = {}
        self.contexts: Dict[str, List[str]] = {}  # contextId -> list of taskIds
        
        # Agent capabilities
        self.agent_card = self._create_agent_card()
        
        logger.info("🏥 A2A Medical Triage Agent Initialized")

    def _create_agent_card(self) -> Dict:
        """Create A2A compliant Agent Card"""
        return {
            "protocolVersion": "0.3.0",
            "name": "Medical Symptom Triage Agent",
            "description": "AI-powered medical triage agent that conducts intelligent symptom assessment, generates dynamic follow-up questions, and provides urgency recommendations with appropriate medical referrals.",
            "url": f"http://localhost:{self.config.get('port', 8080)}/a2a/v1",
            "preferredTransport": "JSONRPC",
            "provider": {
                "organization": "Cisco Outshift contributors/ssyechuri",
                "url": ""
            },
            "iconUrl": f"http://localhost:{self.config.get('port', 8080)}/static/icon.png",
            "version": "2.0.0",
            "documentationUrl": f"http://localhost:{self.config.get('port', 8080)}/docs",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True
            },
            "securitySchemes": {
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            },
            "security": [{"apiKey": []}],
            "defaultInputModes": ["application/json", "text/plain"],
            "defaultOutputModes": ["application/json", "text/plain"],
            "skills": [
                {
                    "id": "medical-triage",
                    "name": "Medical Symptom Triage",
                    "description": "Conducts comprehensive medical symptom assessment using AI-generated dynamic questions, evaluates urgency levels, and provides appropriate medical care recommendations.",
                    "tags": ["medical", "triage", "healthcare", "symptoms", "assessment", "emergency"],
                    "examples": [
                        "I have a severe headache that started this morning",
                        "I'm experiencing chest pain and shortness of breath",
                        "My child has a fever and isn't eating",
                        "I have abdominal pain that's getting worse"
                    ],
                    "inputModes": ["application/json", "text/plain"],
                    "outputModes": ["application/json", "text/plain"]
                },
                {
                    "id": "emergency-assessment",
                    "name": "Emergency Condition Assessment",
                    "description": "Rapid assessment for potentially life-threatening conditions with immediate 911 recommendations when appropriate.",
                    "tags": ["emergency", "911", "urgent", "life-threatening"],
                    "examples": [
                        "I'm having severe chest pain with sweating",
                        "I can't breathe properly",
                        "I have severe bleeding that won't stop"
                    ],
                    "inputModes": ["application/json", "text/plain"],
                    "outputModes": ["application/json", "text/plain"]
                }
            ],
            "supportsAuthenticatedExtendedCard": False
        }

    async def handle_message_send(self, params: Dict) -> Dict:
        """Handle A2A message/send requests"""
        try:
            message_data = params.get("message", {})
            configuration = params.get("configuration", {})
            
            # Extract message details
            role = message_data.get("role", "user")
            parts = message_data.get("parts", [])
            message_id = message_data.get("messageId", str(uuid.uuid4()))
            task_id = message_data.get("taskId")
            context_id = message_data.get("contextId")
            
            # Create A2A message
            a2a_message = A2AMessage(
                role=role,
                parts=[self._convert_part(part) for part in parts],
                messageId=message_id,
                taskId=task_id,
                contextId=context_id
            )
            
            # Get or create task
            if task_id and task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
                    return self._create_error_response(TaskNotCancelableError, TaskNotCancelableError.message, task_id)
            else:
                # Create new task
                task = A2ATask()
                task_id = task.id
                a2a_message.taskId = task_id
                if not context_id:
                    context_id = task.contextId
                    a2a_message.contextId = context_id
                
                self.tasks[task_id] = task
                
                # Track context
                if context_id not in self.contexts:
                    self.contexts[context_id] = []
                self.contexts[context_id].append(task_id)
            
            # Add message to task history
            task.history.append(a2a_message)
            
            # Process the message
            user_input = self._extract_text_from_parts(a2a_message.parts)
            result = await self._process_triage_message(task, user_input)
            
            # Update task status
            if result.get("triage_complete", False):
                task.status.state = TaskState.COMPLETED
                task.current_stage = "complete"
                
                # Create artifacts
                if result.get("recommendation"):
                    artifact = Artifact(
                        name="Triage Assessment",
                        description="Medical triage assessment and recommendations",
                        parts=[
                            DataPart(data={
                                "urgency_level": result.get("urgency_level", ""),
                                "doctor_type": result.get("doctor_type", ""),
                                "recommendation": result.get("recommendation", ""),
                                "symptoms": task.symptoms,
                                "duration": task.symptom_duration,
                                "severity_score": task.severity_score,
                                "clinical_notes": self._generate_clinical_notes(task)
                            })
                        ]
                    )
                    task.artifacts.append(artifact)
            elif result.get("emergency_alert", False):
                task.status.state = TaskState.COMPLETED
                task.current_stage = "complete"
            else:
                task.status.state = TaskState.INPUT_REQUIRED
            
            # Create response message if needed
            if result.get("response"):
                response_message = A2AMessage(
                    role="agent",
                    parts=[TextPart(text=result["response"])],
                    taskId=task_id,
                    contextId=context_id
                )
                task.history.append(response_message)
                task.status.message = response_message
            
            # Return task or message based on configuration
            if configuration.get("blocking", False) or task.status.state == TaskState.COMPLETED:
                return self._task_to_dict(task)
            else:
                return self._message_to_dict(task.status.message) if task.status.message else self._task_to_dict(task)
            
        except Exception as e:
            logger.error(f"Error in message/send: {e}")
            return self._create_error_response(InternalError, InternalError.message)

    async def handle_tasks_get(self, params: Dict) -> Dict:
        """Handle A2A tasks/get requests"""
        try:
            task_id = params.get("id")
            history_length = params.get("historyLength", 10)
            
            if not task_id or task_id not in self.tasks:
                return self._create_error_response(TaskNotFoundError, TaskNotFoundError.message, task_id)
            
            task = self.tasks[task_id]
            
            # Limit history if requested
            if history_length and len(task.history) > history_length:
                task_copy = A2ATask(**task.__dict__)
                task_copy.history = task.history[-history_length:]
                return self._task_to_dict(task_copy)
            
            return self._task_to_dict(task)
            
        except Exception as e:
            logger.error(f"Error in tasks/get: {e}")
            return self._create_error_response(InternalError, InternalError.message)

    async def handle_tasks_cancel(self, params: Dict) -> Dict:
        """Handle A2A tasks/cancel requests"""
        try:
            task_id = params.get("id")
            
            if not task_id or task_id not in self.tasks:
                return self._create_error_response(TaskNotFoundError, TaskNotFoundError.message, task_id)
            
            task = self.tasks[task_id]
            
            if task.status.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
                return self._create_error_response(TaskNotCancelableError, TaskNotCancelableError.message, task_id)
            
            task.status.state = TaskState.CANCELED
            task.status.message = A2AMessage(
                role="agent",
                parts=[TextPart(text="Task has been canceled.")],
                taskId=task_id,
                contextId=task.contextId
            )
            
            return self._task_to_dict(task)
            
        except Exception as e:
            logger.error(f"Error in tasks/cancel: {e}")
            return self._create_error_response(InternalError, InternalError.message)

    async def _process_triage_message(self, task: A2ATask, user_input: str) -> Dict:
        """Process triage message through enhanced workflow"""
        
        if task.current_stage == "initial":
            return await self._process_initial_assessment(task, user_input)
        elif task.current_stage == "generic":
            return await self._process_generic_questions(task, user_input)
        elif task.current_stage == "specific":
            return await self._process_specific_questions(task, user_input)
        elif task.current_stage == "assessment":
            return await self._process_final_assessment(task, user_input)
        else:
            return {"response": "Triage session complete.", "triage_complete": True}

    async def _process_initial_assessment(self, task: A2ATask, user_input: str) -> Dict:
        """Process initial symptom identification with AI"""
        
        ai_result = await self.medical_ai.process_triage_assessment(
            task, user_input, "Analyze chief complaint and identify symptoms"
        )
        
        # Update task with extracted data
        if ai_result.get("extract"):
            for key, value in ai_result["extract"].items():
                setattr(task, key, value)
        
        # Extract symptoms
        symptoms_mentioned = ai_result.get("symptoms_identified", [])
        task.symptoms = symptoms_mentioned
        task.chief_complaint = user_input
        
        # Check if medical
        is_medical = ai_result.get("is_medical", True)
        
        if not is_medical:
            task.current_stage = "complete"
            task.urgency_level = "low"
            task.recommendation = "Non-medical appointment scheduling"
            
            return {
                "response": "I understand this is not a medical emergency. Let me help you schedule your appointment.",
                "triage_complete": True,
                "is_medical": False
            }
        
        # Move to generic questions
        task.current_stage = "generic"
        
        response = ai_result.get("response", "I understand your symptoms. Let me ask you a couple of questions.")
        response += "\n\nFirst, how long have you been experiencing these symptoms?"
        
        return {
            "response": response,
            "symptoms_identified": symptoms_mentioned
        }

    async def _process_generic_questions(self, task: A2ATask, user_input: str) -> Dict:
        """Process generic triage questions with AI"""
        
        ai_result = await self.medical_ai.process_triage_assessment(
            task, user_input, "Extract symptom duration and severity information"
        )
        
        # Update task data
        if ai_result.get("extract"):
            for key, value in ai_result["extract"].items():
                setattr(task, key, value)
        
        # Check what we still need
        need_duration = not task.symptom_duration
        need_severity = not task.severity_score
        
        if need_duration:
            return {
                "response": "Thank you. How long have you been experiencing these symptoms?"
            }
        elif need_severity:
            return {
                "response": "Thank you. On a scale of 1 to 10, with 10 being the worst pain imaginable, how severe are your symptoms?"
            }
        else:
            # Both collected, move to AI-generated specific questions
            task.current_stage = "specific"
            return await self._start_dynamic_questions(task)

    async def _start_dynamic_questions(self, task: A2ATask) -> Dict:
        """Start AI-generated specific questions"""
        
        if not task.symptoms:
            # No symptoms identified, move to assessment
            task.current_stage = "assessment"
            return await self._process_final_assessment(task, "")
        
        # Generate dynamic questions using AI
        questions = await self.medical_ai.generate_dynamic_questions(task.symptoms, task.answers)
        
        if not questions:
            # No questions available, move to assessment
            task.current_stage = "assessment"
            return await self._process_final_assessment(task, "")
        
        # Store questions in task metadata
        task.metadata = task.metadata or {}
        task.metadata["current_questions"] = questions
        task.metadata["current_question_index"] = 0
        
        first_question = questions[0]
        
        return {
            "response": f"Now I need to ask you some specific questions about your {', '.join(task.symptoms)}. {first_question}",
            "current_questions": questions,
            "question_number": 1,
            "total_questions": len(questions)
        }

    async def _process_specific_questions(self, task: A2ATask, user_input: str) -> Dict:
        """Process AI-generated specific questions"""
        
        if not task.metadata or "current_questions" not in task.metadata:
            # No questions setup, move to assessment
            task.current_stage = "assessment"
            return await self._process_final_assessment(task, user_input)
        
        questions = task.metadata["current_questions"]
        current_index = task.metadata.get("current_question_index", 0)
        
        # Store the answer
        question_key = f"question_{current_index + 1}"
        task.answers[question_key] = user_input
        
        # Move to next question
        next_index = current_index + 1
        task.metadata["current_question_index"] = next_index
        
        # Check if more questions
        if next_index < len(questions):
            next_question = questions[next_index]
            return {
                "response": f"Thank you. {next_question}",
                "question_number": next_index + 1,
                "total_questions": len(questions)
            }
        
        # All questions complete, move to assessment
        task.current_stage = "assessment"
        return {
            "response": "Thank you for answering all the questions. Let me assess your symptoms now.",
            "questions_complete": True,
            "moving_to_assessment": True
        }

    async def _process_final_assessment(self, task: A2ATask, user_input: str) -> Dict:
        """Process final medical assessment with AI"""
        
        assessment_context = f"""
CLINICAL DATA FOR ASSESSMENT:
- Symptoms: {', '.join(task.symptoms)}
- Duration: {task.symptom_duration}
- Severity: {task.severity_score}/10
- Clinical Answers: {json.dumps(task.answers, indent=2)}

Determine urgency level and appropriate medical recommendation.
"""
        
        ai_result = await self.medical_ai.process_triage_assessment(
            task, "CONDUCT_FINAL_ASSESSMENT", assessment_context
        )
        
        # Extract assessment results
        urgency_level = ai_result.get("urgency_level", "low")
        doctor_type = ai_result.get("doctor_type", "general practitioner")
        recommendation = ai_result.get("recommendation", "Schedule an appointment with your primary care physician")
        
        # Update task
        task.urgency_level = urgency_level
        task.doctor_type = doctor_type
        task.recommendation = recommendation
        task.current_stage = "complete"
        
        # Handle emergency situations
        if urgency_level.lower() == "high" or ai_result.get("emergency_alert", False):
            emergency_response = "⚠️ EMERGENCY: Based on your symptoms, this could be a medical emergency. Please hang up immediately and call 911 or go to the nearest emergency room."
            
            return {
                "response": emergency_response,
                "urgency_level": "high",
                "emergency_alert": True,
                "recommendation": "CALL 911 IMMEDIATELY",
                "triage_complete": True,
                "end_call": True
            }
        
        # Generate final response
        response = ai_result.get("response", "")
        if not response:
            if urgency_level.lower() == "medium":
                response = f"Based on your symptoms, I recommend seeing a {doctor_type} soon. {recommendation}"
            else:
                response = f"Based on your symptoms, you can schedule an appointment with a {doctor_type}. {recommendation}"
        
        return {
            "response": response,
            "urgency_level": urgency_level,
            "doctor_type": doctor_type,
            "recommendation": recommendation,
            "triage_complete": True
        }

    def _convert_part(self, part_data: Dict) -> Union[TextPart, FilePart, DataPart]:
        """Convert dictionary to appropriate Part type"""
        kind = part_data.get("kind", "text")
        
        if kind == "text":
            return TextPart(
                text=part_data.get("text", ""),
                metadata=part_data.get("metadata")
            )
        elif kind == "file":
            return FilePart(
                file=part_data.get("file", {}),
                metadata=part_data.get("metadata")
            )
        elif kind == "data":
            return DataPart(
                data=part_data.get("data", {}),
                metadata=part_data.get("metadata")
            )
        else:
            return TextPart(text=str(part_data))

    def _extract_text_from_parts(self, parts: List) -> str:
        """Extract text content from message parts"""
        text_parts = []
        for part in parts:
            if hasattr(part, 'text'):
                text_parts.append(part.text)
            elif hasattr(part, 'data') and isinstance(part.data, dict):
                text_parts.append(str(part.data))
        return " ".join(text_parts)

    def _task_to_dict(self, task: A2ATask) -> Dict:
        """Convert A2ATask to dictionary for JSON response"""
        return {
            "id": task.id,
            "contextId": task.contextId,
            "status": {
                "state": task.status.state.value,
                "message": self._message_to_dict(task.status.message) if task.status.message else None,
                "timestamp": task.status.timestamp
            },
            "history": [self._message_to_dict(msg) for msg in task.history],
            "artifacts": [self._artifact_to_dict(artifact) for artifact in task.artifacts],
            "metadata": task.metadata,
            "kind": task.kind
        }

    def _message_to_dict(self, message: A2AMessage) -> Dict:
        """Convert A2AMessage to dictionary"""
        return {
            "role": message.role,
            "parts": [self._part_to_dict(part) for part in message.parts],
            "messageId": message.messageId,
            "taskId": message.taskId,
            "contextId": message.contextId,
            "kind": message.kind,
            "metadata": message.metadata,
            "extensions": message.extensions,
            "referenceTaskIds": message.referenceTaskIds
        }

    def _part_to_dict(self, part) -> Dict:
        """Convert Part to dictionary"""
        if isinstance(part, TextPart):
            return {
                "kind": part.kind,
                "text": part.text,
                "metadata": part.metadata
            }
        elif isinstance(part, FilePart):
            return {
                "kind": part.kind,
                "file": part.file,
                "metadata": part.metadata
            }
        elif isinstance(part, DataPart):
            return {
                "kind": part.kind,
                "data": part.data,
                "metadata": part.metadata
            }
        else:
            return {"kind": "text", "text": str(part)}

    def _artifact_to_dict(self, artifact: Artifact) -> Dict:
        """Convert Artifact to dictionary"""
        return {
            "artifactId": artifact.artifactId,
            "name": artifact.name,
            "description": artifact.description,
            "parts": [self._part_to_dict(part) for part in artifact.parts],
            "metadata": artifact.metadata,
            "extensions": artifact.extensions
        }

    def _create_error_response(self, code: int, message: str, data: Any = None) -> Dict:
        """Create A2A compliant error response"""
        return {
            "error": {
                "code": code,
                "message": message,
                "data": data
            }
        }

    def _generate_clinical_notes(self, task: A2ATask) -> str:
        """Generate comprehensive clinical notes"""
        notes = f"MEDICAL TRIAGE ASSESSMENT:\n"
        notes += f"Chief Complaint: {task.chief_complaint}\n"
        notes += f"Symptoms: {', '.join(task.symptoms)}\n"
        notes += f"Duration: {task.symptom_duration}\n"
        notes += f"Severity: {task.severity_score}/10\n"
        notes += f"Urgency: {task.urgency_level.upper()}\n"
        notes += f"Recommendation: {task.recommendation}\n"
        
        if task.answers:
            notes += f"\nCLINICAL RESPONSES:\n"
            for question, answer in task.answers.items():
                notes += f"{question}: {answer}\n"
        
        return notes

# Flask Web Server for A2A Protocol
class A2ATriageServer:
    """Flask server implementing A2A protocol endpoints"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.agent = A2ATriageAgent(config)
        self.app = Flask(__name__)
        CORS(self.app)
        
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup A2A protocol routes"""
        
        # Agent Card endpoint (well-known URI)
        @self.app.route('/.well-known/agent-card.json', methods=['GET'])
        def get_agent_card():
            return jsonify(self.agent.agent_card)
        
        # Main A2A JSON-RPC endpoint
        @self.app.route('/a2a/v1', methods=['POST'])
        async def a2a_endpoint():
            try:
                data = request.get_json()
                
                if not data or "jsonrpc" not in data or data["jsonrpc"] != "2.0":
                    return jsonify({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": InvalidRequestError,
                            "message": InvalidRequestError.message
                        },
                        "id": data.get("id") if data else None
                    }), HTTPStatus.BAD_REQUEST
                
                method = data.get("method")
                params = data.get("params", {})
                request_id = data.get("id")
                
                # Route to appropriate handler
                if method == "message/send":
                    result = await self.agent.handle_message_send(params)
                elif method == "tasks/get":
                    result = await self.agent.handle_tasks_get(params)
                elif method == "tasks/cancel":
                    result = await self.agent.handle_tasks_cancel(params)
                else:
                    return jsonify({
                        "jsonrpc": "2.0",
                        "error": {
                            "code": MethodNotFoundError,
                            "message": MethodNotFoundError
                        },
                        "id": request_id
                    }), HTTPStatus.NOT_FOUND
                
                # Handle errors
                if "error" in result:
                    return jsonify({
                        "jsonrpc": "2.0",
                        "error": result["error"],
                        "id": request_id
                    }), HTTPStatus.BAD_REQUEST
                
                # Success response
                return jsonify({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                })
                
            except Exception as e:
                logger.error(f"A2A endpoint error: {e}")
                return jsonify({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": InternalError,
                        "message": InternalError.message,
                        "data": str(e)
                    },
                    "id": request.get_json().get("id") if request.get_json() else None
                }), HTTPStatus.INTERNAL_SERVER_ERROR
        
        # Health check
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                "status": "healthy",
                "agent": "Medical Triage Agent",
                "version": "2.0.0",
                "protocol": "A2A v0.2.9"
            })
        
        # Documentation
        @self.app.route('/docs', methods=['GET'])
        def documentation():
            return jsonify({
                "name": "Medical Symptom Triage Agent",
                "description": "A2A compliant medical triage agent with AI-powered dynamic questioning",
                "version": "2.0.0",
                "protocol": "A2A v0.2.9",
                "endpoints": {
                    "agent_card": "/.well-known/agent-card.json",
                    "a2a_service": "/a2a/v1",
                    "health": "/health",
                    "docs": "/docs"
                },
                "supported_methods": [
                    "message/send",
                    "tasks/get", 
                    "tasks/cancel"
                ],
                "capabilities": {
                    "streaming": True,
                    "pushNotifications": False,
                    "stateTransitionHistory": True,
                    "dynamic_questioning": True,
                    "ai_powered_assessment": True
                }
            })

    def run(self):
        """Run the A2A server"""
        port = self.config.get('port', 8080)
        host = self.config.get('host', '0.0.0.0')
        debug = self.config.get('debug', False)
        
        logger.info(f"🚀 Starting A2A Medical Triage Server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

def load_config():
    """Load configuration from environment"""
    try:
        load_dotenv()
    except ImportError:
        logger.warning("python-dotenv not available, reading from environment...")
    
    config = {}
    required_configs = {
        'openai_url': 'OPENAI_URL',
        'openai_api_key': 'OPENAI_API_KEY'
    }
    
    optional_configs = {
        'openai_model': 'OPENAI_MODEL',
        'port': 'PORT',
        'host': 'HOST',
        'debug': 'DEBUG'
    }
    
    # Check required configs
    missing_configs = []
    for key, env_var in required_configs.items():
        value = os.getenv(env_var)
        if value and value.strip():
            config[key] = value.strip()
        else:
            missing_configs.append(env_var)
    
    if missing_configs:
        logger.error(f"Missing required environment variables: {missing_configs}")
        return None
    
    # Set optional configs with defaults
    defaults = {
        'openai_model': 'gpt-4o',
        'port': 8080,
        'host': '0.0.0.0',
        'debug': False
    }
    
    for key, env_var in optional_configs.items():
        value = os.getenv(env_var)
        if value:
            if key in ['port']:
                config[key] = int(value)
            elif key in ['debug']:
                config[key] = value.lower() in ['true', '1', 'yes']
            else:
                config[key] = value
        else:
            config[key] = defaults[key]
    
    return config

# CLI Interface for testing
async def test_a2a_agent():
    """Test the A2A agent functionality"""
    config = load_config()
    if not config:
        logger.error("Cannot test without configuration")
        return
    
    agent = A2ATriageAgent(config)
    
    logger.info("🧪 Testing A2A Medical Triage Agent")
    
    # Test message/send
    test_message = {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "I have a severe headache"}],
            "messageId": str(uuid.uuid4())
        }
    }
    
    result = await agent.handle_message_send(test_message)
    logger.info(f"✅ Test result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run test
        asyncio.run(test_a2a_agent())
    else:
        # Run server
        config = load_config()
        if config:
            server = A2ATriageServer(config)
            server.run()
        else:
            logger.error("Failed to load configuration")
