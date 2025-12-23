# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

try:
    script_dir = Path(__file__).resolve().parent
    voice_agent_dir = script_dir.parent
    app_dir = script_dir.parent.parent
except (NameError, AttributeError):
    app_home = os.getenv('APP_HOME', '/Users/xiaodonz/Documents/GitHub/cs1')
    app_dir = Path(app_home) / 'agentic-healthcare-booking-app'
    voice_agent_dir = app_dir / 'voice_agent'

common_dir = app_dir / 'common'
observe_dir = app_dir.parent / 'observe'

if common_dir.exists():
    sys.path.insert(0, str(common_dir.resolve()))
if voice_agent_dir.exists():
    sys.path.insert(0, str(voice_agent_dir.resolve()))
if observe_dir.exists():
    sys.path.insert(0, str(observe_dir.resolve()))

if 'agntcy' in sys.modules:
    agntcy_module = sys.modules['agntcy']
    if hasattr(agntcy_module, '__file__') and agntcy_module.__file__:
        if 'voice_agent' in str(agntcy_module.__file__):
            del sys.modules['agntcy']
            modules_to_remove = [k for k in sys.modules.keys() if k.startswith('agntcy.')]
            for k in modules_to_remove:
                del sys.modules[k]

voice_agent_path = str(voice_agent_dir.resolve())
if voice_agent_path not in sys.path:
    sys.path.insert(0, voice_agent_path)

import importlib.util
observe_config_path = common_dir / 'agntcy' / 'observe' / 'observe_config.py'
if observe_config_path.exists():
    spec = importlib.util.spec_from_file_location("observe_config", observe_config_path)
    observe_config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observe_config_module)
    initialize_observability = observe_config_module.initialize_observability
else:
    raise ImportError(f"observe_config.py not found at {observe_config_path}")

from agntcy.agent.healthcare_agent import HealthcareAgent
from agntcy.services.audio_service import AUDIO_AVAILABLE

load_dotenv()

def get_missing_env_vars(required_vars):
    return (var for var in required_vars if not os.getenv(var))

def run_agent():
    print("=" * 50)
    print("HEALTHCARE VOICE + A2A + MCP AGENT")
    print("=" * 50)

    service_name = "Healthcare_Voice_Agent"
    initialize_observability(service_name)
    
    jwt_required = ['JWT_TOKEN', 'ENDPOINT_URL', 'PROJECT_ID', 'CONNECTION_ID']
    insurance_required = ['MCP_URL', 'X_INF_API_KEY']
    a2a_required = ['A2A_SERVICE_URL', 'A2A_MESSAGE_URL', 'A2A_API_KEY']
    
    missing = []
    missing.extend(get_missing_env_vars(jwt_required))
    missing.extend(get_missing_env_vars(insurance_required))
    missing.extend(get_missing_env_vars(a2a_required))
    
    if missing:
        print(f"ERROR: Missing config: {missing}")
        return
    
    print("Configuration validated")
    
    if AUDIO_AVAILABLE:
        print("Audio system available - Triage conversation integrated")
    else:
        print("Console mode only")
    
    async def start():
        try:
            agent = HealthcareAgent()
            await agent.start()
        except KeyboardInterrupt:
            print("\nAgent stopped by user")
        except Exception as e:
            print(f"Agent error: {e}")
    
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("\nShutting down...")

def main():
    run_agent()

if __name__ == "__main__":
    main()