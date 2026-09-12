import os
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.tools import load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

SECOPS_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(SECOPS_DIR))

from skills import (
    get_llm_settings,
    load_secops_config,
    fetch_security_alerts,
    generate_security_report,
    remediate_vulnerabilities,
    approve_queued_prs,
    get_latest_report,
    get_allowlist,
    get_agent_status,
    lookup_cve,
)


def load_agent_context() -> str:
    parts = []
    for filename in ("AGENTS.md", "SKILL.md"):
        path = SECOPS_DIR / filename
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if content:
            parts.append(content)
    return "\n\n".join(parts)


async def auto_save_session_to_memory(callback_context):
    invocation = callback_context._invocation_context
    memory_service = invocation.memory_service
    session = invocation.session
    if memory_service is None or session is None:
        return
    await memory_service.add_session_to_memory(session)


config_path, config = load_secops_config()
llm_settings = get_llm_settings(config)

if llm_settings["provider"] == "google" and not llm_settings.get("openai_proxy"):
    os.environ["GOOGLE_API_KEY"] = llm_settings["api_key"]
    os.environ["ADK_GOOGLE_API_KEY_SOURCE"] = "shadi"
else:
    os.environ["OPENAI_API_KEY"] = llm_settings["api_key"]
    if llm_settings.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = llm_settings["base_url"]

model = os.getenv("ADK_MODEL") or llm_settings.get("adk_model") or llm_settings.get("model")
if not model:
    model = config.get("adk", {}).get("model", "gemini-3-flash-preview")

base_instruction = (
    "You are a SecOps agent. Use the collect_security_issues tool to gather open security "
    "issues and Dependabot alerts for the allowlisted repos. Use memory tools to recall "
    "prior summaries if they are relevant. Summarize counts and provide the report path."
)
context = load_agent_context()
if context:
    instruction = f"{base_instruction}\n\nContext:\n{context}"
else:
    instruction = base_instruction

root_agent = Agent(
    model=model,
    name="secops_agent",
    description="Collects security issues and Dependabot alerts for allowlisted repos.",
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        load_memory,
        fetch_security_alerts,
        generate_security_report,
        remediate_vulnerabilities,
        approve_queued_prs,
        get_latest_report,
        get_allowlist,
        get_agent_status,
        lookup_cve,
    ],
    after_agent_callback=auto_save_session_to_memory,
)
