import json
import os
import re
import shutil
import subprocess
import tomllib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shadi import ShadiStore, PySessionContext, SqlCipherMemoryStore
from telemetry import tracer


_SUBPROCESS_TEXT_KWARGS = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}


def load_secops_config():
    config_path = Path(os.getenv("SHADI_SECOPS_CONFIG", "secops.toml"))
    if not config_path.exists():
        return config_path, {}
    with config_path.open("rb") as handle:
        return config_path, tomllib.load(handle)


def _secret_env_var(key_name):
    """Return the env var name that can cache a secret to avoid calling op in background."""
    return "SHADI_SECRET_" + key_name.upper().replace("/", "_").replace("-", "_").replace(".", "_")


def require_shadi_secret(store, session, key_name, label):
    env_val = os.environ.get(_secret_env_var(key_name), "").strip()
    if env_val:
        return env_val.encode("utf-8")
    try:
        return store.get(session, key_name)
    except Exception as exc:
        message = (
            f"Missing {label} in SHADI at key '{key_name}'. "
            "Run: uv run agents/secops/import_secops_secrets.py"
        )
        raise RuntimeError(message) from exc


def create_secops_session():
    store = ShadiStore()
    agent_id = os.getenv("SHADI_OPERATOR_AGENT_ID", "secops_agent")
    presentation = os.getenv("SHADI_OPERATOR_PRESENTATION", "").encode("utf-8")
    if not presentation:
        raise RuntimeError("SHADI_OPERATOR_PRESENTATION must be set")
    session = PySessionContext(agent_id, "secops-session-1")

    def verify_operator(verify_agent_id, session_id, presentation_bytes, claims):
        return verify_agent_id == agent_id and len(presentation_bytes) > 0

    store.set_verifier(verify_operator)
    ok = store.verify_session(session, presentation)
    if not ok:
        raise RuntimeError("SecOps verification failed")
    return store, session


def get_secops_credentials(config, store, session):
    secops_config = config.get("secops", {})
    token_key = secops_config.get("token_key", "secops/github_token")
    workspace_key = secops_config.get("workspace_key", "secops/workspace_dir")
    github_token = require_shadi_secret(store, session, token_key, "GitHub token").decode(
        "utf-8"
    )
    workspace = require_shadi_secret(store, session, workspace_key, "workspace dir").decode(
        "utf-8"
    )
    return github_token, workspace, token_key, workspace_key


def resolve_workspace_path(workspace_dir):
    workspace_path = Path(workspace_dir).expanduser()
    if not workspace_path.is_absolute():
        workspace_path = workspace_path.resolve()
    return workspace_path


def require_shadi_secret_value(store, session, key_name, label):
    value = require_shadi_secret(store, session, key_name, label).decode("utf-8").strip()
    if not value:
        raise RuntimeError(f"Missing {label} in SHADI at key '{key_name}'.")
    return value


def get_optional_shadi_secret_value(store, session, key_name):
    try:
        value = store.get(session, key_name).decode("utf-8").strip()
    except Exception:
        return ""
    return value


def get_human_did(store, session, github_handle):
    key_name = f"github/{github_handle}/did"
    return get_optional_shadi_secret_value(store, session, key_name)


def get_llm_settings(config, store=None, session=None, provider_override=None):
    if store is None or session is None:
        store, session = create_secops_session()
    secops_config = config.get("secops", {})
    llm_prefix = secops_config.get("llm_key_prefix", "secops/llm")
    if provider_override:
        provider = provider_override.strip().lower()
    else:
        provider_key = f"{llm_prefix}/provider"
        provider = require_shadi_secret_value(store, session, provider_key, "LLM provider").lower()

    use_openai_proxy = False
    openai_api_key_key = f"{llm_prefix}/openai_api_key"
    if provider in ("google", "anthropic", "claude"):
        if get_optional_shadi_secret_value(store, session, openai_api_key_key):
            model_key = f"{llm_prefix}/openai_model"
            endpoint_key = f"{llm_prefix}/openai_endpoint"
            api_key_key = openai_api_key_key
            api_version_key = None
            use_openai_proxy = True
        elif provider == "google":
            model_key = f"{llm_prefix}/google_model"
            endpoint_key = f"{llm_prefix}/google_endpoint"
            api_key_key = f"{llm_prefix}/google_api_key"
            api_version_key = None
        else:
            model_key = f"{llm_prefix}/claude_model"
            endpoint_key = f"{llm_prefix}/claude_endpoint"
            api_key_key = f"{llm_prefix}/claude_api_key"
            api_version_key = None
    elif provider == "openai":
        model_key = f"{llm_prefix}/openai_model"
        endpoint_key = f"{llm_prefix}/openai_endpoint"
        api_key_key = f"{llm_prefix}/openai_api_key"
        api_version_key = None
    elif provider in ("azure", "azure_openai"):
        model_key = f"{llm_prefix}/azure_openai_deployment_name"
        endpoint_key = f"{llm_prefix}/azure_openai_endpoint"
        api_key_key = f"{llm_prefix}/azure_openai_api_key"
        api_version_key = f"{llm_prefix}/azure_openai_api_version"
    else:
        raise RuntimeError(f"Unsupported LLM provider in SHADI: '{provider}'")

    model_name = require_shadi_secret_value(store, session, model_key, "LLM model")
    if provider == "openai":
        base_url = get_optional_shadi_secret_value(store, session, endpoint_key)
    else:
        base_url = require_shadi_secret_value(store, session, endpoint_key, "LLM endpoint")
    api_key = require_shadi_secret_value(store, session, api_key_key, "LLM API key")
    api_version = ""
    if api_version_key:
        api_version = get_optional_shadi_secret_value(store, session, api_version_key)

    adk_model = model_name
    if (provider == "openai" or use_openai_proxy) and "/" in model_name:
        if not model_name.startswith("openai/"):
            adk_model = f"openai/{model_name}"

    return {
        "provider": provider,
        "model": model_name,
        "adk_model": adk_model,
        "base_url": base_url,
        "api_key": api_key,
        "api_version": api_version,
        "openai_proxy": use_openai_proxy,
    }


def get_alert_severity(alert):
    advisory = alert.get("security_advisory") or {}
    vulnerability = alert.get("security_vulnerability") or {}
    return (advisory.get("severity") or vulnerability.get("severity") or "").lower()


def is_actionable_alert(alert):
    severity = get_alert_severity(alert)
    return severity in ("critical", "high")


def get_patched_version(alert):
    vulnerability = alert.get("security_vulnerability") or {}
    first_patched = vulnerability.get("first_patched_version") or {}
    if isinstance(first_patched, dict):
        identifier = first_patched.get("identifier")
        if identifier:
            return identifier
    return ""


def run_git(args, cwd, token=None):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if token:
        # Use gh as the git credential helper so all HTTPS GitHub operations
        # are authenticated via gh CLI rather than raw token headers.
        env["GH_TOKEN"] = token
        gh_bin = shutil.which("gh") or "gh"
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        env["GIT_CONFIG_COUNT"] = str(count + 1)
        env[f"GIT_CONFIG_KEY_{count}"] = "credential.https://github.com.helper"
        env[f"GIT_CONFIG_VALUE_{count}"] = f"!{gh_bin} auth git-credential"
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        check=True,
        capture_output=True,
        **_SUBPROCESS_TEXT_KWARGS,
        env=env,
    )


def _resolve_repo_root(repo_path):
    return Path(repo_path).resolve()


def _path_within_repo(repo_path, path_value):
    repo_root = _resolve_repo_root(repo_path)
    candidate = Path(path_value)
    candidates = [candidate]
    if not candidate.is_absolute():
        candidates = [candidate.resolve(), (repo_root / candidate).resolve()]
    for resolved in candidates:
        try:
            resolved.relative_to(repo_root)
            return resolved
        except ValueError:
            continue
    raise ValueError(f"{path_value!s} is outside repository {repo_root}")


def _repo_relative_path(repo_path, path_value):
    return _path_within_repo(repo_path, path_value).relative_to(_resolve_repo_root(repo_path)).as_posix()


def clone_or_update_repo(workspace_path, repo, token):
    repo_dir = workspace_path / repo.replace("/", "__")
    if repo_dir.exists():
        status = run_git(["status", "--porcelain"], repo_dir, token)
        if status.stdout.strip():
            return repo_dir, "dirty"
        run_git(["fetch", "origin"], repo_dir, token)
        base_ref = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], repo_dir, token)
        base_branch = base_ref.stdout.strip().rsplit("/", 1)[-1]
        run_git(["checkout", base_branch], repo_dir, token)
        run_git(["reset", "--hard", f"origin/{base_branch}"], repo_dir, token)
        return repo_dir, "updated"
    run_gh(["repo", "clone", repo, str(repo_dir.resolve())], workspace_path, token)
    return repo_dir, "cloned"


