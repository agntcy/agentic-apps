# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import sys
from dotenv import load_dotenv
from identityservice.sdk import IdentityServiceSdk  
import importlib

load_dotenv()

from pathlib import Path
parent = Path(__file__).resolve().parent.parent.parent.parent.parent
print(f"debug: {parent}")
voice_agent_path = parent / 'voice-agent'
print(f"debug: {voice_agent_path}")
triage_agent_path = parent / 'triage-agent'

sys.path.insert(0, str(parent))
sys.path.insert(0, str(voice_agent_path))
sys.path.insert(0, str(triage_agent_path))
# Add agntcy to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) 

from common.tbac import TBAC

# global TBAC instance
tbac = TBAC()

# import and patch
try:
    import importlib.util

    # import and patch A2A Client
    spec1 = importlib.util.spec_from_file_location("a2a_client", voice_agent_path / "agntcy/services/a2a_client.py")
    print(f"looking for {voice_agent_path / "agntcy/services/a2a_client.py"}")
    a2a_mod = importlib.util.module_from_spec(spec1)
    spec1.loader.exec_module(a2a_mod)
    aac = a2a_mod.A2AClient

    print("TBAC: Imported A2AClient module")

    original_send = aac.send_message

    async def patched_send(self, message_parts, task_id=None, context_id=None):
        if not tbac.is_client_authorized():
            print("TBAC: Voice agent not authorized to send message to A2A")
            return None
        return await original_send(self, message_parts, task_id, context_id)
    aac.send_message = patched_send
    print("TBAC: Patched A2AClient.send_message with authorization check")
    
    # import and patch A2A service
    
    spec2 = importlib.util.spec_from_file_location("triage_service", triage_agent_path/ "agntcy/service/triage_service.py")
    triage_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(triage_mod)
    aas=triage_mod.A2ATriageService

    print("TBAC: Imported A2AService module")

    original_handle = aas._handle_message_send

    def patched_handle(self, params, request_id):
        if not tbac.is_a2a_authorized():
            print("TBAC: A2A service not authorized to handle messages")
            return {"error": "A2A service blocked"}
        return original_handle(self, params, request_id)
    aas._handle_message_send = patched_handle
    print("TBAC: Patched A2ATriageService._handle_message_send with authorization check")

    # import and Patch voice agent

    spec3 = importlib.util.spec_from_file_location("healthcare_agent", voice_agent_path / "agntcy/agent/healthcare_agent.py")
    h_mod = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(h_mod)
    ha = h_mod.HealthcareAgent

    print("TBAC: Imported HealthcareAgent module")

    original_triage = ha.HealthcareAgent._start_integrated_triage

    async def patched_triage(self, message):
        if not tbac.is_client_authorized():
            print("TBAC: Triage blocked")
            return {"error": "Medical Triage is not available."}
        return await original_triage(self, message)
    ha.HealthcareAgent.process_message = patched_triage
    print("TBAC: Patched VoiceAgent.process_message with authorization check")

except ImportError:
    print("TBAC: Import Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def run_tbac():
    print("Running with bidirectional TBAC...")

    # import main modules using spec_from_file_location
    voice_main_file = str(voice_agent_path) + "/agntcy/main.py"
    spec_vm = importlib.util.spec_from_file_location("voice_main", voice_main_file)
    m1= importlib.util.module_from_spec(spec_vm)
    spec_vm.loader.exec_module(m1)

    triage_main_file = str(triage_agent_path) + "/infermedica/agntcy/main.py"
    spec_tm = importlib.util.spec_from_file_location("triage_main", triage_main_file)
    m2= importlib.util.module_from_spec(spec_tm)
    spec_tm.loader.exec_module(m2)

    # authorize first
    if not tbac.authorize_bidirectional():
        print("TBAC authorization failed - running without TBAC")
        print(f"Voice authorized: {tbac.is_voice_authorized()}")
        print(f"A2A authorized: {tbac.is_a2a_authorized()}")

    # run service or agent
    if len(sys.argv) > 1 and sys.argv[1] == 'service':
            m2.main()
    elif len(sys.argv) > 1 and sys.argv[1] == 'agent':
            m1.run_agent()

if __name__ == "__main__":
    run_tbac()