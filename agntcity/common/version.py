"""Version and dependency utilities for Lungo exchange service.

Includes helpers to extract dependency versions and to derive a local
git-based fallback for build version and date when running outside CI.
"""

import configparser
import json
import logging
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Optional

try:  
    import tomllib  
except Exception:  
    tomllib = None

logger = logging.getLogger(__name__)


DISPLAY_NAMES = {
    "agntcy-app-sdk": "AGNTCY App SDK",
    "a2a-sdk": "A2A",
    "ioa-observe-sdk": "Observe SDK",
    "langgraph": "LangGraph",
    "agntcy-identity-service-sdk": "Identity",
    "mcp": "MCP",
}


def _extract_name_and_version(spec: str):
    """Extract base package name and version constraint from a dependency spec.
    Returns tuple (base_name, op, version) where op is one of '==', '>=', or '' if unspecified.
    """
    base = spec.split(';', 1)[0].strip()
    
    match = re.search(r"(==|>=)\s*([^;\s]+)", base)
    if match:
        op, ver = match.group(1), match.group(2)
        name_part = base.split(op)[0].strip()
        name = name_part.split('[', 1)[0].strip()
        return name, op, ver
    
    name = base.split('[', 1)[0].strip()
    return name, "", ""


def get_dependencies():
    """Get dependency versions from pyproject.toml and docker-compose.yaml"""
    dependencies = {}
    
    try:
        # Parse pyproject.toml for Python dependencies
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject_path.exists() and tomllib is not None:
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
            
            for dep in data.get('project', {}).get('dependencies', []):
                name, op, ver = _extract_name_and_version(dep)
                display = DISPLAY_NAMES.get(name)
                if display:
                    if op == '==' or op == '>=':
                        dependencies[display] = f"v{ver}"
                    else:
                        dependencies[display] = "unknown"
        
        # Get SLIM version from docker-compose.yaml
        compose_path = Path(__file__).parent.parent / "docker-compose.yaml"
        if compose_path.exists():
            with open(compose_path, 'r') as f:
                content = f.read()
                match = re.search(r'ghcr\.io/agntcy/slim:(\d+\.\d+\.\d+)', content)
                if match:
                    dependencies['SLIM'] = f"v{match.group(1)}"
                
                # Get NATS version at runtime if using 'latest' tag
                nats_match = re.search(r'image:\s*nats:(\S+)', content)
                if nats_match:
                    nats_tag = nats_match.group(1)
                    if nats_tag == 'latest':
                        try:
                            nats_host = 'nats' 
                            if 'TRANSPORT_SERVER_ENDPOINT' in os.environ:
                                endpoint = os.environ['TRANSPORT_SERVER_ENDPOINT']
                                if 'nats://' in endpoint:
                                    host_part = endpoint.split('://')[1].split(':')[0]
                                    if host_part:
                                        nats_host = host_part
                            
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                                sock.settimeout(2)
                                sock.connect((nats_host, 4222))
                                data = sock.recv(1024).decode('utf-8')
                                
                            if 'INFO ' in data:
                                info_line = data.split('INFO ')[1].split('\r\n')[0]
                                info = json.loads(info_line)
                                version = info.get('version', '')
                                if version and re.match(r'^\d+\.\d+\.\d+', str(version)):
                                    dependencies['NATS'] = f"v{version}"
                                else:
                                    dependencies['NATS'] = nats_tag
                            else:
                                dependencies['NATS'] = nats_tag
                        except Exception:
                            dependencies['NATS'] = nats_tag
                    else:
                        dependencies['NATS'] = f"v{nats_tag}" if not nats_tag.startswith('v') else nats_tag
        
    except Exception as e:
        logger.error(f"Error parsing dependencies: {e}")
    
    return dependencies


def _find_git_root(start: Path) -> Optional[Path]:
    """Find git root by ascending from start directory."""
    try:
        p = start.resolve()
        for ancestor in [p, *p.parents]:
            if (ancestor / ".git").exists():
                return ancestor
    except Exception:
        return None
    return None