def update_cargo_manifest(path, package_name, version):
    if not path.exists():
        return False
    updated = False
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    pattern_simple = re.compile(rf"^\s*{re.escape(package_name)}\s*=\s*\"[^\"]+\"\s*$")
    pattern_table = re.compile(
        rf"^\s*{re.escape(package_name)}\s*=\s*\{{[^}}]*version\s*=\s*\"[^\"]+\"[^}}]*\}}\s*$"
    )
    for line in lines:
        if pattern_simple.match(line):
            new_lines.append(f"{package_name} = \"{version}\"")
            updated = True
            continue
        if pattern_table.match(line):
            new_line = re.sub(
                r"version\s*=\s*\"[^\"]+\"",
                f"version = \"{version}\"",
                line,
            )
            new_lines.append(new_line)
            updated = True
            continue
        new_lines.append(line)
    if updated:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def update_package_json(path, package_name, version):
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = False
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        if package_name not in deps:
            continue
        current = deps[package_name]
        prefix = ""
        if isinstance(current, str) and current[:1] in ("^", "~"):
            prefix = current[:1]
        deps[package_name] = f"{prefix}{version}"
        updated = True
    if updated:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return updated


def update_requirements_txt(path, package_name, version):
    """Pin *package_name* to *version* in a ``requirements.txt`` file.

    Replaces any existing version specifier (==, >=, ~=, >, extras [...]  etc.)
    with an exact pin ``package==version``.  Lines that are comments or do not
    mention to the package are left untouched.  Returns True if a change was made.
    """
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    updated = False
    pkg_escaped = re.escape(package_name)
    # Matches: optionally extras like pkg[extra1,extra2], then any version spec
    pattern = re.compile(
        rf"^(\s*{pkg_escaped}(?:\[[^\]]*\])?)\s*[!<>=~^][^\s;#]*(.*)$",
        re.IGNORECASE,
    )
    bare_pattern = re.compile(
        rf"^(\s*{pkg_escaped}(?:\[[^\]]*\])?)\s*([;#].*)?$",
        re.IGNORECASE,
    )
    for line in lines:
        m = pattern.match(line)
        if m:
            new_lines.append(f"{m.group(1).rstrip()}=={version}{m.group(2) or ''}")
            updated = True
            continue
        m2 = bare_pattern.match(line)
        if m2 and m2.group(1).strip():
            tail = m2.group(2) or ""
            new_lines.append(f"{m2.group(1).rstrip()}>={version}{tail}")
            updated = True
            continue
        new_lines.append(line)
    if updated:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def update_pyproject_toml(path, package_name, version):
    """Raise the lower bound of *package_name* in a ``pyproject.toml`` file.

    Handles the common formats used by PEP 517/518 and Poetry:
    * ``package_name = "^1.2"``  (Poetry caret)  → ``package_name = ">={version}"``
    * ``package_name = ">=1.2"`` → ``package_name = ">={version}"``
    * ``package_name = "==1.2"`` → ``package_name = "=={version}"``
    * ``"package_name>=1.2"``    inside a TOML array  → ``"package_name>={version}"``

    Returns True if a change was made.
    """
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    pkg_escaped = re.escape(package_name)
    updated = False

    # Pattern A: `pkg = "specifier"` (Poetry / uv style key-value)
    # Group 1: key+quote, Group 2: operator chars (^, >=, ==, etc.), Group 3: version
    def _replace_a(m):
        nonlocal updated
        updated = True
        op = m.group(2)
        spec_char = "==" if op.startswith("==") else ">="
        return f'{m.group(1)}{spec_char}{version}"'

    text, n = re.subn(
        rf'(\b{pkg_escaped}(?:\[[^\]]*\])?\s*=\s*")([~^>=<!]*)([^"]*)',
        _replace_a,
        text,
        flags=re.IGNORECASE,
    )
    updated = updated or n > 0

    # Pattern B: `"pkg>=specifier"` inside a TOML array / PEP 508 style
    # Group 1: package name (with optional extras), Group 2: operator chars
    def _replace_b(m):
        nonlocal updated
        updated = True
        spec_char = "==" if m.group(2).startswith("==") else ">="
        return f'"{m.group(1)}{spec_char}{version}'

    text, n = re.subn(
        rf'"({pkg_escaped}(?:\[[^\]]*\])?)\s*([!<>=~^]+)[^"]*',
        _replace_b,
        text,
        flags=re.IGNORECASE,
    )
    updated = updated or n > 0

    if updated:
        path.write_text(text, encoding="utf-8")
    return updated


def detect_dockerfile_ecosystem(path):
    """Return 'alpine', 'debian', or 'unknown' by inspecting the first FROM line."""
    if not path.exists():
        return "unknown"
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*FROM\s+(\S+)", line, re.IGNORECASE)
        if m:
            base = m.group(1).lower()
            if "alpine" in base:
                return "alpine"
            if any(x in base for x in ("debian", "ubuntu", "slim", "bookworm", "bullseye", "buster", "focal", "jammy")):
                return "debian"
    return "unknown"


