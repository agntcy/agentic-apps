"""Configuration loading for the A2A Claude Agent server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class HttpBindingConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class SlimRpcBindingConfig:
    enabled: bool = False
    url: str = "http://localhost:46357"
    namespace: str = "agntcy"
    group: str = "default"
    name: str = "claude-agent"
    secret: str = "secretsecretsecretsecretsecretsecret"


@dataclass
class BindingsConfig:
    jsonrpc: HttpBindingConfig = field(default_factory=HttpBindingConfig)
    slimrpc: SlimRpcBindingConfig = field(default_factory=SlimRpcBindingConfig)


@dataclass
class AgentConfig:
    name: str = "Claude Agent"
    description: str = "AI assistant powered by Claude Agent SDK, accessible via A2A protocol"
    version: str = "1.0.0"
    organization: str = "tehsmash"
    bindings: BindingsConfig = field(default_factory=BindingsConfig)


def _parse_http(raw: dict[str, Any]) -> HttpBindingConfig:
    return HttpBindingConfig(
        enabled=raw.get("enabled", True),
        host=raw.get("host", "0.0.0.0"),
        port=raw.get("port", 8000),
    )


def _parse_slimrpc(raw: dict[str, Any]) -> SlimRpcBindingConfig:
    return SlimRpcBindingConfig(
        enabled=raw.get("enabled", False),
        url=raw.get("url", "http://localhost:46357"),
        namespace=raw.get("namespace", "agntcy"),
        group=raw.get("group", "default"),
        name=raw.get("name", "claude-agent"),
        secret=raw.get("secret", "secretsecretsecretsecretsecretsecret"),
    )


def load_config(path: str | Path | None = None) -> AgentConfig:
    """Load agent config from a YAML file.

    Searches for ``agent.yaml`` in the current directory if *path* is not given.
    Missing file is fine — defaults are used.
    """
    if path is None:
        path = Path(os.getcwd()) / "agent.yaml"

    path = Path(path)
    if not path.exists():
        return AgentConfig()

    with path.open() as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    agent_raw = raw.get("agent", {})
    bindings_raw = raw.get("bindings", {})

    bindings = BindingsConfig(
        jsonrpc=_parse_http(bindings_raw.get("jsonrpc", {})),
        slimrpc=_parse_slimrpc(bindings_raw.get("slimrpc", {})),
    )

    return AgentConfig(
        name=agent_raw.get("name", "Claude Agent"),
        description=agent_raw.get("description", AgentConfig.description),
        version=agent_raw.get("version", "1.0.0"),
        organization=agent_raw.get("organization", "tehsmash"),
        bindings=bindings,
    )
