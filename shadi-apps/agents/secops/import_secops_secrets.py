import os
import secrets
import tomllib
from pathlib import Path

from shadi import ShadiStore, PySessionContext


def load_secops_config():
    config_path = Path(os.getenv("SHADI_SECOPS_CONFIG", "secops.toml"))
    if not config_path.exists():
        return config_path, {}
    with config_path.open("rb") as handle:
        return config_path, tomllib.load(handle)


def main():
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    token_key = secops_config.get("token_key", "secops/github_token")
    workspace_key = secops_config.get("workspace_key", "secops/workspace_dir")
    tmp_dir = os.getenv("SHADI_TMP_DIR", "./.tmp")
    agent_id = (
        os.getenv("SHADI_AGENT_ID")
        or os.getenv("SHADI_OPERATOR_AGENT_ID")
        or os.getenv("SHADI_SECOPS_AGENT_ID")
    )
    if agent_id:
        tmp_dir = str(Path(tmp_dir) / agent_id)
    workspace_dir = secops_config.get("workspace_dir", str(Path(tmp_dir) / "shadi-secops"))
    llm_key_prefix = secops_config.get("llm_key_prefix", "secops/llm")
    llm_provider = secops_config.get("llm_provider", os.getenv("LLM_PROVIDER", "anthropic"))
    memory_key_name = secops_config.get("memory_key", "secops/memory_key")
    slim_shared_secret_key = secops_config.get("slim_shared_secret_key", "secops/slim_shared_secret")
    slim_local_did_key = secops_config.get("slim_local_did_key", "secops/slim_local_did")
    slim_remote_did_key = secops_config.get("slim_remote_did_key", "secops/slim_remote_did")

    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    if not github_token:
        raise RuntimeError(
            "GITHUB_TOKEN is required. Set it with: export GITHUB_TOKEN=\"$(gh auth token)\""
        )

    agent_id = os.getenv("SHADI_OPERATOR_AGENT_ID", "secops_agent")
    presentation = os.getenv("SHADI_OPERATOR_PRESENTATION", "").encode("utf-8")
    if not presentation:
        raise RuntimeError("SHADI_OPERATOR_PRESENTATION must be set")

    store = ShadiStore()
    session = PySessionContext(agent_id, "secops-bootstrap-1")

    def verify_operator(verify_agent_id, session_id, presentation_bytes, claims):
        return verify_agent_id == agent_id and len(presentation_bytes) > 0

    store.set_verifier(verify_operator)
    ok = store.verify_session(session, presentation)
    if not ok:
        raise RuntimeError("SecOps verification failed")

    store.put(session, token_key, github_token.encode("utf-8"))
    store.put(session, workspace_key, workspace_dir.encode("utf-8"))

    llm_env_map = {
        "AZURE_OPENAI_API_KEY": "azure_openai_api_key",
        "AZURE_OPENAI_API_VERSION": "azure_openai_api_version",
        "AZURE_OPENAI_ENDPOINT": "azure_openai_endpoint",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "azure_openai_deployment_name",
        "CLAUDE_API_KEY": "claude_api_key",
        "CLAUDE_ENDPOINT": "claude_endpoint",
        "CLAUDE_MODEL": "claude_model",
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_ENDPOINT": "openai_endpoint",
        "OPENAI_MODEL": "openai_model",
        "GOOGLE_API_KEY": "google_api_key",
        "GOOGLE_ENDPOINT": "google_endpoint",
        "GOOGLE_MODEL": "google_model",
    }
    if llm_provider in ("anthropic", "claude"):
        openai_fallbacks = {
            "OPENAI_API_KEY": "CLAUDE_API_KEY",
            "OPENAI_ENDPOINT": "CLAUDE_ENDPOINT",
            "OPENAI_MODEL": "CLAUDE_MODEL",
        }
    elif llm_provider == "google":
        openai_fallbacks = {
            "OPENAI_API_KEY": "GOOGLE_API_KEY",
            "OPENAI_ENDPOINT": "GOOGLE_ENDPOINT",
            "OPENAI_MODEL": "GOOGLE_MODEL",
        }
    else:
        openai_fallbacks = {}
    missing = []
    for env_key, suffix in llm_env_map.items():
        value = os.getenv(env_key, "").strip()
        source_env = env_key
        if not value and env_key in openai_fallbacks:
            fallback_key = openai_fallbacks[env_key]
            value = os.getenv(fallback_key, "").strip()
            if value:
                source_env = fallback_key
        if value:
            store.put(session, f"{llm_key_prefix}/{suffix}", value.encode("utf-8"))
            if source_env == env_key:
                print("Stored LLM secret in SHADI:", f"{llm_key_prefix}/{suffix}")
            else:
                print(
                    "Stored LLM secret in SHADI:",
                    f"{llm_key_prefix}/{suffix}",
                    f"(from {source_env})",
                )
        else:
            if env_key.startswith("OPENAI_") and llm_provider not in ("openai", "azure", "azure_openai"):
                continue
            missing.append(env_key)

    store.put(session, f"{llm_key_prefix}/provider", llm_provider.encode("utf-8"))
    print("Stored LLM provider in SHADI:", f"{llm_key_prefix}/provider")

    memory_key = os.getenv("SECOPS_MEMORY_KEY", "").strip()
    if not memory_key:
        memory_key = secrets.token_urlsafe(32)
    store.put(session, memory_key_name, memory_key.encode("utf-8"))
    print("Stored memory key in SHADI:", memory_key_name)

    slim_shared_secret = os.getenv("SLIM_SHARED_SECRET", "").strip()
    if slim_shared_secret:
        store.put(session, slim_shared_secret_key, slim_shared_secret.encode("utf-8"))
        print("Stored SLIM shared secret in SHADI:", slim_shared_secret_key)

    slim_local_did = os.getenv("SLIM_LOCAL_DID", "").strip()
    if slim_local_did:
        store.put(session, slim_local_did_key, slim_local_did.encode("utf-8"))
        print("Stored SLIM local DID in SHADI:", slim_local_did_key)

    slim_remote_did = os.getenv("SLIM_REMOTE_DID", "").strip()
    if slim_remote_did:
        store.put(session, slim_remote_did_key, slim_remote_did.encode("utf-8"))
        print("Stored SLIM remote DID in SHADI:", slim_remote_did_key)

    print("Stored GitHub token in SHADI:", token_key)
    print("Stored workspace dir in SHADI:", workspace_key)
    print("Using config:", config_path)
    if missing:
        print("Missing LLM env vars:", ", ".join(missing))
        print("Hint: source ~/.env-phoenix before running this script")


if __name__ == "__main__":
    main()
