import asyncio
import json
import os
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent

from shadi import ShadiStore, PySessionContext

AVATAR_DIR = Path(__file__).resolve().parents[1]
SECOPS_DIR = Path(__file__).resolve().parents[2] / "secops"
sys.path.append(str(SECOPS_DIR))

from skills import get_llm_settings, load_secops_config


def load_agent_context() -> str:
    path = AVATAR_DIR / "AGENTS.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def require_slima2a_packages():
    try:
        import httpx
        import slimrpc
        from a2a.client import ClientFactory, minimal_agent_card
        from a2a.types import Message, Part, Role, TextPart
        from slima2a.client_transport import ClientConfig, SRPCTransport, slimrpc_channel_factory
    except ImportError as exc:
        raise RuntimeError(
            "Missing SLIM A2A dependencies. Install: uv pip install slima2a slimrpc a2a httpx"
        ) from exc

    return {
        "httpx": httpx,
        "slimrpc": slimrpc,
        "ClientFactory": ClientFactory,
        "minimal_agent_card": minimal_agent_card,
        "Message": Message,
        "Part": Part,
        "Role": Role,
        "TextPart": TextPart,
        "ClientConfig": ClientConfig,
        "SRPCTransport": SRPCTransport,
        "slimrpc_channel_factory": slimrpc_channel_factory,
    }


def create_avatar_session():
    store = ShadiStore()
    agent_id = os.getenv("SHADI_AVATAR_AGENT_ID", "avatar_agent")
    presentation = os.getenv("SHADI_OPERATOR_PRESENTATION", "").encode("utf-8")
    if not presentation:
        raise RuntimeError("SHADI_OPERATOR_PRESENTATION must be set")
    session = PySessionContext(agent_id, "avatar-session-1")

    def verify_operator(verify_agent_id, session_id, presentation_bytes, claims):
        return verify_agent_id == agent_id and len(presentation_bytes) > 0

    store.set_verifier(verify_operator)
    ok = store.verify_session(session, presentation)
    if not ok:
        raise RuntimeError("Avatar verification failed")
    return store, session


def require_shadi_secret_value(store, session, key_name, label):
    env_var = "SHADI_SECRET_" + key_name.upper().replace("/", "_").replace("-", "_").replace(".", "_")
    env_val = os.getenv(env_var, "").strip()
    if env_val:
        return env_val
    try:
        value = store.get(session, key_name)
    except Exception as exc:
        raise RuntimeError(f"Missing {label} in SHADI at key '{key_name}'.") from exc
    text = value.decode("utf-8").strip()
    if not text:
        raise RuntimeError(f"Missing {label} in SHADI at key '{key_name}'.")
    return text


def resolve_slim_config():
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    store, session = create_avatar_session()
    secret_key = secops_config.get("slim_shared_secret_key", "secops/slim_shared_secret")
    shared_secret = require_shadi_secret_value(store, session, secret_key, "SLIM shared secret")
    tls_insecure = bool(secops_config.get("slim_tls_insecure", True))
    tls_cert = os.getenv("SLIM_TLS_CERT", "").strip()
    tls_key = os.getenv("SLIM_TLS_KEY", "").strip()
    tls_ca = os.getenv("SLIM_TLS_CA", "").strip()
    if not tls_insecure and (not tls_cert or not tls_key or not tls_ca):
        raise RuntimeError("SLIM mTLS requires SLIM_TLS_CERT, SLIM_TLS_KEY, and SLIM_TLS_CA")
    return {
        "endpoint": secops_config.get("slim_endpoint", "http://localhost:47357"),
        "remote_identity": secops_config.get("slim_identity", "agntcy/secops/agent"),
        "local_identity": os.getenv("SHADI_AVATAR_IDENTITY", "agntcy/avatar/client"),
        "shared_secret": shared_secret,
        "insecure": tls_insecure,
        "tls_cert": tls_cert,
        "tls_key": tls_key,
        "tls_ca": tls_ca,
    }


_CLIENT_CACHE = {
    "config_key": None,
    "client": None,
    "httpx_client": None,
}


async def build_client(types, endpoint, local_identity, remote_identity, shared_secret, insecure):
    httpx_client = types["httpx"].AsyncClient()
    slimrpc = types["slimrpc"]

    tls_config = {
        "insecure": bool(insecure),
    }
    if not insecure:
        tls_config["source"] = {
            "type": "file",
            "cert": os.getenv("SLIM_TLS_CERT", "").strip(),
            "key": os.getenv("SLIM_TLS_KEY", "").strip(),
        }
        tls_config["ca_source"] = {
            "type": "file",
            "path": os.getenv("SLIM_TLS_CA", "").strip(),
        }

    slim_app = await slimrpc.common.create_local_app(
        slimrpc.SLIMAppConfig(
            identity=local_identity,
            slim_client_config={
                "endpoint": endpoint,
                "tls": tls_config,
            },
            shared_secret=shared_secret,
        )
    )
    client_config = types["ClientConfig"](
        supported_transports=["JSONRPC", "slimrpc"],
        streaming=True,
        httpx_client=httpx_client,
        slimrpc_channel_factory=types["slimrpc_channel_factory"](slim_app),
    )
    factory = types["ClientFactory"](client_config)
    factory.register("slimrpc", types["SRPCTransport"].create)
    agent_card = types["minimal_agent_card"](remote_identity, ["slimrpc"])
    client = factory.create(card=agent_card)
    return client, httpx_client