def extract_dockerfile_base_image(path):
    """Return the first base image reference from a Dockerfile, if present."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*FROM\s+([^\s]+)", line, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def update_dockerfile_base_image(path, image, version):
    if not path.exists():
        return False
    updated = False
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    pattern = re.compile(
        rf"^\s*FROM\s+{re.escape(image)}(?::[^\s]+)?(?P<suffix>\s+AS\s+\S+)?\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        match = pattern.match(line)
        if match:
            suffix = match.group("suffix") or ""
            new_lines.append(f"FROM {image}:{version}{suffix}")
            updated = True
        else:
            new_lines.append(line)
    if updated:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def is_conventional_commit(message):
    pattern = re.compile(r"^(feat|fix|chore|docs|refactor|perf|test|build|ci|style|revert)(\([^)]+\))?: .+")
    return bool(pattern.match(message))


def apply_dependency_patch(repo_path, alert):
    dependency = alert.get("dependency") or {}
    package = dependency.get("package") or {}
    ecosystem = (package.get("ecosystem") or "").lower()
    name = package.get("name") or ""
    manifest_path = dependency.get("manifest_path") or ""
    patched_version = get_patched_version(alert)
    if not patched_version:
        return {"status": "no_patch", "dependency": name, "ecosystem": ecosystem}

    if ecosystem == "cargo":
        manifest = repo_path / (manifest_path or "Cargo.toml")
        updated = update_cargo_manifest(manifest, name, patched_version)
        if not updated:
            return {"status": "not_updated", "dependency": name, "ecosystem": ecosystem}
        try:
            run_git(["add", _repo_relative_path(repo_path, manifest)], repo_path, token=None)
            cargo_args = [
                "cargo",
                "update",
                "-p",
                name,
                "--precise",
                patched_version,
                "--manifest-path",
                str(_path_within_repo(repo_path, manifest)),
            ]
            subprocess.run(cargo_args, cwd=repo_path, check=True, capture_output=True, text=True)
            run_git(["add", "Cargo.lock"], repo_path, token=None)
        except subprocess.CalledProcessError as exc:
            return {
                "status": "update_failed",
                "dependency": name,
                "ecosystem": ecosystem,
                "error": exc.stderr.strip(),
            }
        return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

    if ecosystem == "npm":
        manifest = repo_path / (manifest_path or "package.json")
        updated = update_package_json(manifest, name, patched_version)
        if not updated:
            return {"status": "not_updated", "dependency": name, "ecosystem": ecosystem}
        try:
            run_git(["add", _repo_relative_path(repo_path, manifest)], repo_path, token=None)
            npm_cwd = manifest.parent
            subprocess.run(
                ["npm", "install", "--package-lock-only"],
                cwd=npm_cwd,
                check=True,
                capture_output=True,
                text=True,
            )
            lockfile = npm_cwd / "package-lock.json"
            if lockfile.exists():
                run_git(["add", _repo_relative_path(repo_path, lockfile)], repo_path, token=None)
        except subprocess.CalledProcessError as exc:
            return {
                "status": "update_failed",
                "dependency": name,
                "ecosystem": ecosystem,
                "error": exc.stderr.strip(),
            }
        return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

    if ecosystem in ("pip", "pip-compile", "python"):
        manifest = repo_path / (manifest_path or "requirements.txt")

        # -- uv.lock: regenerate the lock file using `uv lock --upgrade-package`.
        if manifest_path.endswith("uv.lock"):
            if not manifest.exists():
                return {
                    "status": "missing_lockfile",
                    "dependency": name,
                    "ecosystem": ecosystem,
                    "manifest": manifest_path,
                }
            if not shutil.which("uv"):
                return {"status": "missing_uv", "dependency": name, "ecosystem": ecosystem}
            try:
                subprocess.run(
                    ["uv", "lock", "--upgrade-package", f"{name}=={patched_version}"],
                    cwd=manifest.parent,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                run_git(["add", _repo_relative_path(repo_path, manifest)], repo_path, token=None)
            except subprocess.CalledProcessError as exc:
                return {
                    "status": "update_failed",
                    "dependency": name,
                    "ecosystem": ecosystem,
                    "error": exc.stderr.strip(),
                }
            return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

        # -- requirements.txt: edit the pin in place.
        if manifest_path.endswith("requirements.txt") or manifest_path.endswith(".txt"):
            if not update_requirements_txt(manifest, name, patched_version):
                return {"status": "not_updated", "dependency": name, "ecosystem": ecosystem, "manifest": manifest_path}
            run_git(["add", str(manifest.relative_to(repo_path))], repo_path, token=None)
            # Also regenerate uv.lock if it exists anywhere in the same tree.
            uv_locks = list(manifest.parent.glob("uv.lock")) + list(manifest.parent.parent.glob("uv.lock"))
            for uv_lock in uv_locks:
                if uv_lock.exists() and shutil.which("uv"):
                    try:
                        subprocess.run(
                            ["uv", "lock", "--upgrade-package", f"{name}=={patched_version}"],
                            cwd=uv_lock.parent,
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        run_git(["add", str(uv_lock.relative_to(repo_path))], repo_path, token=None)
                    except OSError:
                        pass
            return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

        # -- pyproject.toml: update the version constraint.
        if manifest_path.endswith("pyproject.toml"):
            if not update_pyproject_toml(manifest, name, patched_version):
                return {"status": "not_updated", "dependency": name, "ecosystem": ecosystem, "manifest": manifest_path}
            run_git(["add", str(manifest.relative_to(repo_path))], repo_path, token=None)
            # Regenerate lock file (uv.lock / poetry.lock) if tooling is available.
            uv_lock = manifest.parent / "uv.lock"
            poetry_lock = manifest.parent / "poetry.lock"
            if uv_lock.exists() and shutil.which("uv"):
                try:
                    subprocess.run(
                        ["uv", "lock", "--upgrade-package", f"{name}=={patched_version}"],
                        cwd=manifest.parent,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    run_git(["add", str(uv_lock.relative_to(repo_path))], repo_path, token=None)
                except OSError:
                    pass
            elif poetry_lock.exists() and shutil.which("poetry"):
                try:
                    subprocess.run(
                        ["poetry", "update", name],
                        cwd=manifest.parent,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    run_git(["add", str(poetry_lock.relative_to(repo_path))], repo_path, token=None)
                except OSError:
                    pass
            return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

        return {
            "status": "unsupported_manifest",
            "dependency": name,
            "ecosystem": ecosystem,
            "manifest": manifest_path,
        }

    if ecosystem in ("docker", "dockerfile"):
        manifest = repo_path / (manifest_path or "Dockerfile")
        updated = update_dockerfile_base_image(manifest, name, patched_version)
        if not updated:
            return {
                "status": "not_updated",
                "dependency": name,
                "ecosystem": ecosystem,
                "manifest": manifest_path,
            }
        run_git(["add", _repo_relative_path(repo_path, manifest)], repo_path, token=None)
        return {"status": "updated", "dependency": name, "ecosystem": ecosystem, "version": patched_version}

    return {"status": "unsupported", "dependency": name, "ecosystem": ecosystem}


def _extract_dockerfile_hints_from_workflows(repo_path: Path) -> list:
    """Scan ``.github/workflows/`` for docker build steps.

    Returns a list of ``(hints, dockerfile_path)`` pairs where *hints* is a
    list of lowercase service/image-name keywords and *dockerfile_path* is the
    resolved absolute ``Path`` to the Dockerfile inside *repo_path*.

    Understands:
    * ``docker/build-push-action`` ``file:``, ``dockerfile:``, and ``context:`` YAML fields.
    * ``docker build -f|--file <path>`` inside ``run:`` steps.
    * Image name from ``tags:`` and ``image:`` fields for richer hint matching.
    * Step ``name:`` fields that contain hyphenated service identifiers.

    Pure regex/filesystem — no YAML parser required.
    """
    workflow_dir = repo_path / ".github" / "workflows"
    if not workflow_dir.exists():
        return []

    repo_root = _resolve_repo_root(repo_path)

    results: list = []          # list[tuple[list[str], Path]]
    seen_paths: set = set()

    wf_files = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))

    def _safe_resolve(path_str: str) -> "Path | None":
        """Resolve *path_str* relative to *repo_path*, rejecting escapes."""
        try:
            candidate = (repo_root / path_str.lstrip("./")).resolve()
            candidate.relative_to(repo_root)   # raises ValueError on escape
            return candidate
        except (ValueError, OSError):
            return None

    def _register(hints: list, df_path: Path) -> None:
        if df_path in seen_paths:
            for existing_hints, existing_path in results:
                if existing_path == df_path:
                    for h in hints:
                        if h not in existing_hints:
                            existing_hints.append(h)
                    break
        else:
            seen_paths.add(df_path)
            results.append((list(hints), df_path))

    def _hints_for_path(df_path: Path, extra: list) -> list:
        h = [df_path.parent.name.lower()]
        for e in extra:
            if e and e not in h:
                h.append(e)
        return h

    def _flush(blk: dict) -> None:
        target: "Path | None" = None
        # Prefer explicit Dockerfile path. In docker/build-push-action, the
        # dockerfile path is commonly relative to the build context.
        dockerfile_path = blk.get("file") or blk.get("dockerfile") or ""
        context_path = blk.get("context") or ""
        if dockerfile_path and "${{" not in dockerfile_path:
            candidate_path = dockerfile_path
            if blk.get("dockerfile") and context_path and "${{" not in context_path:
                candidate_path = str(Path(context_path) / dockerfile_path)
            c = _safe_resolve(candidate_path)
            if c and c.exists():
                target = c
        # Fall back to context dir + implicit Dockerfile.
        if target is None and blk.get("context") and "${{" not in blk["context"]:
            c = _safe_resolve(blk["context"] + "/Dockerfile")
            if c and c.exists():
                target = c
        if target is None:
            return

        extra: list = []
        for key in ("tags", "image"):
            val = blk.get(key, "")
            if val and "${{" not in val:
                # "ghcr.io/org/scheduler-agent:latest" → "scheduler-agent"
                image_name = val.strip().splitlines()[0].split(":")[0].split("/")[-1].strip()
                if image_name:
                    extra.append(image_name.lower())
        if blk.get("context"):
            ctx_name = Path(blk["context"].lstrip("./")).name.lower()
            if ctx_name:
                extra.append(ctx_name)
        if blk.get("name"):
            for tok in re.split(r"\s+", blk["name"].strip().lower()):
                tok = tok.strip("\"',-.()")
                if ("-" in tok or "_" in tok) and len(tok) > 2:
                    extra.append(tok)

        _register(_hints_for_path(target, extra), target)

    for wf_file in wf_files:
        try:
            text = wf_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Walk line-by-line accumulating per-step key/value pairs.
        current: dict = {}
        for line in text.splitlines():
            if re.match(r"^\s{2,}-\s", line):   # step/list-item boundary
                _flush(current)
                current = {}
            m = re.match(r"^\s*(file|dockerfile|context|tags|image|name):\s*['\"]?(.*?)['\"]?\s*$", line.strip())
            if m:
                current[m.group(1)] = m.group(2).strip().strip("'\"")
        _flush(current)

        # Also handle: docker build -f ./path/Dockerfile  in run: blocks.
        for m in re.finditer(
            r"docker\s+build\b[^\n]*?(?:-f|--file)\s+['\"]?\.?/?([^\s'\"#\n${}]+)",
            text, re.IGNORECASE,
        ):
            path_str = m.group(1).strip()
            if "${{" in path_str:
                continue
            c = _safe_resolve(path_str)
            if c and c.exists():
                _register([c.parent.name.lower()], c)

    return results


def _list_repo_dockerfiles(repo_path: Path) -> list[Path]:
    """Return all Dockerfiles in *repo_path* using portable Python traversal."""
    dockerfiles: list[Path] = []
    for root, dirs, files in os.walk(_resolve_repo_root(repo_path)):
        dirs[:] = [
            name
            for name in dirs
            if not name.startswith(".") and name not in ("node_modules", "vendor", "__pycache__")
        ]
        if "Dockerfile" in files:
            dockerfiles.append(Path(root) / "Dockerfile")
    return dockerfiles


def _tokenize_match_text(value: str) -> set[str]:
    """Split a path-like or image-like value into lowercase match tokens."""
    return {
        token
        for token in re.split(r"[^a-z0-9]+", value.lower())
        if token
    }


def _select_best_dockerfile_candidate(repo_path: Path, candidates, hints):
    """Return the best matching Dockerfile path for the given alert hints."""
    stop_tokens = {
        "artifacts",
        "container",
        "containers",
        "dockerfile",
        "ghcr",
        "io",
        "latest",
        "report",
        "trivy",
    }
    scored = []
    for candidate_hints, dockerfile in candidates:
        rel_path = _repo_relative_path(repo_path, dockerfile)
        path_tokens = _tokenize_match_text(rel_path)
        candidate_hint_tokens = set()
        for candidate_hint in candidate_hints:
            candidate_hint_tokens.update(_tokenize_match_text(candidate_hint))
        candidate_hint_tokens -= stop_tokens

        best_overlap = 0
        exact_parent = 0
        for hint in hints:
            hint_tokens = _tokenize_match_text(hint) - stop_tokens
            if not hint_tokens:
                continue
            overlap = len(hint_tokens & (path_tokens | candidate_hint_tokens))
            if overlap > best_overlap:
                best_overlap = overlap
            if dockerfile.parent.name.lower() in hint_tokens or dockerfile.parent.name.lower() in candidate_hint_tokens:
                exact_parent = 1
        if best_overlap > 0:
            scored.append((best_overlap, exact_parent, dockerfile))

    if not scored:
        return None

    scored.sort(key=lambda item: (item[0], item[1], -len(item[2].parts)), reverse=True)
    best_overlap, best_exact_parent, best_path = scored[0]
    if len(scored) == 1:
        return best_path
    second_overlap, second_exact_parent, _ = scored[1]
    if (best_overlap, best_exact_parent) > (second_overlap, second_exact_parent):
        return best_path
    return None


def _find_dockerfile_for_alert(repo_path, alert, fields):
    """Search the local repository clone for the Dockerfile that corresponds to
    a code-scanning (Trivy) alert.

    Strategy (in priority order):
    1. ``location.path`` in the alert points directly at a Dockerfile — use it.
    2. Use Dockerfile locations declared in ``.github/workflows/`` as the
       authoritative set of container build definitions, and match alert hints
       against those paths first.
    3. If workflow metadata is absent or inconclusive, fall back to a generic
       Dockerfile scan of the local clone.
    4. If only one Dockerfile exists in the repo, assume it is the target.
    5. Give up — return None so the caller can log ``no_dockerfile_found``.

    The repo is already cloned locally (by ``clone_or_update_fork``), so the
    search uses pure filesystem operations — no network calls.
    """
    repo_root = _resolve_repo_root(repo_path)
    instance = alert.get("most_recent_instance") or {}
    location = instance.get("location") or {}
    alert_path = location.get("path", "")
    category = instance.get("category", "") or ""
    environment_raw = instance.get("environment", "") or ""

    # 1. Direct Dockerfile path from the alert.
    if alert_path and re.search(r"dockerfile", alert_path, re.IGNORECASE):
        candidate = repo_root / alert_path
        if candidate.exists():
            return candidate

    # Enumerate every Dockerfile in the repository once using Python traversal.
    all_dockerfiles = _list_repo_dockerfiles(repo_path)

    if not all_dockerfiles:
        return None

    # Build a list of candidate service/image name hints.
    hints = []
    # From the SARIF artifact path (e.g. "trivy-report-frontend/trivy-frontend.sarif")
    sarif_raw = fields.get("source_sarif_file", "") or alert_path or ""
    sarif_stem = Path(sarif_raw).stem  # "trivy-frontend"
    hints.append(re.sub(r"^trivy[-_]?(report[-_])?", "", sarif_stem, flags=re.IGNORECASE))
    # Parent directory of the SARIF path (e.g. "trivy-report-frontend" → "frontend")
    sarif_parent = Path(sarif_raw).parent.name
    hints.append(re.sub(r"^trivy[-_]?(report[-_])?", "", sarif_parent, flags=re.IGNORECASE))
    # Category often includes the scanned image name, e.g. trivy-scheduler-agent.
    hints.append(re.sub(r"^trivy[-_]?(report[-_])?", "", category, flags=re.IGNORECASE))
    if alert_path:
        alert_path_obj = Path(alert_path)
        hints.append(alert_path_obj.name)
        if alert_path_obj.parent.name:
            hints.append(alert_path_obj.parent.name)
    if environment_raw:
        try:
            environment = json.loads(environment_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            environment = {}
        for key in ("image", "repo"):
            value = environment.get(key)
            if not value:
                continue
            value_str = str(value)
            hints.append(value_str.split("/")[-1].split(":")[0])
            parts = [part for part in value_str.split("/") if part]
            if len(parts) >= 2:
                hints.append(parts[-2])

    # 2. Match hints against the workflow-derived (service, Dockerfile) map.
    #    These paths are the authoritative container build definitions.
    workflow_map = _extract_dockerfile_hints_from_workflows(repo_path)
    workflow_target = _select_best_dockerfile_candidate(repo_path, workflow_map, hints)
    if workflow_target is not None:
        return workflow_target

    # 3. Fall back to the repo-wide Dockerfile scan if workflow metadata is
    #    absent or insufficient.
    repo_candidates = [([dockerfile.parent.name.lower()], dockerfile) for dockerfile in all_dockerfiles]
    repo_target = _select_best_dockerfile_candidate(repo_path, repo_candidates, hints)
    if repo_target is not None:
        return repo_target

    # 4. If only one Dockerfile in the whole repo, it must be the one.
    if len(all_dockerfiles) == 1:
        return all_dockerfiles[0]

    return None


def apply_container_cve_patch(repo_path, alert):
    """Plan container CVE remediation for a SARIF / code-scanning alert.

    The repository must already be cloned locally (done by ``clone_or_update_fork``
    in ``remediate_repos``).  This function:
      1. Parses the Trivy message to get the vulnerable package + fixed version.
      2. Searches the local clone for the matching Dockerfile using
         ``_find_dockerfile_for_alert`` (filesystem glob + name heuristics).
      3. Recommends a clean remediation path: rebuild the image and, when the
         scan points at an outdated base image, prefer updating the ``FROM``
         line instead of inserting ad-hoc package-install commands.

    Returns a result dict with keys: status, cve_id, package, fixed_version, path.
    """
    rule = alert.get("rule") or {}
    instance = alert.get("most_recent_instance") or {}
    location = instance.get("location") or {}
    message_text = (instance.get("message") or {}).get("text", "")

    cve_id = rule.get("id", "")
    severity = rule.get("severity", "")
    alert_path = location.get("path", "")

    fields = parse_trivy_message(message_text)
    package = fields.get("package", "")
    fixed_version = fields.get("fixed_version", "")

    if not package:
        return {"status": "no_package", "cve_id": cve_id, "path": alert_path}

    target = _find_dockerfile_for_alert(repo_path, alert, fields)

    if target is None:
        return {
            "status": "no_dockerfile_found",
            "cve_id": cve_id,
            "package": package,
            "path": alert_path,
        }

    rel = _repo_relative_path(repo_path, target)
    base_image = extract_dockerfile_base_image(target)
    if not base_image:
        return {
            "status": "base_image_review_required",
            "cve_id": cve_id,
            "severity": severity,
            "package": package,
            "fixed_version": fixed_version,
            "path": rel,
            "recommendation": "Review the Dockerfile and rebuild the image. Do not add ad-hoc package-install lines for this CVE.",
        }

    return {
        "status": "base_image_refresh_recommended",
        "cve_id": cve_id,
        "severity": severity,
        "package": package,
        "fixed_version": fixed_version,
        "path": rel,
        "base_image": base_image,
        "recommendation": "Rebuild the image. If the container scan attributes the CVE to the base image lineage, update the FROM image/tag rather than adding package-level Dockerfile edits.",
    }


def run_gh(args, cwd, token):
    if not shutil.which("gh"):
        raise RuntimeError("gh CLI is required for PR creation")
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    result = subprocess.run(
        ["gh"] + args,
        cwd=cwd,
        capture_output=True,
        **_SUBPROCESS_TEXT_KWARGS,
        env=env,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )
    return result


def ensure_upstream_remote(repo_path, upstream_repo, token):
    upstream_url = f"https://github.com/{upstream_repo}.git"
    try:
        current = run_git(["remote", "get-url", "upstream"], repo_path, token)
        if current.stdout.strip() != upstream_url:
            run_git(["remote", "set-url", "upstream", upstream_url], repo_path, token)
    except subprocess.CalledProcessError:
        run_git(["remote", "add", "upstream", upstream_url], repo_path, token)


def ensure_fork(upstream_repo, fork_owner, token, cwd):
    _, repo_name = upstream_repo.split("/", 1)
    fork_repo = f"{fork_owner}/{repo_name}"

    # Check if a fork already exists with the expected name.
    try:
        run_gh(["api", f"repos/{fork_repo}"], cwd, token)
        return fork_repo
    except subprocess.CalledProcessError:
        pass

    # Also check if a fork exists under a different name (e.g. repo was renamed).
    try:
        forks_result = run_gh(["api", f"repos/{upstream_repo}/forks", "--jq",
                               f'[.[] | select(.owner.login == "{fork_owner}")] | first | .full_name'], cwd, token)
        existing = forks_result.stdout.strip().strip('"')
        if existing and existing != "null":
            return existing
    except subprocess.CalledProcessError:
        pass

    # Create the fork via the API.
    try:
        fork_result = run_gh(["api", f"repos/{upstream_repo}/forks",
                               "-f", f"owner={fork_owner}", "--method", "POST"], cwd, token)
        created_name = json.loads(fork_result.stdout).get("full_name")
        if created_name:
            fork_repo = created_name
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").lower()
        if "already exists" not in stderr and "name already exists" not in stderr:
            raise RuntimeError(
                f"Failed to create fork of {upstream_repo}: {exc.stderr.strip() if exc.stderr else exc}"
            ) from exc

    for _ in range(10):
        try:
            run_gh(["api", f"repos/{fork_repo}"], cwd, token)
            return fork_repo
        except subprocess.CalledProcessError:
            time.sleep(1)

    raise RuntimeError(f"fork not ready for {fork_repo}")


def clone_or_update_fork(workspace_path, upstream_repo, fork_owner, token):
    fork_repo = ensure_fork(upstream_repo, fork_owner, token, workspace_path)
    repo_dir = workspace_path / fork_repo.replace("/", "__")

    if repo_dir.exists():
        status = run_git(["status", "--porcelain"], repo_dir, token)
        if status.stdout.strip():
            # Dirty working tree — clean it so the sync can proceed.
            run_git(["checkout", "--", "."], repo_dir, token)
            run_git(["clean", "-fd"], repo_dir, token)
        run_git(["fetch", "origin"], repo_dir, token)
    else:
        run_gh(["repo", "clone", fork_repo, str(repo_dir.resolve())], workspace_path, token)

    ensure_upstream_remote(repo_dir, upstream_repo, token)
    run_git(["fetch", "upstream"], repo_dir, token)
    base_ref = run_git(["symbolic-ref", "refs/remotes/upstream/HEAD"], repo_dir, token)
    base_branch = base_ref.stdout.strip().rsplit("/", 1)[-1]
    run_git(["checkout", "-B", base_branch], repo_dir, token)
    run_git(["reset", "--hard", f"upstream/{base_branch}"], repo_dir, token)
    run_git(["push", "origin", base_branch, "--force"], repo_dir, token)

    return repo_dir, "updated", fork_repo, base_branch


def create_remediation_issue(repo, updates, token, cwd):
    issue_title = "SecOps: remediate critical vulnerabilities"
    issue_body_lines = [
        "Automated remediation guidance for critical dependency and container-image alerts.",
        "",
        "Updates:",
    ]
    for update in updates:
        dep = update.get("dependency")
        if dep:
            version = update.get("version")
            status_line = update.get("status")
            if version:
                issue_body_lines.append(f"- {dep}: {version} ({status_line})")
            else:
                issue_body_lines.append(f"- {dep}: {status_line}")
            continue

        cve_id = update.get("cve_id") or "?"
        package = update.get("package") or "container finding"
        base_image = update.get("base_image")
        path = update.get("path")
        status_line = update.get("status")
        fixed_version = update.get("fixed_version")

        line = f"- [{cve_id}] {package}"
        if fixed_version:
            line += f" fixed in {fixed_version}"
        if base_image:
            line += f" on base image {base_image}"
        if path:
            line += f" in {path}"
        line += f" ({status_line})"
        issue_body_lines.append(line)
    issue_body_lines.append("")
    issue_body_lines.append("Generated by SHADI SecOps.")

    issue_body = "\n".join(issue_body_lines)
    response = run_gh(
        [
            "api",
            f"repos/{repo}/issues",
            "-f",
            f"title={issue_title}",
            "-f",
            f"body={issue_body}",
        ],
        cwd,
        token,
    )
    payload = json.loads(response.stdout)
    return payload.get("number"), payload.get("html_url")


def pending_prs_path(workspace_dir):
    return resolve_workspace_path(workspace_dir) / "secops_pending_prs.json"


def write_pending_prs(workspace_dir, pending):
    path = pending_prs_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")
    return path


def load_pending_prs(workspace_dir):
    path = pending_prs_path(workspace_dir)
    if not path.exists():
        return path, {"repos": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {"repos": {}}
    data.setdefault("repos", {})
    return path, data


def remediate_repos(config, github_token, report, workspace_dir, create_prs=True, fork_owner=None):
    workspace_path = resolve_workspace_path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)
    remediation = {}
    pending = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": {},
    }
    if not fork_owner:
        fork_owner = os.getenv("SHADI_HUMAN_GITHUB", "").strip()
    if not fork_owner:
        raise RuntimeError(
            "SHADI_HUMAN_GITHUB must be set to create forks and PRs. "
            "Set it as an environment variable, pass 'human_github' in the command, "
            "or add 'human_github = \"<handle>\"' under [secops] in your config file."
        )

    secops_cfg = config.get("secops", {})
    git_name  = (
        secops_cfg.get("git_name")
        or os.getenv("SHADI_GIT_NAME", "")
        or os.getenv("GIT_AUTHOR_NAME", "")
    ).strip()
    git_email = (
        secops_cfg.get("git_email")
        or os.getenv("SHADI_GIT_EMAIL", "")
        or os.getenv("GIT_AUTHOR_EMAIL", "")
    ).strip()

    def _global_git(key):
        """Return the value of a global git config key, or empty string."""
        try:
            r = subprocess.run(
                ["git", "config", "--global", key],
                capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except OSError:
            return ""

    # SSH signing key: prefer explicit config/env, fall back to global git config.
    git_signing_key = (
        secops_cfg.get("git_signing_key")
        or os.getenv("SHADI_GIT_SIGNING_KEY", "")
        or _global_git("user.signingkey")
    ).strip()
    gpg_format   = _global_git("gpg.format")     # e.g. "ssh"
    gpg_ssh_prog = _global_git("gpg.ssh.program") # e.g. "/Applications/1Password.app/.../op-ssh-sign"
    global_gpgsign = _global_git("commit.gpgsign").lower() in ("true", "1", "yes")

    for repo, repo_data in report.get("repos", {}).items():
        alerts = repo_data.get("data", {}).get("dependabot", [])
        actionable_alerts = [alert for alert in alerts if is_actionable_alert(alert)]
        cs_alerts = repo_data.get("data", {}).get("code_scanning", [])
        actionable_cs = [a for a in cs_alerts if is_actionable_code_scanning_alert(a)]

        if not actionable_alerts and not actionable_cs:
            remediation[repo] = {"status": "no_actionable_alerts"}
            continue

        repo_path, clone_status, fork_repo, base_branch = clone_or_update_fork(
            workspace_path, repo, fork_owner, github_token
        )
        if not base_branch:
            remediation[repo] = {"status": "fork_sync_failed"}
            continue
        branch_name = f"fix/secops-remediate-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        try:
            run_git(["checkout", "-b", branch_name], repo_path, github_token)
        except subprocess.CalledProcessError:
            run_git(["checkout", branch_name], repo_path, github_token)
        if git_email:
            run_git(["config", "user.email", git_email], repo_path, github_token)
        if git_name:
            run_git(["config", "user.name", git_name], repo_path, github_token)
        if git_signing_key:
            # Replicate the global 1Password SSH signing config in the repo.
            fmt  = gpg_format or "ssh"
            prog = gpg_ssh_prog or shutil.which("op-ssh-sign") or "/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
            run_git(["config", "gpg.format",       fmt],              repo_path, github_token)
            run_git(["config", "gpg.ssh.program",  prog],             repo_path, github_token)
            run_git(["config", "user.signingkey",  git_signing_key],  repo_path, github_token)
            run_git(["config", "commit.gpgsign",   "true"],           repo_path, github_token)

        updates = []
        for alert in actionable_alerts:
            update = apply_dependency_patch(repo_path, alert)
            update["severity"] = get_alert_severity(alert)
            updates.append(update)

        # Container scan alerts are turned into rebuild/base-image guidance.
        container_updates = []
        for cs_alert in actionable_cs:
            try:
                cu = apply_container_cve_patch(repo_path, cs_alert)
            except (subprocess.CalledProcessError, OSError) as exc:
                cve_id = (cs_alert.get("rule") or {}).get("id", "?")
                cu = {"status": "analysis_error", "cve_id": cve_id, "error": str(exc)}
            container_updates.append(cu)

        all_updates = updates + container_updates
        status = run_git(["status", "--porcelain"], repo_path, github_token)
        if not status.stdout.strip():
            container_follow_up = [
                cu
                for cu in container_updates
                if cu.get("status") in ("base_image_refresh_recommended", "base_image_review_required")
            ]
            if container_follow_up:
                issue_number, issue_url = create_remediation_issue(repo, all_updates, github_token, repo_path)
                remediation[repo] = {
                    "status": "container_rebuild_recommended",
                    "updates": all_updates,
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                }
                run_git(["checkout", base_branch], repo_path, github_token)
                continue
            remediation[repo] = {
                "status": "no_changes",
                "updates": all_updates,
            }
            run_git(["checkout", base_branch], repo_path, github_token)
            continue

        commit_message = "chore(secops): remediate critical vulnerabilities"
        if not is_conventional_commit(commit_message):
            raise RuntimeError(f"commit message is not conventional: '{commit_message}'")
        run_git(["add", "-A"], repo_path, github_token)
        commit_args = ["commit", "-m", commit_message, "-s"]
        if git_signing_key and (global_gpgsign or bool(secops_cfg.get("git_signing_key") or os.getenv("SHADI_GIT_SIGNING_KEY", ""))):
            commit_args.append("-S")
        run_git(commit_args, repo_path, github_token)
        run_git(["push", "origin", branch_name], repo_path, github_token)

        pr_body_lines = [
            "Automated remediation for critical dependency vulnerabilities and container-image findings.",
            "",
        ]
        if updates:
            pr_body_lines += ["**Dependency updates:**"]
            for update in updates:
                dep = update.get("dependency") or "unknown"
                version = update.get("version")
                status_line = update.get("status")
                if version:
                    pr_body_lines.append(f"- {dep}: {version} ({status_line})")
                else:
                    pr_body_lines.append(f"- {dep}: {status_line}")
        if container_updates:
            pr_body_lines += ["", "**Container image remediation guidance:**"]
            for cu in container_updates:
                cve = cu.get("cve_id") or "?"
                pkg = cu.get("package") or "?"
                ver = cu.get("fixed_version") or ""
                path = cu.get("path") or "?"
                base_image = cu.get("base_image") or ""
                st = cu.get("status")
                line = f"- [{cve}] {pkg}"
                if ver:
                    line += f" fixed in {ver}"
                if base_image:
                    line += f" on {base_image}"
                line += f" in `{path}` ({st})"
                pr_body_lines.append(line)

        issue_number, issue_url = create_remediation_issue(repo, all_updates, github_token, repo_path)
        if issue_number:
            pr_body_lines.append("")
            pr_body_lines.append(f"Fixes #{issue_number}")
        pr_body = "\n".join(pr_body_lines)
        if not create_prs:
            pending["repos"][repo] = {
                "title": commit_message,
                "head": f"{fork_owner}:{branch_name}",
                "base": base_branch,
                "body": pr_body,
                "updates": all_updates,
                "issue_number": issue_number,
                "issue_url": issue_url,
                "fork_owner": fork_owner,
            }
            remediation[repo] = {
                "status": "pending_pr_approval",
                "updates": all_updates,
                "branch": branch_name,
                "fork": fork_repo,
                "issue_url": issue_url,
            }
        else:
            try:
                pr_response = run_gh(
                    [
                        "pr", "create",
                        "--repo", repo,
                        "--head", f"{fork_owner}:{branch_name}",
                        "--base", base_branch,
                        "--title", commit_message,
                        "--body", pr_body,
                    ],
                    repo_path,
                    github_token,
                )
                pr_url = pr_response.stdout.strip()
                remediation[repo] = {
                    "status": "pr_created",
                    "updates": all_updates,
                    "pr_url": pr_url,
                    "branch": branch_name,
                    "fork": fork_repo,
                    "issue_url": issue_url,
                }
            except (RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
                remediation[repo] = {
                    "status": "pr_failed",
                    "updates": all_updates,
                    "error": str(exc),
                    "branch": branch_name,
                    "fork": fork_repo,
                    "issue_url": issue_url,
                }

        run_git(["checkout", base_branch], repo_path, github_token)

    if pending["repos"]:
        write_pending_prs(workspace_dir, pending)
    return remediation


def approve_pending_prs(config, github_token, workspace_dir):
    path, pending = load_pending_prs(workspace_dir)
    results = {}
    remaining = {"generated_at": pending.get("generated_at"), "repos": {}}

    for repo, pr in pending.get("repos", {}).items():
        try:
            pr_response = run_gh(
                [
                    "api",
                    f"repos/{repo}/pulls",
                    "-f",
                    f"title={pr['title']}",
                    "-f",
                    f"head={pr['head']}",
                    "-f",
                    f"base={pr['base']}",
                    "-f",
                    f"body={pr['body']}",
                ],
                resolve_workspace_path(workspace_dir),
                github_token,
            )
            pr_payload = json.loads(pr_response.stdout)
            results[repo] = {
                "status": "pr_created",
                "pr_url": pr_payload.get("html_url"),
                "branch": pr.get("head"),
                "issue_url": pr.get("issue_url"),
            }
        except (RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
            results[repo] = {
                "status": "pr_failed",
                "error": str(exc),
                "branch": pr.get("head"),
                "issue_url": pr.get("issue_url"),
            }
            remaining["repos"][repo] = pr

    if remaining["repos"]:
        path.write_text(json.dumps(remaining, indent=2) + "\n", encoding="utf-8")
    else:
        if path.exists():
            path.unlink()
    return results


def github_get_json(api_base, token, path, query=""):
    url = f"{api_base.rstrip('/')}{path}{query}"
    request = Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", "shadi-secops-agent")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def fetch_dependabot_alerts(api_base, token, repo):
    owner, name = repo.split("/", 1)
    path = f"/repos/{owner}/{name}/dependabot/alerts"
    return github_get_json(api_base, token, path, "?state=open")


def fetch_security_issues(api_base, token, repo, label):
    owner, name = repo.split("/", 1)
    path = f"/repos/{owner}/{name}/issues"
    query = f"?state=open&labels={label}"
    return github_get_json(api_base, token, path, query)


def fetch_code_scanning_alerts_gh(token, repo, cwd):
    """Use gh CLI to fetch open code scanning (SARIF / Trivy) alerts for a repo.
    Returns a list of alert dicts with structured location and message data.
    Returns an empty list if code scanning is not enabled for the repo.
    """
    try:
        result = run_gh(
            ["api", "--paginate", f"repos/{repo}/code-scanning/alerts",
             "--jq", '.[] | select(.state == "open")'],
            cwd,
            token,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").lower()
        if "404" in stderr or "not found" in stderr or "advanced security" in stderr:
            return []
        raise
    alerts = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return alerts


def parse_trivy_message(text):
    """Parse a Trivy SARIF message body into a dict with lower_snake_case keys."""
    fields = {}
    for line in (text or "").splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip().lower().replace(" ", "_")] = val.strip()
    return fields


def is_actionable_code_scanning_alert(alert):
    severity = (alert.get("rule") or {}).get("severity", "").lower()
    # SARIF: 'error' → critical, 'warning' → high
    return severity in ("error", "critical", "high", "warning")


def collect_security_report(config, github_token, allowlisted_repos, labels, workspace_dir=None):
    api_base = config.get("github", {}).get("api_base", "https://api.github.com")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": {},
        "skill_trace": [
            {
                "skill": "collect_security_issues",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    total_alerts = 0
    total_issues = 0

    with tracer.start_as_current_span("secops.github_fetch") as span:
        span.set_attribute("github.repo_count", len(allowlisted_repos))
        span.add_event("github_fetch.started", {"repos": ",".join(allowlisted_repos)})
        gh_cwd = resolve_workspace_path(workspace_dir) if workspace_dir else Path(".").resolve()
        gh_cwd.mkdir(parents=True, exist_ok=True)
        total_code_scanning = 0
        for repo in allowlisted_repos:
            repo_entry = {"dependabot": [], "issues": {}, "code_scanning": []}
            try:
                alerts = fetch_dependabot_alerts(api_base, github_token, repo)
                repo_entry["dependabot"] = alerts
                total_alerts += len(alerts)
            except (HTTPError, URLError, ValueError) as exc:
                repo_entry["dependabot_error"] = str(exc)

            for label in labels:
                try:
                    issues = fetch_security_issues(api_base, github_token, repo, label)
                    repo_entry["issues"][label] = issues
                    total_issues += len(issues)
                except (HTTPError, URLError, ValueError) as exc:
                    repo_entry["issues"][label] = {"error": str(exc), "items": []}

            # Fetch SARIF / code-scanning alerts via gh CLI (Trivy, CodeQL, etc.)
            try:
                cs_alerts = fetch_code_scanning_alerts_gh(github_token, repo, gh_cwd)
                repo_entry["code_scanning"] = cs_alerts
                actionable_cs = sum(1 for a in cs_alerts if is_actionable_code_scanning_alert(a))
                total_code_scanning += actionable_cs
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                repo_entry["code_scanning_error"] = str(exc)

            repo_alerts = len(repo_entry.get("dependabot", []))
            repo_issues = sum(
                len(v) if isinstance(v, list) else 0 for v in repo_entry["issues"].values()
            )
            repo_cs = len(repo_entry.get("code_scanning", []))
            span.add_event(
                "github_fetch.repo_done",
                {"repo": repo, "alerts": repo_alerts, "issues": repo_issues, "code_scanning": repo_cs},
            )
            report["repos"][repo] = {
                "dependabot_count": repo_alerts,
                "issue_counts": {
                    label: len(items) if isinstance(items, list) else 0
                    for label, items in repo_entry["issues"].items()
                },
                "code_scanning_count": repo_cs,
                "data": repo_entry,
            }

        span.add_event(
            "github_fetch.done",
            {"total_alerts": total_alerts, "total_issues": total_issues,
             "total_code_scanning": total_code_scanning},
        )
    return report, total_alerts, total_issues, total_code_scanning


def generate_llm_markdown(report, total_alerts, total_issues, llm_settings):
    try:
        from openai import AzureOpenAI, OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is required for LLM reports") from exc

    prompt = (
        "You are a SecOps assistant. Generate a Markdown report with these sections:\n"
        "1) Executive summary (2-4 bullets).\n"
        "2) Critical vulnerabilities only (Dependabot or issues).\n"
        "3) Remediation plan per repo (actionable steps).\n"
        "   - If a patch is available, propose code updates and a PR summary.\n"
        "   - If a patch is not available, state that remediation is blocked and list next steps.\n"
        "4) Risk notes if no critical findings.\n\n"
        "Use concise language and include repository names.\n\n"
        "Input JSON follows.\n"
    )
    def _slim_repo(repo_data):
        """Return a compact summary of a repo's findings for the LLM prompt."""
        slim = {
            "dependabot_count": repo_data.get("dependabot_count", 0),
            "code_scanning_count": repo_data.get("code_scanning_count", 0),
            "issue_counts": repo_data.get("issue_counts", {}),
            "dependabot": [],
            "code_scanning": [],
            "issues": {},
        }
        raw_data = repo_data.get("data", {})
        for alert in raw_data.get("dependabot", []):
            adv = alert.get("security_advisory") or {}
            vuln = alert.get("security_vulnerability") or {}
            pkg = vuln.get("package") or {}
            fp = vuln.get("first_patched_version") or {}
            slim["dependabot"].append({
                "number": alert.get("number"),
                "severity": (adv.get("severity") or vuln.get("severity") or "").lower(),
                "cve_id": adv.get("cve_id") or "",
                "summary": adv.get("summary") or "",
                "package": pkg.get("name") or "",
                "ecosystem": pkg.get("ecosystem") or "",
                "vulnerable_version_range": vuln.get("vulnerable_version_range") or "",
                "patched_version": fp.get("identifier") or "",
                "url": alert.get("html_url") or "",
            })
        for cs_alert in raw_data.get("code_scanning", []):
            if is_actionable_code_scanning_alert(cs_alert):
                instance = cs_alert.get("most_recent_instance") or {}
                fields = parse_trivy_message((instance.get("message") or {}).get("text", ""))
                slim["code_scanning"].append({
                    "cve_id": (cs_alert.get("rule") or {}).get("id", ""),
                    "severity": (cs_alert.get("rule") or {}).get("severity", ""),
                    "path": (instance.get("location") or {}).get("path", ""),
                    "package": fields.get("package", ""),
                    "fixed_version": fields.get("fixed_version", ""),
                })
        for label, items in (raw_data.get("issues") or {}).items():
            if isinstance(items, list):
                slim["issues"][label] = [
                    {"number": i.get("number"), "title": i.get("title"), "url": i.get("html_url")}
                    for i in items
                ]
            else:
                slim["issues"][label] = items
        return slim

    payload = {
        "generated_at": report.get("generated_at"),
        "total_dependabot_alerts": total_alerts,
        "total_labeled_issues": total_issues,
        "repos": {
            repo: _slim_repo(data) for repo, data in report.get("repos", {}).items()
        },
    }
    prompt = f"{prompt}{json.dumps(payload, indent=2)}"

    provider = llm_settings["provider"]
    api_key = llm_settings["api_key"]
    base_url = llm_settings["base_url"]
    model_name = llm_settings["model"]
    api_version = llm_settings.get("api_version")

    if provider in ("azure", "azure_openai", "openai") and api_version:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base_url,
            api_version=api_version,
        )
    else:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    timeout_seconds = float(os.getenv("SHADI_LLM_TIMEOUT", "180"))
    with tracer.start_as_current_span("secops.llm_generate") as span:
        span.set_attribute("llm.provider", provider)
        span.set_attribute("llm.model", model_name)
        span.add_event("llm.request_sent", {"provider": provider, "model": model_name})
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout_seconds,
            )
        except Exception as exc:
            span.record_exception(exc)
            span.add_event("llm.request_failed", {"error": str(exc)})
            raise RuntimeError(
                f"LLM report generation failed for provider '{provider}' and model '{model_name}' "
                f"(endpoint: {base_url!r}). "
                f"Root cause: {type(exc).__name__}: {exc}. "
                "Verify the secops/llm secrets for provider, endpoint, model, and API key."
            ) from exc
        span.add_event("llm.response_received")
        choices = getattr(response, "choices", None) or []
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if content:
                return content.strip()
    raise RuntimeError("LLM response did not contain text")


