import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
from uuid import uuid4

from shadi import ShadiStore, PySessionContext


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


def load_secops_config():
    import tomllib
    from pathlib import Path
    config_path = Path(os.getenv("SHADI_SECOPS_CONFIG", "secops.toml"))
    if not config_path.exists():
        return config_path, {}
    with config_path.open("rb") as handle:
        return config_path, tomllib.load(handle)


def create_prompt_session():
    store = ShadiStore()
    agent_id = os.getenv("SHADI_OPERATOR_AGENT_ID", "shadi_prompt")
    presentation = os.getenv("SHADI_OPERATOR_PRESENTATION", "").encode("utf-8")
    if not presentation:
        raise RuntimeError("SHADI_OPERATOR_PRESENTATION must be set")
    session = PySessionContext(agent_id, "shadi-prompt-1")

    def verify_operator(verify_agent_id, session_id, presentation_bytes, claims):
        return verify_agent_id == agent_id and len(presentation_bytes) > 0

    store.set_verifier(verify_operator)
    ok = store.verify_session(session, presentation)
    if not ok:
        raise RuntimeError("Prompt session verification failed")
    return store, session


def require_shadi_secret_value(store, session, key_name, label):
    try:
        value = store.get(session, key_name)
    except Exception as exc:
        raise RuntimeError(f"Missing {label} in SHADI at key '{key_name}'.") from exc
    text = value.decode("utf-8").strip()
    if not text:
        raise RuntimeError(f"Missing {label} in SHADI at key '{key_name}'.")
    return text


def run_slimctl(args):
    if not shutil.which("slimctl"):
        print("slimctl not found. Install it to discover channels.")
        return
    try:
        result = subprocess.run(
            ["slimctl"] + args,
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        print("slimctl error:", exc.stderr.strip() or exc.stdout.strip())


async def build_client(types, endpoint, local_identity, remote_identity, shared_secret, insecure):
    httpx_client = types["httpx"].AsyncClient()
    slimrpc = types["slimrpc"]

    slim_app = await slimrpc.common.create_local_app(
        slimrpc.SLIMAppConfig(
            identity=local_identity,
            slim_client_config={
                "endpoint": endpoint,
                "tls": {"insecure": bool(insecure)},
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


async def send_message(types, client, text):
    request = types["Message"](
        role=types["Role"].user,
        message_id=str(uuid4()),
        parts=[types["Part"](root=types["TextPart"](text=text))],
    )
    output = ""
    async for response in client.send_message(request=request):
        if isinstance(response, types["Message"]):
            for part in response.parts:
                if isinstance(part.root, types["TextPart"]):
                    output += part.root.text
        else:
            task, _ = response
            if task.status.state == "completed" and task.artifacts:
                for artifact in task.artifacts:
                    for part in artifact.parts:
                        if isinstance(part.root, types["TextPart"]):
                            output += part.root.text
    return output


def prompt_help():
    return (
        "Commands:\n"
        "  :help                  Show this help\n"
        "  :exit                  Exit the prompt\n"
        "  :use <remote_did>       Set remote agent DID\n"
        "  :channels [node_id]     List SLIM nodes or connections via slimctl\n"
        "  :routes <node_id>       List SLIM routes via slimctl\n"
        "  :commands               Ask agent for available commands\n"
        "  <text>                  Send free-text to the agent\n"
    )


async def main():
    logging.getLogger("a2a.utils.telemetry").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(description="SHADI SLIM A2A prompt")
    parser.add_argument("--endpoint", default=os.getenv("SHADI_SLIM_ENDPOINT", "http://localhost:46357"))
    parser.add_argument("--local-did", default=os.getenv("SHADI_SLIM_LOCAL_DID", "did:slim:local-user"))
    parser.add_argument("--remote-did", default=os.getenv("SHADI_SLIM_REMOTE_DID", ""))
    parser.add_argument("--secret-key", default="secops/slim_shared_secret")
    parser.add_argument("--insecure", action="store_true", default=True)
    args = parser.parse_args()

    if not args.remote_did:
        print("Remote DID is required. Use --remote-did or SHADI_SLIM_REMOTE_DID.")
        return

    types = require_slima2a_packages()
    store, session = create_prompt_session()
    shared_secret = require_shadi_secret_value(store, session, args.secret_key, "SLIM shared secret")

    client, httpx_client = await build_client(
        types,
        endpoint=args.endpoint,
        local_identity=args.local_did,
        remote_identity=args.remote_did,
        shared_secret=shared_secret,
        insecure=args.insecure,
    )

    print("SHADI prompt connected.")
    print(prompt_help())

    try:
        while True:
            line = input("shadi> ").strip()
            if not line:
                continue
            if line in (":exit", "exit", "quit"):
                break
            if line in (":help", "help", "?"):
                print(prompt_help())
                continue
            if line.startswith(":use "):
                args.remote_did = line.split(" ", 1)[1].strip()
                client, httpx_client = await build_client(
                    types,
                    endpoint=args.endpoint,
                    local_identity=args.local_did,
                    remote_identity=args.remote_did,
                    shared_secret=shared_secret,
                    insecure=args.insecure,
                )
                print(f"Remote DID set to {args.remote_did}")
                continue
            if line.startswith(":channels"):
                parts = line.split()
                if len(parts) == 1:
                    run_slimctl(["node", "list"])
                else:
                    run_slimctl(["connection", "list", "--node-id", parts[1]])
                continue
            if line.startswith(":routes"):
                parts = line.split()
                if len(parts) < 2:
                    print("Usage: :routes <node_id>")
                else:
                    run_slimctl(["route", "list", "--node-id", parts[1]])
                continue
            if line in (":commands", ":skills"):
                payload = json.dumps({"command": "help"})
                output = await send_message(types, client, payload)
                print(output)
                continue

            output = await send_message(types, client, line)
            print(output)
    finally:
        await httpx_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