def get_latest_tag_and_date(start: Optional[Path] = None) -> Optional[dict]:
    """Return newest tag and its dates from local git, or None if unavailable."""
    try:
        start = start or Path(__file__).parent
        git_root = _find_git_root(start)
        if not git_root:
            return None

        expected_root = Path(__file__).parent.parent.parent.resolve()
        try:
            git_root.resolve().relative_to(expected_root)
        except ValueError:
            logger.warning(f"Git root {git_root} is outside expected path {expected_root}")
            return None

        def _run(args: list[str]) -> str:
            return subprocess.check_output(
                args, cwd=git_root, text=True, stderr=subprocess.DEVNULL
            ).strip()

        out = _run([
            "git", "for-each-ref",
            "--sort=-creatordate",
            "--format=%(refname:short)\t%(creatordate:iso8601)\t%(creatordate:unix)",
            "refs/tags",
        ])
        
        if not out:
            return None
            
        line = out.splitlines()[0]
        parts = line.split("\t")
        if len(parts) < 3:
            return None
            
        return {"tag": parts[0], "created_iso": parts[1], "created_unix": parts[2]}
        
    except Exception as e:
        logger.debug(f"Git fallback failed: {e}")
        return None


def _format_build_date(build_date: str) -> str:
    """Format build date to just show the date part (YYYY-MM-DD)."""
    if build_date == "unknown":
        return build_date

    if ' ' in build_date:
        date_part = build_date.split(' ')[0]
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
            return date_part
    
    if 'T' in build_date:
        date_part = build_date.split('T')[0]
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
            return date_part
    
    if re.match(r'^\d{4}-\d{2}-\d{2}$', build_date):
        return build_date
    
    return build_date


def get_version_info(properties_file_path: Path, app_name: str = "lungo-exchange", service_name: str = "lungo-exchange") -> dict:
    """Get complete version information for the application.
    
    Args:
        properties_file_path: Path to the about.properties file
        
    Returns:
        Dictionary containing app, service, version, build_date, build_timestamp, image, and dependencies
    """
    try:
        expected_root = Path(__file__).parent.parent.resolve()
        try:
            properties_file_path.resolve().relative_to(expected_root)
        except ValueError:
            logger.warning(f"Properties file {properties_file_path} is outside expected path {expected_root}")
            properties_file_path = expected_root / "about.properties"

        # Try to read from about.properties first
        if properties_file_path.exists():
            config = configparser.ConfigParser()
            with open(properties_file_path, "r") as f:
                config_string = "[DEFAULT]\n" + f.read()
            config.read_string(config_string)
            
            props = dict(config["DEFAULT"])

            app_name_final = props.get("app.name", app_name)
            service_final = props.get("app.service", service_name)
            version = props.get("build.version", props.get("version", "unknown"))
            build_date = props.get("build.date", props.get("date", "unknown"))
            build_ts = props.get("build.timestamp", props.get("timestamp", "unknown"))
            image_name = props.get("image.name", "unknown")
            image_tag = props.get("image.tag", "unknown")
            image = (
                f"{image_name}:{image_tag}" if image_name != "unknown" and image_tag != "unknown" else image_name
            )

            # Fill in any missing values with git fallback
            if version == "unknown" or build_date == "unknown" or build_ts == "unknown":
                git_info = get_latest_tag_and_date(properties_file_path)
                if git_info:
                    if version == "unknown":
                        version = git_info.get("tag", version)
                    if build_date == "unknown":
                        build_date = git_info.get("created_iso", build_date)
                    if build_ts == "unknown":
                        build_ts = git_info.get("created_unix", build_ts)

            return {
                "app": app_name_final,
                "service": service_final,
                "version": version,
                "build_date": _format_build_date(build_date),
                "build_timestamp": build_ts,
                "image": image,
                "dependencies": get_dependencies(),
            }

        # No about.properties file found - use git fallback
        logger.error("No about.properties file found - metadata unavailable")
        git_info = get_latest_tag_and_date(properties_file_path)
        if git_info:
            return {
                "app": app_name,
                "service": service_name,
                "version": git_info.get("tag", "unknown"),
                "build_date": _format_build_date(git_info.get("created_iso", "unknown")),
                "build_timestamp": git_info.get("created_unix", "unknown"),
                "image": "unknown",
                "dependencies": get_dependencies(),
            }

        # No properties file and no git info
        return {
            "app": app_name,
            "service": service_name,
            "version": "unknown",
            "build_date": "unknown",
            "build_timestamp": "unknown",
            "image": "unknown",
            "dependencies": get_dependencies(),
        }

    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        return {
            "app": app_name,
            "service": service_name,
            "version": "unknown",
            "build_date": "unknown",
            "build_timestamp": "unknown",
            "image": "unknown",
            "dependencies": {},
        }
