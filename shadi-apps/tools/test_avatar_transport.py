"""Quick test: send commands to SecOps via SLIM without the LLM."""
import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/avatar/adk_agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/secops"))

from agent import (
    build_client,
    require_slima2a_packages,
    resolve_slim_config,
)

TERMINAL_STATES = {"completed", "failed", "canceled"}


async def send_command(client, types, command_json):
    request = types["Message"](
        role=types["Role"].user,
        message_id="test-cmd",
        parts=[types["Part"](root=types["TextPart"](text=command_json))],
    )
    output = ""
    async for response in client.send_message(request=request):
        if isinstance(response, types["Message"]):
            for part in response.parts:
                if isinstance(part.root, types["TextPart"]):
                    output += part.root.text
        else:
            task, _ = response
            state = task.status.state.value if task.status and hasattr(task.status.state, "value") else str(task.status.state)
            if state in TERMINAL_STATES and task.artifacts:
                for artifact in task.artifacts:
                    for part in artifact.parts:
                        if isinstance(part.root, types["TextPart"]):
                            output += part.root.text
    return output


async def main():
    types = require_slima2a_packages()
    config = resolve_slim_config()
    print("config:", {k: v for k, v in config.items() if k != "shared_secret"}, flush=True)

    client, _ = await asyncio.wait_for(
        build_client(
            types,
            endpoint=config["endpoint"],
            local_identity=config["local_identity"],
            remote_identity=config["remote_identity"],
            shared_secret=config["shared_secret"],
            insecure=config["insecure"],
        ),
        timeout=10,
    )
    print("SLIM client built OK", flush=True)

    cmd = sys.argv[1] if len(sys.argv) > 1 else '{"command":"status"}'
    print(f"Sending: {cmd}", flush=True)
    result = await send_command(client, types, cmd)
    print("RESULT:", result[:1000] if result else "(empty)")


if __name__ == "__main__":
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=timeout))
    except asyncio.TimeoutError:
        print(f"TIMEOUT: no response from SecOps within {timeout}s", flush=True)
    except Exception:
        traceback.print_exc()

