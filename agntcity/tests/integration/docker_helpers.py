# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import time
from typing import Optional, Tuple
import json
from typing import List
import subprocess
from pathlib import Path

# If you always run from the lungo dir, set it once:
PROJECT_DIR = Path(__file__).resolve().parents[2]  # .../coffee_agents/lungo

def _compose_cmd(files: List[str]) -> List[str]:
    """
    Build a docker compose command ensuring:
      - All compose file paths are absolute (rooted at PROJECT_DIR) so invocation
        location does not matter.
    """
    cmd = ["docker", "compose"]
    for f in files:
        if f.strip():
            # Normalize relative compose file references to absolute paths
            compose_file = (PROJECT_DIR / f.strip()).resolve()
            cmd += ["-f", str(compose_file)]
    return cmd

def _run(cmd: List[str]):
    """
    Execute a docker compose command from PROJECT_DIR to make calls location-agnostic.
    """
    print(">", " ".join(cmd))
    try:
        result = subprocess.run(cmd, check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
        return result  # return result so callers (like up()) can inspect .stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}\n")

        # 1. Show resolved compose config dynamically using the same file set
        print("\n--- docker compose config ---")
        subprocess.run(
            _compose_cmd([f for f in cmd if f.endswith(('.yaml', '.yml'))]) + ["config"],
            check=False,
            cwd=PROJECT_DIR,
        )

        # 2. Attempt to show logs for the target service(s)
        try:
            # Extract service name (ignore flags and docker/compose keywords)
            services = [a for a in cmd if not a.startswith("-") and a not in ("docker", "compose", "up", "down", "build")]
            if services:
                svc = services[-1]
                print(f"\n--- Logs for service '{svc}' ---")
                subprocess.run(
                    cmd[: cmd.index("compose") + 1] + ["logs", "--no-color", "--tail=200", svc],
                    check=False,
                    cwd=PROJECT_DIR,
                )
        except Exception as log_err:
            print(f"(could not get logs: {log_err})")

        raise

def up(files: List[str], services: List[str]):
    preview = _run(_compose_cmd(files) + ["config", "--images"]).stdout
    print("Images Compose will use (from config):")
    print(preview.strip(), "\n")
    cmd = _compose_cmd(files) + ["up", "-d", "--build"] + services
    _run(cmd)
    time.sleep(0.5)
    for svc in services:
        wait_for_service(files, svc)

def down(files: List[str]):
    # 'down' ignores service list; it tears down the whole project
    cmd = _compose_cmd(files) + ["down", "-v"]
    _run(cmd)

def _container_id(files: List[str], service: str) -> str:
    cmd = _compose_cmd(files) + ["ps", "-a", "-q", service]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR)
    cid = res.stdout.strip()

    if res.returncode == 0 and cid:
        return cid

    print(f"\nFailed to find container ID for service '{service}\n")
    ps_out = subprocess.run(
        _compose_cmd(files) + ["ps", "--format", "table"],
        capture_output=True, text=True, cwd=PROJECT_DIR
    )
    print("docker compose ps output:")
    print(ps_out.stdout or ps_out.stderr or "<no output>")
    raise RuntimeError(
        f"No container id found for service '{service}'."
    )

def _inspect_state_health(container_id: str) -> Tuple[str, Optional[str]]:
    # Return (state, health) where state in {"created","running","exited","restarting","removing","dead"}
    # and health in {"healthy","unhealthy","starting", None}
    res = subprocess.run(
        ["docker", "inspect", container_id],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        raise RuntimeError(f"`docker inspect` failed for {container_id}: {res.stderr.strip()}")
    data = json.loads(res.stdout)[0]
    state = data.get("State", {})
    status = state.get("Status")  # docker's running/exited/etc
    health = None
    if "Health" in state and state["Health"]:
        health = state["Health"].get("Status")  # healthy/unhealthy/starting
    return status, health

def _compose_logs(files: List[str], service: str, tail: int = 200):
    try:
        res = subprocess.run(
            _compose_cmd(files) + ["logs", "--no-color", f"--tail={tail}", service],
            capture_output=True, text=True, cwd=PROJECT_DIR
        )
        out = (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")
        if out.strip():
            print(out.strip())
    except Exception:
        pass


def wait_for_service(files: List[str], service: str, timeout: float = 30.0, poll: float = 0.5):
    """
    Wait until the service container is running, and if it has a healthcheck, until it is healthy.
    If the container exits or on timeout, raises RuntimeError
    """
    deadline = time.time() + timeout
    cid = _container_id(files, service)  # ensures same compose context
    last_state, last_health = None, None

    while time.time() < deadline:
        state, health = _inspect_state_health(cid)

        # Terminal failure: exited/dead → dump logs and raise now
        if state in {"exited", "dead"}:
            print(f"Service {service} exited early (state={state}). Dumping logs:")
            _compose_logs(files, service)
            # Fallback to docker logs for very-early crashes
            try:
                res = subprocess.run(["docker", "logs", "--tail", "200", cid], capture_output=True, text=True)
                log_out = (res.stdout or "") + (("\n" + res.stderr) if res.stderr else "")
                if log_out.strip():
                    print(log_out.strip())
            except Exception:
                pass
            raise RuntimeError(f"Service '{service}' exited before becoming ready (state={state}, health={health}).")

        # Success conditions
        if health:  # healthcheck present
            if health == "healthy":
                print(f"Service {service} is healthy (container {cid[:12]}).")
                return
        else:
            if state == "running":
                print(f"Service {service} is running (container {cid[:12]}).")
                return

        # Progress note (only when it changes)
        if (state, health) != (last_state, last_health):
            print(f"Waiting for {service}: state={state}, health={health}")
            last_state, last_health = (state, health)

        time.sleep(poll)

    print(f"Timed out waiting for {service}. Dumping logs:")
    _compose_logs(files, service)
    raise RuntimeError(f"Service {service} did not become ready (state={last_state}, health={last_health}).")
