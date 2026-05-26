import os
import time
from pathlib import Path

from shadi import ShadiStore, PySessionContext


def run_demo():
    print("== SHADI Demo: Secure Agent Run ==")
    print("Step 1: Load sandbox policy (JSON)")
    policy_path = os.getenv("SHADI_POLICY_PATH", "sandbox.json")
    print("Using policy:", policy_path)

    print("Step 2: Brokered secrets check")
    brokered = os.getenv("SHADI_BROKER_SECRET")
    if brokered is not None:
        print("Brokered secret length:", len(brokered.encode("utf-8")))
        print("Step 3: Mock SLIM/MLS message")
        mock_slim_message()
        return

    print("Step 2b: Keystore-backed secret access")
    store = ShadiStore()
    session = PySessionContext("tourist_agent", "session-1")

    def verify_didvc(agent_id, session_id, presentation, claims):
        return agent_id == "tourist_agent" and len(presentation) > 0

    store.set_verifier(verify_didvc)
    ok = store.verify_session(session, b"dummy-didvc")
    if not ok:
        raise RuntimeError("DID/VC verification failed")

    store.put(session, "tourist_api_key", b"secret-value")
    secret = store.get(session, "tourist_api_key")
    print("Keystore secret length:", len(secret))

    print("Step 3: Mock SLIM/MLS message")
    mock_slim_message()


def run_secops_demo():
    print("== SHADI Demo: SecOps Autonomous Agent ==")
    print("Step 1: Load sandbox policy (JSON)")
    policy_path = os.getenv("SHADI_POLICY_PATH", "sandbox.json")
    print("Using policy:", policy_path)

    print("Step 2: Initialize secured session for SecOps")
    store = ShadiStore()
    session = PySessionContext("secops_agent", "secops-session-1")

    def verify_operator(agent_id, session_id, presentation, claims):
        return agent_id == "secops_agent" and len(presentation) > 0

    store.set_verifier(verify_operator)
    ok = store.verify_session(session, b"dummy-operator-didvc")
    if not ok:
        raise RuntimeError("SecOps verification failed")

    print("Step 3: Load SecOps credentials from SHADI")
    store.put(session, "secops/github_token", b"example-token")
    store.put(session, "secops/ssh_key", b"example-ssh-key")
    tmp_dir = os.getenv("SHADI_TMP_DIR", "./.tmp")
    agent_id = os.getenv("SHADI_AGENT_ID") or os.getenv("SHADI_OPERATOR_AGENT_ID")
    if agent_id:
        tmp_dir = str(Path(tmp_dir) / agent_id)
    workspace_dir = str(Path(tmp_dir) / "shadi-secops")
    store.put(session, "secops/workspace_dir", workspace_dir.encode("utf-8"))
    token_len = len(store.get(session, "secops/github_token"))
    workspace = store.get(session, "secops/workspace_dir").decode("utf-8")
    print("Github token length:", token_len)
    print("Workspace dir:", workspace)

    print("Step 4: Monitor GitHub security advisories")
    print("- Repo: agntcy/dir")
    print("- Finding: multiple CVEs pending remediation")

    print("Step 5: Clone repo and prepare remediation plan")
    print("- Clone into workspace")
    print("- Propose dependency/container upgrades")
    print("- Draft code patches and tests")

    print("Step 6: Create pull request with remediation")
    print("- Open PR in agntcy/dir")
    print("- Attach summary and risk notes")


def mock_slim_message():
    print("SLIM: preparing MLS session")
    time.sleep(0.1)
    print("SLIM: encrypting message")
    time.sleep(0.1)
    print("SLIM: sending to peer")
    time.sleep(0.1)
    print("SLIM: message delivered")


if __name__ == "__main__":
    mode = os.getenv("SHADI_DEMO", "default")
    if mode == "secops":
        run_secops_demo()
    else:
        run_demo()