def write_report(report, workspace_dir, filename, total_alerts, total_issues, llm_settings):
    workspace_path = resolve_workspace_path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)
    report_path = workspace_path / filename
    markdown = generate_llm_markdown(report, total_alerts, total_issues, llm_settings)
    with tracer.start_as_current_span("secops.write_report") as span:
        span.set_attribute("report.path", str(report_path))
        report_path.write_text(markdown, encoding="utf-8")
        span.set_attribute("report.bytes", len(markdown.encode()))
        span.add_event("report.written", {"path": str(report_path)})
    return report_path


def resolve_tmp_dir(agent_id_envs=None):
    base = os.getenv("SHADI_TMP_DIR", "./.tmp")
    agent_id = os.getenv("SHADI_AGENT_ID")
    if not agent_id and agent_id_envs:
        for env_name in agent_id_envs:
            value = os.getenv(env_name)
            if value:
                agent_id = value
                break
    if agent_id:
        return os.path.join(base, agent_id)
    return base


def record_secops_memory(config, summary):
    secops_config = config.get("secops", {})
    tmp_dir = resolve_tmp_dir(("SHADI_OPERATOR_AGENT_ID", "SHADI_SECOPS_AGENT_ID"))
    default_db = os.path.join(tmp_dir, "shadi-secops", "secops_memory.db")
    db_path = (
        os.getenv("SHADI_SECOPS_MEMORY_DB")
        or os.getenv("SHADI_MEMORY_DB")
        or secops_config.get("memory_db")
        or default_db
    )

    memory_key_name = secops_config.get("memory_key", "secops/memory_key")
    scope = secops_config.get("memory_scope", "secops")

    payload = json.dumps(summary, indent=2)
    report_day = summary.get("report_day") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry_keys = [
        "security_report",
        f"security_report_{report_day}",
    ]
    try:
        # Resolve the actual encryption key value (not just the key name).
        shadi_store, session = create_secops_session()
        memory_key = require_shadi_secret(shadi_store, session, memory_key_name, "memory key").decode("utf-8").strip()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        store = SqlCipherMemoryStore(db_path, memory_key)
        results = []
        for entry_key in entry_keys:
            record_id = store.put(scope, entry_key, payload)
            results.append(str(record_id))
    except Exception as exc:
        return {
            "status": "error",
            "stderr": str(exc),
        }

    results = [item for item in results if item]
    if results:
        return {"status": "saved", "result": results}
    return {"status": "saved"}


