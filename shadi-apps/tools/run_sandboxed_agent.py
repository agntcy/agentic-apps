import argparse
import json
import os
import sys
from pathlib import Path

from shadi import SandboxPolicyHandle, run_sandboxed
from telemetry import tracer


def load_policy(policy_path: str) -> tuple[SandboxPolicyHandle, dict]:
    policy_file = Path(policy_path)
    if not policy_file.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_file}")
    with tracer.start_as_current_span("shadi.policy.load") as span:
        span.set_attribute("policy.source", str(policy_file))
        try:
            policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Policy file is not valid JSON: {exc}") from exc

        allowed_paths = set()
        for path in policy_data.get("read", []) or []:
            allowed_paths.add(str(path))
        for path in policy_data.get("write", []) or []:
            allowed_paths.add(str(path))
        for path in policy_data.get("allow", []) or []:
            allowed_paths.add(str(path))
        span.set_attribute("policy.allowed_paths.count", len(allowed_paths))
        network_mode = "blocked" if policy_data.get("net_block") else "allowed"
        span.set_attribute("network.mode", network_mode)

    policy = SandboxPolicyHandle()
    for path in policy_data.get("read", []) or []:
        policy.allow_read_path(path)
    for path in policy_data.get("write", []) or []:
        policy.allow_write_path(path)
    for path in policy_data.get("allow", []) or []:
        policy.allow_read_path(path)
        policy.allow_write_path(path)
    if policy_data.get("net_block") is not None:
        policy.block_network(bool(policy_data.get("net_block")))
    return policy, policy_data


def build_env(policy_data: dict) -> dict | None:
    allowlist = policy_data.get("net_allow", []) or []
    if not allowlist:
        return None

    env = dict(os.environ)
    env["SHADI_NET_ALLOWLIST"] = ",".join(str(item) for item in allowlist)

    tools_dir = str(Path(__file__).resolve().parent)
    existing = env.get("PYTHONPATH", "")
    if existing:
        env["PYTHONPATH"] = f"{tools_dir}{os.pathsep}{existing}"
    else:
        env["PYTHONPATH"] = tools_dir

    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a command inside the SHADI sandbox using a JSON policy."
    )
    parser.add_argument("--policy", required=True, help="Path to JSON policy file")
    parser.add_argument("--cwd", help="Working directory for the command")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("Command required after '--'", file=sys.stderr)
        return 2

    try:
        policy, policy_data = load_policy(args.policy)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    allowed_paths = set()
    for path in policy_data.get("read", []) or []:
        allowed_paths.add(str(path))
    for path in policy_data.get("write", []) or []:
        allowed_paths.add(str(path))
    for path in policy_data.get("allow", []) or []:
        allowed_paths.add(str(path))
    network_mode = "blocked" if policy_data.get("net_block") else "allowed"

    env = build_env(policy_data)
    with tracer.start_as_current_span("shadi.sandbox.run") as span:
        span.set_attribute("command", " ".join(command))
        span.set_attribute("cwd", args.cwd or str(Path.cwd()))
        span.set_attribute("policy.source", args.policy)
        span.set_attribute("policy.allowed_paths.count", len(allowed_paths))
        span.set_attribute("network.mode", network_mode)
        exit_code = run_sandboxed(command, policy, cwd=args.cwd, env=env)
        span.set_attribute("exit.code", exit_code)
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
