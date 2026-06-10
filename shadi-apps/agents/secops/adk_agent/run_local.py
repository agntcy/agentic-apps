import asyncio
import os
import sys
from pathlib import Path

from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT_DIR))

from agents.secops.skills import load_secops_config
from agents.shared.shadi_adk_memory import ShadiBackedMemoryService

APP_NAME = "shadi_secops"
USER_ID = os.getenv("SECOPS_USER_ID", "local-user")
SESSION_ID = os.getenv("SECOPS_SESSION_ID", "secops-session")
DEFAULT_QUERY = "Collect security issues for the allowlisted repos."


def build_query():
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    return DEFAULT_QUERY


async def run_local(query):
    session_service = InMemorySessionService()
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    tmp_dir = os.getenv("SHADI_TMP_DIR", "./.tmp")
    agent_id = (
        os.getenv("SHADI_AGENT_ID")
        or os.getenv("SHADI_OPERATOR_AGENT_ID")
        or os.getenv("SHADI_SECOPS_AGENT_ID")
    )
    if agent_id:
        tmp_dir = str(Path(tmp_dir) / agent_id)
    default_db = str(Path(tmp_dir) / "shadi-secops" / "secops_memory.db")
    memory_db = (
        os.getenv("SHADI_ADK_MEMORY_DB")
        or secops_config.get("memory_db")
        or default_db
    )
    memory_key = secops_config.get("memory_key", "secops/memory_key")
    memory_scope = secops_config.get("memory_scope", "secops")
    memory_entry_key = f"adk_memory/{APP_NAME}/{USER_ID}"
    memory_service = ShadiBackedMemoryService(
        app_name=APP_NAME,
        user_id=USER_ID,
        db_path=memory_db,
        key_name=memory_key,
        scope=memory_scope,
        entry_key=memory_entry_key,
    )

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )

    content = types.Content(role="user", parts=[types.Part(text=query)])
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            print(event.content.parts[0].text.strip())


if __name__ == "__main__":
    asyncio.run(run_local(build_query()))