# ── Individual ADK-exposed tools ─────────────────────────────────────────────
# The LLM chains these based on SKILL.md guidance.  State between steps is
# persisted as secops_raw_alerts.json in the workspace directory.

_RAW_ALERTS_FILE = "secops_raw_alerts.json"
_NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _resolve_human_github(secops_config, override=None):
    if override and override.strip():
        return override.strip()
    return (
        secops_config.get("human_github", "").strip()
        or os.getenv("SHADI_HUMAN_GITHUB", "").strip()
        or None
    )


def fetch_security_alerts(
    labels: str = "security,cve,vulnerability",
    repos: str | None = None,
) -> dict:
    """Fetch open Dependabot alerts, security-labeled issues, and SARIF code-scanning
    alerts (via gh CLI) for all allowlisted repos.  Saves raw data to the workspace for
    use by generate_security_report and remediate_vulnerabilities.  Call first.

    Args:
        labels: Comma-separated issue labels to search for.
        repos:  Optional comma-separated list of repos (owner/name) to scan.
                Must be a subset of the configured allowlist.  When omitted all
                allowlisted repos are scanned.
    """
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    store, session = create_secops_session()
    github_token, workspace, _, _ = get_secops_credentials(config, store, session)
    allowlist = secops_config.get("allowlist", [])
    if repos:
        requested = [r.strip() for r in repos.split(",") if r.strip()]
        allowlist_set = set(allowlist)
        allowlist = [r for r in requested if r in allowlist_set]
        if not allowlist:
            return {"status": "error", "error": f"None of the requested repos are in the allowlist: {requested}"}
    label_list = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]
    with tracer.start_as_current_span("secops.fetch_security_alerts") as span:
        span.set_attribute("fetch.labels", labels)
        span.set_attribute("fetch.repo_count", len(allowlist))
        report, total_alerts, total_issues, total_code_scanning = collect_security_report(
            config, github_token, allowlist, label_list, workspace_dir=workspace
        )
        workspace_path = resolve_workspace_path(workspace)
        raw_path = workspace_path / _RAW_ALERTS_FILE
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        span.set_attribute("fetch.total_alerts", total_alerts)
        span.set_attribute("fetch.total_issues", total_issues)
        span.set_attribute("fetch.total_code_scanning", total_code_scanning)
    return {
        "status": "ok",
        "dependabot_alerts": total_alerts,
        "labeled_issues": total_issues,
        "code_scanning_alerts": total_code_scanning,
        "repos": allowlist,
        "raw_data_path": str(raw_path),
    }


