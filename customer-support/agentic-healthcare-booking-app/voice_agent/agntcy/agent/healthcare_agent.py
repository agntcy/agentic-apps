# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import time
import random
import string
import sys
from pathlib import Path
from ioa_observe.sdk.decorators import agent, workflow
from ioa_observe.sdk.metrics.agents.availability import agent_availability
from agntcy.models.session import Session
from agntcy.services.llm_client import LLMClient
from agntcy.services.audio_service import AudioSystem
from agntcy.services.a2a_client import A2AClient
from agntcy.services.insurance_client import InsuranceClient
from dotenv import load_dotenv

# Try to import TaskState from a2a, fallback if not available
try:
    from a2a.types import TaskState
except ImportError:
    # Define TaskState enum if not available
    from enum import Enum
    class TaskState(Enum):
        COMPLETED = "completed"
        INPUT_REQUIRED = "input_required"
        FAILED = "failed"
        CANCELED = "canceled"
load_dotenv()

@agent(name="healthcare_agent", description="healthcare voice agent", version="1.0.0", protocol="A2A")
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
        from ioa_observe.sdk.metrics.agents.availability import agent_availability
        start = time.time()
        agent_availability.record_agent_heartbeat("healthcare_voice_agent")
        observe_latency = time.time() - start
        print(f"Observe heartbeat latency: {observe_latency:.2f} seconds")
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
            if turn %5 ==0:
                agent_availability.record_agent_heartbeat("healthcare_voice_agent")
            
            user_input = await self.audio.listen(timeout=5)
            
            if user_input in ["UNCLEAR", "TIMEOUT", "ERROR"]:
                errors += 1
                agent_availability.record_agent_activity("healthcare_voice_agent", success=False)
                if user_input == "TIMEOUT":
                    await self.audio.speak("I'm still here. What would you like me to help you with?")
                else:
                    await self.audio.speak("I didn't catch that clearly. Could you please repeat?")
                continue
            agent_availability.record_agent_activity("healthcare_voice_agent", success=True)
            
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
    
    @workflow(name="integrated_triage_workflow")
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
                return {
                    "goto":"__end__",
                    "error":True,
                    "success":False,
                    "reason":"triage_start_failed"
                }
            
            if result.get('kind') == 'task':
                self.session.triage_task_id = result['id']
                self.session.triage_context_id = result['contextId']
                
                print(f"TRIAGE: Started task {self.session.triage_task_id}")
                
                if result['status'].get('message'):
                    triage_question = self._extract_text_from_message(result['status']['message'])
                    if triage_question:
                        await self.audio.speak(triage_question)
                        self.session.add_interaction("assistant", triage_question)
                return {
                    "goto": "triage_service_agent",
                    "success": True,
                    "task_id" : result['id'],
                    "context_id":result['contextId'],
                    "action":"triage_started"
                }
                
        except Exception as e:
            print(f"TRIAGE: Error starting: {e}")
            await self._end_triage_mode("Let me help you schedule your appointment.")
            return{
                "goto":"__end__",
                "error":True,
                "success":False,
                "error_message":str(e)
            }
    
    @workflow(name="triage_conversational_flow")
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
                return{
                    "goto":"__end__",
                    "error":True,
                    "success":False,
                    "reason":"triage_communication_failed"
                }
            
            task_data = result.get('a2a_response', result)
            task_state = result['status']['state']
            print(f"TRIAGE: A2A task state: {task_state}")
            
            if task_state == TaskState.COMPLETED:
                print("TRIAGE: Assessment COMPLETED - exiting A2A mode")
                
                if task_data.get('artifacts'):
                    artifact = task_data['artifacts'][0]
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
                
                return {
                    "goto":"__end__",
                    "success":True,
                    "triage_complete":True,
                    "urgency_level":urgency,
                    "doctor_type":doctor_type
                }
                
            elif task_state == TaskState.INPUT_REQUIRED:
                if result['status'].get('message'):
                    next_question = self._extract_text_from_message(result['status']['message'])
                    if next_question:
                        await self.audio.speak(next_question)
                        self.session.add_interaction("assistant", next_question)
                    return {
                        "goto":"triage_service_agent",
                        "success":True,
                        "action":"continue_triage",
                        "state":"awaiting_user_input"
                    }
                else:
                    print("TRIAGE: No message in input-required state - ending triage")
                    await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
                    return {
                        "goto":"__end__",
                        "error":True,
                        "success":False,
                        "reason":"no_triage_message"
                    }

            elif task_state in [TaskState.FAILED, TaskState.CANCELED]:
                print(f"TRIAGE: Task ended with state: {task_state}")
                await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
                return {
                    "goto":"__end__",
                    "error":True,
                    "success":False,
                    "task_state":task_state
                }

        except Exception as e:
            print(f"TRIAGE: Error in conversation: {e}")
            await self._end_triage_mode("Let me help you continue with scheduling your appointment.")
            return {
                "goto":"__end__",
                "error":True,
                "success":False,
                "error_message":str(e)
            }
    
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