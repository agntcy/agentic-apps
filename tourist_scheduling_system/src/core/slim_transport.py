#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
SLIM Transport Layer for Tourist Scheduling System

Provides SLIMA2A integration enabling A2A protocol over SLIM messaging.
Uses slimrpc for RPC-style communication with MLS encryption.

Key components:
- SLIMConfig: Configuration dataclass for SLIM connection settings
- SLIMRPCHandler: Wraps A2A DefaultRequestHandler for SLIM transport
- create_slim_channel_factory: Creates slimrpc channels for client connections
- SLIMTransport: Client transport implementation for A2A over SLIM

Usage:
    # Server side
    from core.slim_transport import SLIMConfig, create_slim_server

    config = SLIMConfig(
        endpoint="http://localhost:46357",
        local_id="agntcy/tourist_scheduling/scheduler",
        shared_secret="tourist-scheduling-demo-secret-key-32"
    )
    server = create_slim_server(config, agent_card, request_handler)
    await server.start()

    # Client side
    from core.slim_transport import SLIMConfig, create_slim_client_factory

    config = SLIMConfig(
        endpoint="http://localhost:46357",
        local_id="agntcy/tourist_scheduling/guide",
        shared_secret="tourist-scheduling-demo-secret-key-32"
    )
    client_factory = create_slim_client_factory(config)
    client = client_factory.create(card=agent_card)
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Conditional imports - slimrpc/slima2a may not be installed
try:
    import slimrpc
    from slima2a.handler import SRPCHandler
    from slima2a.client_transport import SRPCTransport
    SLIM_AVAILABLE = True
except ImportError:
    SLIM_AVAILABLE = False
    slimrpc = None  # type: ignore
    SRPCHandler = None  # type: ignore
    SRPCTransport = None  # type: ignore
    logger.warning("slimrpc/slima2a not installed - SLIM transport unavailable")


@dataclass
class SLIMConfig:
    """Configuration for SLIM transport connection.

    Attributes:
        endpoint: SLIM gateway endpoint (e.g., "http://localhost:46357")
        local_id: Local agent identifier in format "org/namespace/agent"
        shared_secret: MLS shared secret for encryption (min 32 chars)
        tls_insecure: Whether to skip TLS verification (dev only)
    """
    endpoint: str = "http://localhost:46357"
    local_id: str = "agntcy/tourist_scheduling/agent"
    shared_secret: str = "tourist-scheduling-demo-secret-key-32"  # min 32 chars
    tls_insecure: bool = True

    @property
    def slim_config(self) -> dict:
        """Return SLIM connection config dict for slimrpc."""
        return {
            "endpoint": self.endpoint,
            "tls": {
                "insecure": self.tls_insecure,
            },
        }


def check_slim_available() -> bool:
    """Check if SLIM transport is available."""
    return SLIM_AVAILABLE


async def create_slim_app(config: SLIMConfig):
    """Create a SLIM application instance for server or client use.

    Args:
        config: SLIM configuration

    Returns:
        slim_bindings.Slim instance ready to use
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    import slim_bindings

    # Create identity provider with shared secret
    provider = slim_bindings.IdentityProvider.shared_secret(config.shared_secret)
    verifier = slim_bindings.IdentityVerifier.shared_secret(config.shared_secret)

    # Parse local_id into Name (org/namespace/app format)
    parts = config.local_id.split("/")
    if len(parts) == 3:
        name = slim_bindings.Name(parts[0], parts[1], parts[2])
    else:
        name = slim_bindings.Name("agntcy", "tourist_scheduling", config.local_id)

    # Create Slim instance
    slim_app = slim_bindings.Slim(name, provider, verifier, local_service=True)

    # Connect to gateway as a client (for routing)
    await slim_app.connect(config.slim_config)

    return slim_app


def create_slim_server(
    config: SLIMConfig,
    agent_card,
    request_handler,
):
    """Create a SLIM RPC server for A2A agent.

    Args:
        config: SLIM configuration
        agent_card: A2A AgentCard describing the agent
        request_handler: A2A DefaultRequestHandler for processing requests

    Returns:
        A tuple of (slimrpc.Server, async start function)

    Raises:
        ImportError: If slimrpc/slima2a not installed
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    from slima2a.types.a2a_pb2_slimrpc import add_A2AServiceServicer_to_server

    # Create SRPC handler wrapping the A2A request handler
    handler = SRPCHandler(agent_card, request_handler)

    # Create SLIMAppConfig for the server
    app_config = slimrpc.SLIMAppConfig(
        identity=config.local_id,
        slim_client_config=config.slim_config,
        shared_secret=config.shared_secret,
    )

    async def start_server():
        """Start the SLIM server."""
        # Create server from app config (this creates the Slim app internally)
        server = await slimrpc.Server.from_slim_app_config(app_config)

        # Register A2A service
        add_A2AServiceServicer_to_server(handler, server)

        logger.info(f"[SLIM] Starting server for {config.local_id} -> {config.endpoint}")

        # Start serving (run is the correct method)
        await server.run()
        return server

    return start_server

    logger.info(f"[SLIM] Created server for {config.local_id} -> {config.endpoint}")
    return server