def generate_security_report(
    report_name: str = "secops_security_report.md",
    provider: str | None = None,
    human_github_handle: str | None = None,
) -> dict:
    """Generate a Markdown security report using the LLM from alert data saved by
    fetch_security_alerts.  Saves the report and records a memory entry."""
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    store, session = create_secops_session()
    _, workspace, _, _ = get_secops_credentials(config, store, session)
    llm_settings = get_llm_settings(config, store, session, provider_override=provider)
    raw_path = resolve_workspace_path(workspace) / _RAW_ALERTS_FILE
    if not raw_path.exists():
        return {"status": "error", "error": "No alert data found. Call fetch_security_alerts first."}
    report = json.loads(raw_path.read_text(encoding="utf-8"))
    total_alerts = sum(r.get("dependabot_count", 0) for r in report.get("repos", {}).values())
    total_issues = sum(
        sum(c for c in r.get("issue_counts", {}).values())
        for r in report.get("repos", {}).values()
    )
    human_github = _resolve_human_github(secops_config, human_github_handle)
    if human_github:
        human_did = get_human_did(store, session, human_github)
        if human_did:
            report["human"] = {"github_handle": human_github, "did": human_did}
    report_path = write_report(report, workspace, report_name, total_alerts, total_issues, llm_settings)
    memory_status = record_secops_memory(config, {
        "generated_at": report.get("generated_at"),
        "report_day": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "dependabot_alerts": total_alerts,
        "labeled_issues": total_issues,
        "repos": list(report.get("repos", {}).keys()),
        "report_path": str(report_path),
        "model": llm_settings["model"],
        "provider": llm_settings["provider"],
    })
    return {
        "status": "ok",
        "report_path": str(report_path),
        "dependabot_alerts": total_alerts,
        "labeled_issues": total_issues,
        "memory": memory_status,
    }


