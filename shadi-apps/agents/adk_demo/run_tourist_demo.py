import json
import os
import shlex
import sys
from pathlib import Path

from shadi import SandboxPolicyHandle, run_sandboxed


def main() -> int:
    apps_root = os.getenv("AGENTIC_APPS_PATH")
    if not apps_root:
        apps_root = str((Path(__file__).resolve().parents[2] / "agentic-apps"))
    if not apps_root:
        print("AGENTIC_APPS_PATH is required.")
        return 2

    app_dir = Path(apps_root) / "tourist_scheduling_system"
    if not app_dir.exists():
        print("tourist_scheduling_system not found at:", app_dir)
        return 2

    tourist_cmd = os.getenv("TOURIST_CMD")
    if not tourist_cmd:
        print("TOURIST_CMD is required (command to run the Tourist/Guide agent).")
        return 2

    policy_path = os.getenv("SHADI_POLICY_PATH", "sandbox.json")
    policy_file = Path(policy_path)
    if not policy_file.exists():
        print("Policy file not found:", policy_file)
        return 2

    try:
        policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("Policy file is not valid JSON:", exc)
        return 2

    policy = SandboxPolicyHandle()
    for path in policy_data.get("read", []) or []:
        policy.allow_read_path(path)
    for path in policy_data.get("write", []) or []:
        policy.allow_write_path(path)
    if policy_data.get("net_block") is not None:
        policy.block_network(bool(policy_data.get("net_block")))
    for path in policy_data.get("allow", []) or []:
        policy.allow_read_path(path)
        policy.allow_write_path(path)

    command = shlex.split(tourist_cmd)
    if not command:
        print("TOURIST_CMD is empty.")
        return 2

    print("Running:", " ".join(command))
    return run_sandboxed(
        command,
        policy,
        cwd=str(app_dir),
        inject_keychain=["TouristScheduler=SHADI_BROKER_SECRET"],
    )


if __name__ == "__main__":
    sys.exit(main())