def create_slim_channel_factory(config: SLIMConfig) -> Callable[[str], "slimrpc.Channel"]:
    """Create a channel factory for SLIM RPC client connections.

    Args:
        config: SLIM configuration

    Returns:
        Factory function that creates slimrpc.Channel for a given topic
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    def channel_factory(topic: str) -> "slimrpc.Channel":
        """Create a channel to the specified remote topic."""
        channel = slimrpc.Channel(
            local=config.local_id,
            remote=topic,
            slim=config.slim_config,
            shared_secret=config.shared_secret,
        )
        logger.debug(f"[SLIM] Created channel {config.local_id} -> {topic}")
        return channel

    return channel_factory


def create_slim_client_factory(config: SLIMConfig, httpx_client=None):
    """Create an A2A ClientFactory configured for SLIM transport.

    Args:
        config: SLIM configuration
        httpx_client: Optional httpx client for fallback HTTP transport

    Returns:
        ClientFactory configured with SLIM transport support
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    from a2a.client import ClientFactory, ClientConfig

    channel_factory = create_slim_channel_factory(config)

    client_config = ClientConfig(
        supported_transports=["JSONRPC", "slimrpc"],
        streaming=True,
        httpx_client=httpx_client,
        slimrpc_channel_factory=channel_factory,
    )

    client_factory = ClientFactory(client_config)
    client_factory.register("slimrpc", SRPCTransport.create)

    logger.info(f"[SLIM] Created client factory for {config.local_id}")
    return client_factory


def minimal_slim_agent_card(agent_id: str, url: Optional[str] = None):
    """Create a minimal AgentCard for SLIM transport.

    Args:
        agent_id: Agent identifier (used as URL topic for SLIM)
        url: Optional HTTP URL (for fallback transport)

    Returns:
        AgentCard with slimrpc transport enabled
    """
    from a2a.client.client_factory import minimal_agent_card

    # Create card with slimrpc as supported transport
    # The agent_id becomes the topic for SLIM routing
    return minimal_agent_card(agent_id, ["slimrpc"])


# Environment variable names for SLIM configuration
SLIM_ENV_VARS = {
    "SLIM_ENDPOINT": "endpoint",
    "SLIM_LOCAL_ID": "local_id",
    "SLIM_SHARED_SECRET": "shared_secret",
    "SLIM_TLS_INSECURE": "tls_insecure",
}


def config_from_env(prefix: str = "") -> SLIMConfig:
    """Load SLIM configuration from environment variables.

    Args:
        prefix: Optional prefix for env vars (e.g., "SCHEDULER_")

    Returns:
        SLIMConfig populated from environment
    """
    import os

    def get_env(key: str, default: str) -> str:
        return os.environ.get(f"{prefix}{key}", os.environ.get(key, default))

    return SLIMConfig(
        endpoint=get_env("SLIM_ENDPOINT", "http://localhost:46357"),
        local_id=get_env("SLIM_LOCAL_ID", "agntcy/tourist_scheduling/agent"),
        shared_secret=get_env("SLIM_SHARED_SECRET", "tourist-scheduling-demo-secret-key-32"),
        tls_insecure=get_env("SLIM_TLS_INSECURE", "true").lower() == "true",
    )