def remediate_vulnerabilities(
    human_github_handle: str | None = None,
    create_prs: bool = False,
    repos: str | None = None,
) -> dict:
    """Patch critical vulnerabilities from alert data saved by fetch_security_alerts.
    Forks repos, commits patches, and optionally opens PRs via gh CLI.

    Args:
        human_github_handle: GitHub handle of the human who will own the fork.
        create_prs:          Open a PR after each repo patch.
        repos:               Optional comma-separated list of repos (owner/name) to
                             remediate.  When omitted all repos in the saved alert data
                             are remediated.
    """
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    store, session = create_secops_session()
    github_token, workspace, _, _ = get_secops_credentials(config, store, session)
    raw_path = Path(workspace) / _RAW_ALERTS_FILE
    if not raw_path.exists():
        return {"status": "error", "error": "No alert data found. Call fetch_security_alerts first."}
    report = json.loads(raw_path.read_text(encoding="utf-8"))
    if repos:
        requested = {r.strip() for r in repos.split(",") if r.strip()}
        report = dict(report)
        report["repos"] = {k: v for k, v in report.get("repos", {}).items() if k in requested}
        if not report["repos"]:
            return {"status": "error", "error": f"None of the requested repos found in alert data: {sorted(requested)}"}
    human_github = _resolve_human_github(secops_config, human_github_handle)
    allow_prs = create_prs or bool(secops_config.get("auto_pr", False))
    remediation = remediate_repos(
        config, github_token, report, workspace,
        create_prs=allow_prs, fork_owner=human_github,
    )
    return {"status": "ok", "remediation": remediation}