async def get_cached_client(types, config):
    config_key = (
        config["endpoint"],
        config["local_identity"],
        config["remote_identity"],
        config["shared_secret"],
        config["insecure"],
        config.get("tls_cert"),
        config.get("tls_key"),
        config.get("tls_ca"),
    )
    if _CLIENT_CACHE["client"] and _CLIENT_CACHE["config_key"] == config_key:
        return _CLIENT_CACHE["client"], _CLIENT_CACHE["httpx_client"]

    if _CLIENT_CACHE["httpx_client"]:
        await _CLIENT_CACHE["httpx_client"].aclose()

    client, httpx_client = await build_client(
        types,
        endpoint=config["endpoint"],
        local_identity=config["local_identity"],
        remote_identity=config["remote_identity"],
        shared_secret=config["shared_secret"],
        insecure=config["insecure"],
    )
    _CLIENT_CACHE["config_key"] = config_key
    _CLIENT_CACHE["client"] = client
    _CLIENT_CACHE["httpx_client"] = httpx_client
    return client, httpx_client


async def send_message(types, client, text):
    request = types["Message"](
        role=types["Role"].user,
        message_id="avatar-message",
        parts=[types["Part"](root=types["TextPart"](text=text))],
    )
    TERMINAL_STATES = {"completed", "failed", "canceled"}
    output = ""
    async for response in client.send_message(request=request):
        print(f"[send_message] response type={type(response).__name__}", flush=True)
        if isinstance(response, types["Message"]):
            for part in response.parts:
                if isinstance(part.root, types["TextPart"]):
                    output += part.root.text
        else:
            task, _ = response
            state = task.status.state.value if task.status and hasattr(task.status.state, "value") else str(task.status.state) if task.status else ""
            print(f"[send_message] task.state={state} artifacts={len(task.artifacts) if task.artifacts else 0}", flush=True)
            if state in TERMINAL_STATES and task.artifacts:
                for artifact in task.artifacts:
                    for part in artifact.parts:
                        if isinstance(part.root, types["TextPart"]):
                            output += part.root.text
    return output


def format_secops_error(exc):
    messages = []
    current = exc
    visited = set()
    while current and id(current) not in visited:
        visited.add(id(current))
        message = str(current).strip()
        if message:
            messages.append(message)
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

    combined = " | ".join(messages)
    if "session handshake failed" in combined:
        return (
            "SecOps connection failed during SLIM session handshake. "
            "Check that the SecOps A2A server is running and that Avatar and SecOps use the same "
            "SLIM endpoint, identity, shared secret, and TLS settings."
        )
    return str(exc)


def normalize_secops_payload(payload):
    if isinstance(payload, dict):
        return json.dumps(payload)
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                return json.dumps(data)
        except json.JSONDecodeError:
            pass
        return json.dumps({"command": payload.strip()})
    return json.dumps({"command": str(payload).strip()})


async def send_secops_command(payload):
    normalized = normalize_secops_payload(payload)
    print(f"[send_secops_command] payload={normalized}", flush=True)
    try:
        types = require_slima2a_packages()
        config = resolve_slim_config()
        client, _httpx_client = await get_cached_client(types, config)
        result = await send_message(types, client, normalized)
        print(f"[send_secops_command] result={result!r}", flush=True)
        return result
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return f"ERROR calling SecOps: {format_secops_error(exc)}"


config_path, config = load_secops_config()
avatar_store, avatar_session = create_avatar_session()
llm_settings = get_llm_settings(config, store=avatar_store, session=avatar_session)

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
    "You are Avatar, a human interface agent. Convert the user request into a JSON command "
    "for the SecOps agent and send it using the send_secops_command tool. The SecOps agent "
    "accepts commands: scan, remediate, approve_prs, report, and help. Optional JSON fields: "
    "provider, labels, report_name, create_prs, human_github. "
    "Use the 'repos' field (comma-separated owner/name string) to scope scan or remediate to "
    "specific repositories — for example if the user says 'remediate agentic-apps' set "
    "'repos': 'agntcy/agentic-apps'. When no specific repo is mentioned, omit repos. "
    "Always send valid JSON. Reply with the SecOps response."
)
context = load_agent_context()
if context:
    instruction = f"{base_instruction}\n\nContext:\n{context}"
else:
    instruction = base_instruction

root_agent = Agent(
    model=model,
    name="avatar_agent",
    description="Human interface agent that routes commands to SecOps over SLIM A2A.",
    instruction=instruction,
    tools=[send_secops_command],
)
