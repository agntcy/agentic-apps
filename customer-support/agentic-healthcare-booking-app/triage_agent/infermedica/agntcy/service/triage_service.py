# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import uuid
import logging
import sys
from pathlib import Path
from datetime import datetime
from http import HTTPStatus
from flask import Flask, request, jsonify
from flask_cors import CORS
from ioa_observe.sdk.decorators import tool, task, workflow, agent
from common.triage_client import TriageClient
from common.tbac import TBAC

from a2a.types import TaskState, JSONRPCErrorResponse, JSONParseError, InvalidRequestError, MethodNotFoundError, InvalidParamsError, InternalError, TaskNotFoundError, TaskNotCancelableError

logger = logging.getLogger(__name__)

@agent(name='a2a_triage_service', description='A2A Medical Triage Service', version='1.0.0', protocol="A2A")
class A2ATriageService:
    """
    Standalone A2A Medical Triage Service with TBAC Integration
    """
    
    def __init__(self, host='0.0.0.0', port=8887, debug=False, enable_tbac=True):
        self.app = Flask(__name__)
        CORS(self.app)
        
        self.host = host
        self.port = port
        self.debug = debug
        
        # Initialize TBAC
        self.tbac = TBAC() if enable_tbac else None
        self.enable_tbac = enable_tbac

        # Load shared key for authentication
        self.shared_key = os.getenv("SHARED_KEY")
        if not self.shared_key:
            logger.warning("SHARED_KEY not found in environment variables")
        
        # In-memory storage for tasks and contexts
        self.tasks = {}
        self.contexts = {}
        
        # Load triage API configuration
        self._load_triage_config()

        # Initialize TriageClient
        self.triage_client = TriageClient(self)
        
        # Setup Flask routes
        self._setup_routes()
        
        # Perform TBAC authorization if enabled
        if self.tbac:
            if not self.tbac.authorize_bidirectional():
                logger.warning("TBAC authorization failed - service will continue but may be restricted")
    
    def _check_authorization(self, operation="general"):
        """Check TBAC authorization for operations"""
        if not self.enable_tbac or not self.tbac:
            return True
        
        if operation == "receive_message":
            # Check if client agent is authorized to send messages to A2A service
            if not self.tbac.is_client_authorized():
                logger.warning("TBAC: client agent not authorized to send messages to A2A service")
                return False
        elif operation == "send_response":
            # Check if A2A service is authorized to send responses back
            if not self.tbac.is_a2a_authorized():
                logger.warning("TBAC: A2A service not authorized to send responses")
                return False
        
        return True
    
    def _create_tbac_error_response(self, request_id, operation):
        """Create error response for TBAC authorization failure"""
        return self._create_error_response(
            request_id, 
            TaskNotFoundError, 
            TaskNotFoundError.message,
            {"tbac_error": True, "operation": operation}
        )
    
    def _load_triage_config(self):
        """Load external triage API configuration from environment variables"""
        required_vars = [
            'TRIAGE_APP_ID',
            'TRIAGE_APP_KEY', 
            'TRIAGE_INSTANCE_ID',
            'TRIAGE_TOKEN_URL',
            'TRIAGE_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            setattr(self, var.lower(), value)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
    def require_auth(self, f):
        """Decorator to require X-Shared-Key authentication"""
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("X-Shared-Key")
            if not self.shared_key:
                logger.warning("SHARED_KEY not configured - authentication disabled")
                return f(*args, **kwargs)
            
            if not auth_header:
                logger.warning("Missing X-Shared-Key header")
                return jsonify(self._create_error_response(
                    None, HTTPStatus.UNAUTHORIZED, "Authorization required"
                )), HTTPStatus.UNAUTHORIZED
            
            if auth_header != self.shared_key:
                logger.warning(f"Invalid X-Shared-Key: {auth_header[:10]}...")
                return jsonify(self._create_error_response(
                    None, HTTPStatus.UNAUTHORIZED, "Invalid authorization key"
                )), HTTPStatus.UNAUTHORIZED
            
            return f(*args, **kwargs)
        
        decorated_function.__name__ = f.__name__
        return decorated_function
    
    def _setup_routes(self):
        """Setup Flask routes for A2A protocol endpoints"""
        
        @self.app.route('/.well-known/agent-card.json', methods=['GET'])
        def agent_card():
            """A2A Agent Discovery Card"""
            card_data = {
                "name": "Medical Triage Agent A2A service",
                "description": "A2A service for an AI agent that performs medical symptom triage and assessment using professional medical protocols",
                "url": f"http://{request.host}",
                "provider": {
                    "organization": "Outshift",
                    "url": f"http://{request.host}"
                },
                "iconUrl": f"http://{request.host}/icon.png",
                "version": "1.0.0",
                "documentationUrl": f"http://{request.host}/docs",
                "capabilities": {
                    "streaming": False,
                    "pushNotifications": False,
                    "stateTransitionHistory": False,
                    "extensions": []
                },
                "securitySchemes": {
                    "tbac": {
                        "type": "http",
                        "scheme": "bearer",
                        "description": "Task-Based Access Control (TBAC)"
                    } if self.enable_tbac else {
                        "type": "http",
                        "scheme": "none"
                    }
                },
                "security": ["tbac"] if self.enable_tbac else [],
                "defaultInputModes": ["text/plain", "application/json"],
                "defaultOutputModes": ["text/plain", "application/json"],
                "skills": [
                    {
                        "id": "medical-triage",
                        "name": "Medical Symptom Triage A2A Service",
                        "description": "Performs comprehensive medical symptom assessment and triage using AI-powered clinical protocols",
                        "tags": ["healthcare", "triage", "medical", "symptoms", "diagnosis"],
                        "examples": [
                            "I have chest pain and shortness of breath",
                            "My child has a fever and headache",
                            "I'm experiencing severe abdominal pain"
                        ],
                        "inputModes": ["text/plain", "application/json"],
                        "outputModes": ["text/plain", "application/json"]
                    }
                ],
                "supportsAuthenticatedExtendedCard": False
            }
            
            # Add TBAC status to card if enabled
            if self.enable_tbac and self.tbac:
                card_data["tbac_status"] = {
                    "enabled": True,
                    "client_authorized": self.tbac.is_client_authorized(),
                    "a2a_authorized": self.tbac.is_a2a_authorized(),
                    "fully_authorized": self.tbac.is_fully_authorized()
                }
            
            return jsonify(card_data)
        
        @self.app.route('/health', methods=['GET'])
        @self.require_auth
        def health_check():
            """Health check endpoint with TBAC status"""
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "active_tasks": len(self.tasks)
            }
            
            if self.enable_tbac and self.tbac:
                health_data["tbac"] = {
                    "enabled": True,
                    "client_authorized": self.tbac.is_client_authorized(),
                    "a2a_authorized": self.tbac.is_a2a_authorized(),
                    "fully_authorized": self.tbac.is_fully_authorized()
                }
            
            return jsonify(health_data)
        
        @self.app.route('/docs', methods=['GET'])
        def documentation():
            """Basic documentation endpoint"""
            return jsonify({
                "title": "Medical Triage A2A Service",
                "description": "Agent-to-Agent protocol service for medical symptom triage",
                "tbac_enabled": self.enable_tbac,
                "endpoints": {
                    "/.well-known/agent-card.json": "Agent discovery card",
                    "/health": "Health check",
                    "/docs": "This documentation",
                    "/": "JSON-RPC 2.0 endpoint for A2A communication"
                },
                "supported_methods": [
                    "message/send",
                    "tasks/get", 
                    "tasks/cancel"
                ]
            })
        
        @self.app.route('/', methods=['POST'])
        @self.require_auth
        def handle_jsonrpc():
            """Main JSON-RPC 2.0 endpoint for A2A protocol with TBAC"""
            try:
                data = request.get_json()
                
                if not self._validate_jsonrpc_request(data):
                    logger.warning(f"Invalid JSON-RPC request: {data}")
                    return jsonify(self._create_error_response(
                        data.get('id'), InvalidRequestError, InvalidRequestError.message
                    ))
                
                method = data['method']
                params = data.get('params', {})
                request_id = data['id']
                
                
                # TBAC authorization check for incoming requests
                if not self._check_authorization("receive_message"):
                    return jsonify(self._create_tbac_error_response(request_id, "receive_message"))
                
                if method == 'message/send':
                    return jsonify(self._handle_message_send(params, request_id))
                elif method == 'tasks/get':
                    return jsonify(self._handle_tasks_get(params, request_id))
                elif method == 'tasks/cancel':
                    return jsonify(self._handle_tasks_cancel(params, request_id))
                else:
                    logger.warning(f"Unknown method: {method}")
                    return jsonify(self._create_error_response(
                        request_id, MethodNotFoundError, MethodNotFoundError.message
                    ))
                    
            except Exception as e:
                logger.error(f"Error handling JSON-RPC request: {e}", exc_info=True)
                return jsonify(self._create_error_response(
                    None, InternalError, InternalError.message
                ))
        @self.app.errorhandler(HTTPStatus.NOT_FOUND)
        def not_found(error):
            return jsonify({"error": "Not found"}), HTTPStatus.NOT_FOUND

        @self.app.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR)
        def internal_error(error):
            logger.error(f"Internal server error: {error}")
            return jsonify({"error": "Internal server error"}), HTTPStatus.INTERNAL_SERVER_ERROR

    def _validate_jsonrpc_request(self, data):
        """Validate JSON-RPC 2.0 request format"""
        if not isinstance(data, dict):
            return False
        if data.get('jsonrpc') != '2.0':
            return False
        if 'method' not in data:
            return False
        if 'id' not in data:
            return False
        return True
    
    def _create_error_response(self, request_id, code, message, data=None):
        """Create JSON-RPC 2.0 error response"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        if data:
            response["error"]["data"] = data
        return response
    
    def _create_success_response(self, request_id, result):
        """Create JSON-RPC 2.0 success response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    @task(name="handle_a2a_message", description="process incoming a2a message from agent", version=1)
    def _handle_message_send(self, params, request_id):
        try:
            message = params.get('message')
            if not message:
                return self._create_error_response(request_id, InvalidParamsError, InvalidParamsError.message)
            
            parts = message.get('parts', [])
            task_id = message.get('taskId')
            context_id = message.get('contextId')
            message_id = message.get('messageId', str(uuid.uuid4()))
            
            user_text = ""
            for part in parts:
                if part.get('kind') == 'text':
                    user_text = part.get('text', '')
                    break
            
            if task_id and task_id in self.tasks:
                result= self._continue_existing_task(task_id, user_text, request_id, message)
            else:
                result= self._create_new_task(user_text, context_id, request_id, message)
            
            if 'result' in result:
                task_result=result['result']
                task_state=task_result.get('status',{}).get('state')
                if task_state == TaskState.COMPLETED:
                    return{
                        **result,
                        "goto":"healthcare_voice_agent",
                        "success":True,
                        "action":"triage_completed"
                    }
                elif task_state == TaskState.INPUT_REQUIRED:
                    return{
                        **result,
                        "goto":"healthcare_voice_agent",
                        "success":True,
                        "action":"triage_continuing"
                    }
                elif task_state == TaskState.FAILED:
                    return{
                        **result,
                        "goto":"Healthcare_voice_agent",
                        "success":False,
                        "error":True,
                        "action":"triage_failed"
                    }
            return result
        except Exception as e:
            print(f"A2A-SERVICE: Error in message/send: {e}")
            error_response= self._create_error_response(request_id, InternalError, InternalError.message)
            return{
                **error_response,
                "goto":"healthcare_voice_agent",
                "success":False,
                "error":True,
                "error_message":str(e)
            }
    
    @workflow(name="medical_triage_workflow", description="complete medical triage workflow", version=1)
    def _create_new_task(self, user_text, context_id, request_id, original_message):
        task_id = str(uuid.uuid4())
        if not context_id:
            context_id = str(uuid.uuid4())
        
        print(f"A2A-SERVICE: Creating new task {task_id}")
        
        task = {
            "id": task_id,
            "contextId": context_id,
            "status": {
                "state": TaskState.SUBMITTED,
                "timestamp": datetime.now().isoformat()
            },
            "history": [original_message],
            "artifacts": [],
            "metadata": {
                "triage_token": None,
                "survey_id": None,
                "triage_state": "starting"
            },
            "kind": "task"
        }
        
        demographics = self._extract_demographics(user_text)
        age = demographics.get('age', 30)
        sex = demographics.get('sex', 'male')
        
        print(f"A2A-SERVICE: Starting triage with age={age}, sex={sex}")
        
        logger.error(f"DEBUG: user_text='{user_text}', demographics={demographics}, age={age}, sex={sex}")
        
        if not age or not sex:
            logger.error(f"Missing required demographics: age={age}, sex={sex}")
            return self._create_error_response(
                request_id, InvalidParamsError, InvalidParamsError.message
            )
        
        
        result = self._start_triage_session(age, sex, user_text, task)
        
        if result['success']:
            task['metadata'].update(result['metadata'])
            task['status']['state'] = TaskState.INPUT_REQUIRED
            
            agent_message = {
                "role": "agent",
                "parts": [{"kind": "text", "text": result['response']}],
                "messageId": str(uuid.uuid4()),
                "taskId": task_id,
                "contextId": context_id,
                "kind": "message"
            }
            task['history'].append(agent_message)
            task['status']['message'] = agent_message
            task['metadata']['triage_state'] = 'in_progress'
            
            print(f"A2A-SERVICE: Triage started successfully for task {task_id}")
            self.tasks[task_id] = task
            success_response= self._create_success_response(request_id, task)
            return {
                **success_response,
                "goto":"healthcare_voice_agent",
                "success":True,
                "action":"triage_started",
                "task_id":task_id
            }
        else:
            task['status']['state'] = TaskState.FAILED
            print(f"A2A-SERVICE: Triage start failed for task {task_id}")
            self.tasks[task_id] = task
            error_response= self._create_error_response(request_id, InternalError, InternalError.message)
            return {
                **error_response,
                "goto":"healthcare_voice_agent",
                "success":False,
                "error":True,
                "action":"triage_failed"
            }
    
    
    def _continue_existing_task(self, task_id, user_text, request_id, message):
        task = self.tasks[task_id]
        
        print(f"A2A-SERVICE: Continuing task {task_id}, current state: {task['status']['state']}")
        
        if task['status']['state'] in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
            print(f"A2A-SERVICE: Task {task_id} already in terminal state")
            error_response= self._create_error_response(request_id, TaskNotCancelableError , TaskNotCancelableError.message)
            return{
                **error_response,
                "goto":"healthcare_voice_agent",
                "success":False,
                "error":True,
                "action":"task_terminal_state"
            }
        
        task['history'].append(message)
        
        result = self._send_triage_message(task, user_text)
        
        if result['success']:
            agent_message = {
                "role": "agent",
                "parts": [{"kind": "text", "text": result['response']}],
                "messageId": str(uuid.uuid4()),
                "taskId": task_id,
                "contextId": task['contextId'],
                "kind": "message"
            }
            task['history'].append(agent_message)
            task['status']['message'] = agent_message
            
            
            external_state = result.get('state', 'in_progress')
            task['metadata']['triage_state'] = external_state
            
            print(f"A2A-SERVICE: External triage state: {external_state}")
            
           
            if external_state == 'present_result':
                print("A2A-SERVICE: Triage completed - changing to COMPLETED state")
                task['status']['state'] = TaskState.COMPLETED
              
                summary_result = self.triage_client._get_triage_summary(task)
                artifact_data = {
                    "urgency_level": summary_result.get('urgency_level', 'standard'),
                    "doctor_type": summary_result.get('doctor_type', 'general practitioner'),
                    "notes": summary_result.get('notes', 'Triage assessment completed'),
                    "completed_at": datetime.now().isoformat()
                }
                
                artifact = {
                    "artifactId": str(uuid.uuid4()),
                    "name": "Medical Triage Assessment",
                    "description": "Results from medical triage evaluation",
                    "parts": [
                        {
                            "kind": "data",
                            "data": artifact_data
                        }
                    ]
                }
                task['artifacts'] = [artifact]
                print(f"A2A-SERVICE: Task {task_id} COMPLETED with results")
                success_response = self._create_success_response(request_id,task)
                return{
                    **success_response,
                    "goto":"healthcare_voice_agent",
                    "success":True,
                    "action":"triage_completed",
                    "urgency_level":artifact_data["urgency_level"],
                    "doctor_type":artifact_data["doctor_type"]
                }
                
            elif external_state == 'in_progress':
                task['status']['state'] = TaskState.INPUT_REQUIRED
                print(f"A2A-SERVICE: Task {task_id} waiting for more input")
                success_response = self._create_success_response(request_id,task)
                return{
                    **success_response,
                    "goto":"healthcare_voice_agent",
                    "success":True,
                    "action":"triage_continuing"
                }
                
            elif external_state == 'post_result':
                print("A2A-SERVICE: WARNING - received post_result, task should already be completed")
                task['status']['state'] = TaskState.COMPLETED
                success_response = self._create_success_response(request_id,task)
                return{
                    **success_response,
                    "goto":"healthcare_voice_agent",
                    "success":True,
                    "action":"triage_post_result"
                }
                
            else:
                task['status']['state'] = TaskState.INPUT_REQUIRED
                success_response = self._create_success_response(request_id,task)
                return{
                    **success_response,
                    "goto":"healthcare_voice_agent",
                    "success":True,
                    "action":"triage_default_continue"
                }
                
        else:
            task['status']['state'] = TaskState.FAILED
            error_response = self._create_error_response(request_id, InternalError, InternalError.message)
            return{
                    **error_response,
                    "goto":"healthcare_voice_agent",
                    "success":False,
                    "error":True,
                    "action":"triage_message_failed"
                }
        
    @tool(name="extract_demographics")
    def _extract_demographics(self, text):
        """Extract age and sex from user input text"""
        demographics = {}
        
        # Age extraction patterns
        age_patterns = [
            r'\b(\d{1,2})\s*(?:years?\s*old|yo)\b',
            r'\bage\s*(?:is\s*)?(\d{1,2})\b',
            r'\bi\s*am\s*(\d{1,2})\b'
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, text.lower())
            if match:
                age = int(match.group(1))
                if 1 <= age <= 120:
                    demographics['age'] = age
                    break
        
        # Sex extraction
        text_lower = text.lower()
        if any(word in text_lower for word in ['male', 'man', 'boy', 'he', 'his', 'him']):
            demographics['sex'] = 'male'
        elif any(word in text_lower for word in ['female', 'woman', 'girl', 'she', 'her']):
            demographics['sex'] = 'female'
        
        return demographics
    
    @workflow(name="start_triage_session", description="start a new triage session with external API", version=1)
    def _start_triage_session(self, age, sex, complaint, task):
        """Start a new triage session with external API"""
        try:
            token = self.triage_client._get_triage_token()
            survey_id = self.triage_client._create_triage_survey(token, age, sex)
            
            initial_response = self.triage_client._send_triage_api_message(token, survey_id, complaint)
            
            return {
                'success': True,
                'response': initial_response.get('response', 'Medical triage session started. Please describe your symptoms.'),
                'metadata': {
                    'triage_token': token,
                    'survey_id': survey_id
                }
            }
        except Exception as e:
            logger.error(f"Error starting triage session: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    @tool(name="send_triage_message")
    def _send_triage_message(self, task, message):
        """Send message to external triage API"""
        try:
            token = task['metadata']['triage_token']
            survey_id = task['metadata']['survey_id']
            
            result = self.triage_client._send_triage_api_message(token, survey_id, message)
            return result
        except Exception as e:
            logger.error(f"Error sending triage message: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
        
    def _handle_tasks_get(self, params, request_id):
        """Handle tasks/get JSON-RPC method"""
        task_id = params.get('id')
        if not task_id or task_id not in self.tasks:
            logger.warning(f"Task not found: {task_id}")
            return self._create_error_response(request_id, TaskNotFoundError, TaskNotFoundError.message)
        
        task = self.tasks[task_id]
        history_length = params.get('historyLength', 10)
        
        # Limit history if requested
        if history_length and len(task.get('history', [])) > history_length:
            task_copy = task.copy()
            task_copy['history'] = task['history'][-history_length:]
            return self._create_success_response(request_id, task_copy)
        
        return self._create_success_response(request_id, task)
    
    def _handle_tasks_cancel(self, params, request_id):
        """Handle tasks/cancel JSON-RPC method"""
        task_id = params.get('id')
        if not task_id or task_id not in self.tasks:
            logger.warning(f"Task not found for cancellation: {task_id}")
            return self._create_error_response(request_id, TaskNotFoundError, TaskNotFoundError.message)
        
        task = self.tasks[task_id]
        
        # Check if task can be cancelled
        if task['status']['state'] in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
            logger.warning(f"Task {task_id} cannot be cancelled - in terminal state")
            return self._create_error_response(request_id, TaskNotCancelableError, TaskNotCancelableError.message)
        
        # Cancel the task
        task['status']['state'] = TaskState.CANCELED
        task['status']['timestamp'] = datetime.now().isoformat()
        
        return self._create_success_response(request_id, task)

    def run(self):
        """Run the Flask application"""
        
        # Run Flask app
        self.app.run(
            host=self.host,
            port=self.port,
            debug=self.debug,
            use_reloader=False
        )