def approve_queued_prs() -> dict:
    """Open PRs for all changes queued in secops_pending_prs.json after human review."""
    config_path, config = load_secops_config()
    store, session = create_secops_session()
    github_token, workspace, _, _ = get_secops_credentials(config, store, session)
    return approve_pending_prs(config, github_token, workspace)


def get_latest_report(report_name: str = "secops_security_report.md") -> dict:
    """Return the content of the latest security report from the workspace."""
    config_path, config = load_secops_config()
    store, session = create_secops_session()
    _, workspace, _, _ = get_secops_credentials(config, store, session)
    report_path = Path(workspace) / report_name
    if not report_path.exists():
        return {"status": "missing", "path": str(report_path)}
    return {"status": "ok", "path": str(report_path), "report": report_path.read_text(encoding="utf-8")}


def get_allowlist() -> dict:
    """Return the list of allowlisted repositories from the agent config."""
    _, config = load_secops_config()
    return {"status": "ok", "allowlist": config.get("secops", {}).get("allowlist", [])}


def get_agent_status() -> dict:
    """Return current workspace path, allowlist, and SLIM config info."""
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    tmp_dir = resolve_tmp_dir(("SHADI_OPERATOR_AGENT_ID", "SHADI_SECOPS_AGENT_ID"))
    workspace = secops_config.get("workspace_dir", str(Path(tmp_dir) / "shadi-secops"))
    return {
        "status": "ok",
        "config": str(config_path),
        "workspace": workspace,
        "allowlist": secops_config.get("allowlist", []),
        "slim_endpoint": secops_config.get("slim_endpoint", "http://localhost:47357"),
        "slim_identity": secops_config.get("slim_identity", "agntcy/secops/agent"),
    }


def lookup_cve(cve_id: str = "", package_name: str = "", max_results: int = 5) -> dict:
    """Query the NIST NVD database for CVE details and remediation guidance.

    Use this when you have a CVE ID from a Dependabot alert or want to look up
    vulnerabilities affecting a specific package.  Returns CVSS score, severity,
    description, CWE weaknesses, and reference URLs (vendor advisories, patches).

    Prefer cve_id when an alert already contains one.  Fall back to package_name
    for keyword searches (e.g. "requests 2.28" or "openssl 3.0").

    Args:
        cve_id:       Specific CVE identifier, e.g. "CVE-2023-44487".
        package_name: Package or keyword to search when cve_id is empty.
        max_results:  Max CVEs to return for keyword searches (1–20, default 5).

    Returns:
        {
          "status": "ok" | "not_found" | "error" | "rate_limited",
          "cves": [
            {
              "id": str,
              "published": str,
              "last_modified": str,
              "description": str,
              "cvss_v3": {"score": float, "severity": str, "vector": str} | None,
              "cvss_v2": {"score": float, "severity": str} | None,
              "cwe": [str],
              "references": [str],
            }
          ],
          "total_results": int,
        }
    """
    if not cve_id and not package_name:
        return {"status": "error", "error": "Provide cve_id or package_name"}

    params: dict[str, str] = {}
    if cve_id:
        params["cveId"] = cve_id.strip().upper()
    else:
        params["keywordSearch"] = package_name.strip()
        params["resultsPerPage"] = str(min(max(1, max_results), 20))

    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{_NVD_BASE}?{query}"

    req = Request(url)
    req.add_header("User-Agent", "shadi-secops-agent/1.0")
    nvd_api_key = os.environ.get("NVD_API_KEY", "")
    if nvd_api_key:
        req.add_header("apiKey", nvd_api_key)

    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in (403, 429):
            return {
                "status": "rate_limited",
                "error": (
                    f"NVD rate limit hit (HTTP {exc.code}). "
                    "Set NVD_API_KEY env var to raise quota from 5 to 50 req/30s."
                ),
            }
        if exc.code == 404:
            return {"status": "not_found", "error": f"CVE not found: {cve_id}"}
        return {"status": "error", "error": f"NVD API HTTP {exc.code}: {exc.reason}"}
    except URLError as exc:
        return {"status": "error", "error": f"Network error reaching NVD: {exc.reason}"}

    vulnerabilities = data.get("vulnerabilities", [])
    if not vulnerabilities:
        return {"status": "not_found", "cves": [], "total_results": 0}

    results = []
    for item in vulnerabilities:
        cve = item.get("cve", {})

        descriptions = cve.get("descriptions", [])
        desc = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

        # CVSS v3.1 preferred, fall back to v3.0
        cvss_v3 = None
        for key in ("cvssMetricV31", "cvssMetricV30"):
            metrics = cve.get("metrics", {}).get(key, [])
            if metrics:
                d = metrics[0].get("cvssData", {})
                cvss_v3 = {
                    "score": d.get("baseScore"),
                    "severity": d.get("baseSeverity"),
                    "vector": d.get("vectorString"),
                }
                break

        cvss_v2 = None
        v2_metrics = cve.get("metrics", {}).get("cvssMetricV2", [])
        if v2_metrics:
            d = v2_metrics[0].get("cvssData", {})
            cvss_v2 = {
                "score": d.get("baseScore"),
                "severity": v2_metrics[0].get("baseSeverity"),
            }

        cwe_list: list[str] = []
        for weakness in cve.get("weaknesses", []):
            for d in weakness.get("description", []):
                val = d.get("value", "")
                if val.startswith("CWE-"):
                    cwe_list.append(val)

        refs = [r["url"] for r in cve.get("references", []) if r.get("url")]

        results.append({
            "id": cve.get("id", ""),
            "published": cve.get("published", ""),
            "last_modified": cve.get("lastModified", ""),
            "description": desc,
            "cvss_v3": cvss_v3,
            "cvss_v2": cvss_v2,
            "cwe": cwe_list,
            "references": refs,
        })

    return {
        "status": "ok",
        "cves": results,
        "total_results": data.get("totalResults", len(results)),
    }


# kept for backward-compat; a2a_server and secops.py now call the individual tools
def skill_collect_security_issues(
    labels="security,cve,vulnerability",
    report_name="secops_security_report.md",
    provider=None,
    remediate=False,
    create_prs=False,
    human_github_handle=None,
):
    fetch_result = fetch_security_alerts(labels=labels)
    if fetch_result.get("status") != "ok":
        return fetch_result
    report_result = generate_security_report(
        report_name=report_name, provider=provider, human_github_handle=human_github_handle
    )
    if remediate:
        rem_result = remediate_vulnerabilities(
            human_github_handle=human_github_handle, create_prs=create_prs
        )
        report_result["remediation"] = rem_result.get("remediation")
    report_result["status"] = "success"
    report_result["repos"] = fetch_result.get("repos", [])
    return report_result
