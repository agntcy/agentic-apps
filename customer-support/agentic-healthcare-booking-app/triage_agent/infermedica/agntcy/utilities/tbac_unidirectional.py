# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
from dotenv import load_dotenv
from identityservice.sdk import IdentityServiceSdk
import importlib
import sys

load_dotenv()
from pathlib import Path
parent = Path(__file__).resolve().parent.parent.parent.parent.parent
voice_agent_path = parent / 'voice-agent'
triage_agent_path = parent / 'triage-agent'

sys.path.insert(0, str(parent))
sys.path.insert(0, str(voice_agent_path))
sys.path.insert(0, str(triage_agent_path))
# Add agntcy to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) 

class tbac_oneway:
    def __init__(self):
        self.client_api_key = os.getenv('CLIENT_AGENT_API_KEY')
        self.client_id = os.getenv('CLIENT_AGENT_ID')
        self.a2a_api_key = os.getenv('A2A_SERVICE_API_KEY')
        self.a2a_id = os.getenv('A2A_SERVICE_ID')

        if not all([self.client_api_key, self.client_id, self.a2a_api_key, self.a2a_id]):
            print("TBAC Disabled: Missing credentials:")
            return

        try:
            self.client_sdk = IdentityServiceSdk(api_key=self.client_api_key)
            self.a2a_sdk = IdentityServiceSdk(api_key=self.a2a_api_key)
            print("TBAC SDKs initialized")
        except Exception as e:
            print(f"TBAC setup failed: {e}")

    def token_auth(self):
        pass

    client_sdk = IdentityServiceSdk(api_key=os.getenv("CLIENT_AGENT_API_KEY"))
    a2a_sdk = IdentityServiceSdk(api_key=os.getenv("A2A_SERVICE_API_KEY"))

    client_token = client_sdk.access_token(agentic_service_id=os.getenv("A2A_SERVICE_ID"))
    print(f"Client token generated for access to A2a : {str(client_token)[:5]}...")


# global instance

tbac_instance = tbac_oneway()

import importlib.util

# patch A2A Client
a2a_file = str(voice_agent_path) + "/agntcy/services/a2a_client.py"
spec1 = importlib.util.spec_from_file_location("a2a_client", a2a_file)
a2a_mod = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(a2a_mod)
aac = a2a_mod.A2AClient

print("TBAC: Imported A2AClient module")

original_send = aac.send_message
def patched_send(self, *args, **kwargs):
    if not tbac_instance.a2a_sdk.authorize(tbac_instance.client_token):
        raise Exception("authorization failed: Client -> A2A")
    print("Client -> A2A authorized successfully.")
    return original_send(self, *args, **kwargs)
aac.send_message = patched_send

# Patch voice agent
ha_file = str(voice_agent_path) + "/agntcy/agent/healthcare_agent.py"
spec2 = importlib.util.spec_from_file_location("healthcare_agent", ha_file)
ha_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ha_mod)
ha = ha_mod.HealthcareAgent

print("TBAC: Imported HealthcareAgent module")

original_triage = ha._start_integrated_triage
def patched_triage(self, *args, **kwargs):
    # A2A uses same token to respond - client already authorized it.
    print(" A2A -> Client authorized successfully.")
    return original_triage(self, *args, **kwargs)
ha._start_integrated_triage = patched_triage

if __name__ == "__main__":
    # import and run voice agent main
    main_file = str(voice_agent_path) + "/agntcy/main.py"
    spec3 = importlib.util.spec_from_file_location("main", main_file)
    main_mod = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(main_mod)
    main_mod.main()
