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

import asyncio
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
        endpoint: SLIM node endpoint (e.g., "http://localhost:46357")
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
        Async function that starts the server and returns (server, slim_app, server_task)

    Raises:
        ImportError: If slimrpc/slima2a not installed
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    from slima2a.types.a2a_pb2_slimrpc import add_A2AServiceServicer_to_server
    from slimrpc.channel import create_local_app

    # Create SRPC handler wrapping the A2A request handler
    handler = SRPCHandler(agent_card, request_handler)

    # Log config for debugging
    logger.info(f"[SLIM] Creating SLIMAppConfig for {config.local_id}")
    logger.info(f"[SLIM] shared_secret length: {len(config.shared_secret)} chars")
    logger.info(f"[SLIM] slim_client_config: {config.slim_config}")

    # Create SLIMAppConfig for the server
    app_config = slimrpc.SLIMAppConfig(
        identity=config.local_id,
        slim_client_config=config.slim_config,
        shared_secret=config.shared_secret,
    )

    # Shared state for the server
    _local_app = None
    _server = None

    async def _resilient_run(server):
        """Custom resilient run loop that handles transient SLIM errors.

        Unlike the default server.run(), this catches errors from listen_for_session()
        and continues rather than crashing the entire server.
        """
        local_app = server._local_app
        instance = local_app.id_str

        # Subscribe to all handler topics (same as server.run() but we do it once upfront)
        await local_app.subscribe(local_app.local_name)
        logger.info(f"[SLIM] Subscribed to {local_app.local_name}")

        for service_method, rpc_handler in server.handlers.items():
            from slimrpc.common import handler_name_to_pyname
            import slim_bindings as sb

            subscription_name = handler_name_to_pyname(
                local_app.local_name,
                service_method.service,
                service_method.method,
            )
            strs = subscription_name.components_strings()
            s_clone = sb.Name(strs[0], strs[1], strs[2], local_app.local_name.id)
            logger.info(f"[SLIM] Subscribing to {s_clone}")
            await local_app.subscribe(s_clone)
            server._pyname_to_handler[s_clone] = rpc_handler

        # Main loop - listen for sessions with error recovery
        consecutive_errors = 0
        max_consecutive_errors = 50  # Prevent infinite tight loops on persistent errors

        while True:
            try:
                logger.debug(f"[SLIM] {instance} waiting for new session")
                session = await local_app.listen_for_session()
                logger.info(f"[SLIM] {instance} received session: {session.id}")

                # Reset error counter on successful session
                consecutive_errors = 0

                # Handle session in background task
                asyncio.create_task(server.handle_session(session))

            except asyncio.CancelledError:
                logger.info(f"[SLIM] Server cancelled for {config.local_id}")
                raise

            except Exception as e:
                error_str = str(e)
                consecutive_errors += 1

                # Check if this is a transient SLIM routing error
                is_transient = any(msg in error_str for msg in [
                    "no matching found",
                    "subscription not found",
                    "session unknown",
                    "error in message forwarding",
                    "ProcessingError",
                ])

                if is_transient:
                    # Log at debug level for common transient errors
                    if consecutive_errors <= 3:
                        logger.warning(f"[SLIM] Transient error (#{consecutive_errors}): {e}")
                    else:
                        logger.debug(f"[SLIM] Transient error (#{consecutive_errors}): {e}")

                    # Brief sleep to avoid tight loop
                    await asyncio.sleep(0.1)

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(
                            f"[SLIM] Too many consecutive errors ({consecutive_errors}), "
                            f"attempting subscription refresh..."
                        )
                        # Try to refresh subscriptions
                        try:
                            await local_app.subscribe(local_app.local_name)
                            for s_clone in server._pyname_to_handler.keys():
                                await local_app.subscribe(s_clone)
                            consecutive_errors = 0
                            logger.info("[SLIM] Subscriptions refreshed successfully")
                        except Exception as refresh_err:
                            logger.error(f"[SLIM] Failed to refresh subscriptions: {refresh_err}")
                            # Wait longer before retrying
                            await asyncio.sleep(5.0)

                    continue
                else:
                    # Non-transient error - log and continue
                    logger.error(f"[SLIM] Unexpected error in session loop: {e}")
                    await asyncio.sleep(1.0)
                    continue

    async def start_server():
        """Start the SLIM server and return both server and its slim_app for reuse."""
        nonlocal _local_app, _server

        # Create the local app explicitly so we can share it
        _local_app = await create_local_app(app_config)

        # Create server from the local_app directly
        _server = slimrpc.Server(local_app=_local_app)

        # Register A2A service
        add_A2AServiceServicer_to_server(handler, _server)

        logger.info(f"[SLIM] Starting server for {config.local_id} -> {config.endpoint}")

        # Start our custom resilient run loop instead of server.run()
        server_task = asyncio.create_task(
            _resilient_run(_server),
            name=f"slim-server-{config.local_id}"
        )
        logger.info(f"[SLIM] Server run() task started for {config.local_id}")

        # Return a tuple of (server, local_app, server_task) so caller can:
        # 1. Get the local_app for client factory
        # 2. Monitor/cancel the server task if needed
        return _server, _local_app, server_task

    return start_server


def create_channel_factory_from_app(local_app) -> Callable[[str], "slimrpc.Channel"]:
    """Create a channel factory from an existing Slim app.

    This allows reusing the same Slim connection for both server and client operations.

    Args:
        local_app: An existing slim_bindings.Slim instance

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
            remote=topic,
            local_app=local_app,
        )
        logger.debug(f"[SLIM] Created channel -> {topic}")
        return channel

    return channel_factory


def create_client_factory_from_app(local_app, httpx_client=None):
    """Create an A2A ClientFactory from an existing Slim app.

    This allows reusing the same Slim connection for both server and client operations.

    Args:
        local_app: An existing slim_bindings.Slim instance
        httpx_client: Optional httpx client for fallback HTTP transport

    Returns:
        ClientFactory configured with SLIM transport support
    """
    if not SLIM_AVAILABLE:
        raise ImportError(
            "slimrpc and slima2a packages required for SLIM transport. "
            "Install with: uv pip install slima2a"
        )

    from a2a.client import ClientFactory
    from slima2a.client_transport import ClientConfig as SLIMClientConfig

    # Create channel factory using the existing app
    channel_factory = create_channel_factory_from_app(local_app)

    # Use slima2a's ClientConfig which has the slimrpc_channel_factory field
    client_config = SLIMClientConfig(
        supported_transports=["slimrpc"],
        streaming=True,
        httpx_client=httpx_client,
        slimrpc_channel_factory=channel_factory,
    )

    client_factory = ClientFactory(client_config)
    client_factory.register("slimrpc", SRPCTransport.create)

    logger.info(f"[SLIM] Created client factory from existing app")
    return client_factory


async def create_slim_channel_factory(config: SLIMConfig) -> Callable[[str], "slimrpc.Channel"]:
    """Create a channel factory for SLIM RPC client connections.

    This function creates a SLIM app (async) and returns a sync factory
    that creates channels using that app.

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

    from slimrpc.channel import create_local_app

    # Create SLIMAppConfig and the local app (async)
    app_config = slimrpc.SLIMAppConfig(
        identity=config.local_id,
        slim_client_config=config.slim_config,
        shared_secret=config.shared_secret,
    )

    # Create and connect the local Slim app
    local_app = await create_local_app(app_config)
    logger.info(f"[SLIM] Created local app for {config.local_id}")

    def channel_factory(topic: str) -> "slimrpc.Channel":
        """Create a channel to the specified remote topic."""
        # Channel just needs remote topic and the local_app
        channel = slimrpc.Channel(
            remote=topic,
            local_app=local_app,
        )
        logger.debug(f"[SLIM] Created channel {config.local_id} -> {topic}")
        return channel

    return channel_factory


async def create_slim_client_factory(config: SLIMConfig, httpx_client=None):
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

    from a2a.client import ClientFactory
    from slima2a.client_transport import ClientConfig as SLIMClientConfig

    # Create channel factory (async - creates and connects the Slim app)
    channel_factory = await create_slim_channel_factory(config)

    # Use slima2a's ClientConfig which has the slimrpc_channel_factory field
    client_config = SLIMClientConfig(
        supported_transports=["slimrpc"],
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

    Environment Variables:
        SLIM_ENDPOINT: Full endpoint URL (e.g., "http://slim-node:46357")
        SLIM_GATEWAY_HOST: Host name for SLIM gateway (alternative to SLIM_ENDPOINT)
        SLIM_GATEWAY_PORT: Port for SLIM gateway (used with SLIM_GATEWAY_HOST)
        SLIM_LOCAL_ID: Local agent identifier
        SLIM_SHARED_SECRET: MLS shared secret for encryption
        SLIM_TLS_INSECURE: Whether to skip TLS verification
    """
    import os

    def get_env(key: str, default: str) -> str:
        return os.environ.get(f"{prefix}{key}", os.environ.get(key, default))

    # Construct endpoint from SLIM_GATEWAY_HOST and SLIM_GATEWAY_PORT if SLIM_ENDPOINT not set
    endpoint = get_env("SLIM_ENDPOINT", "")
    if not endpoint:
        gateway_host = get_env("SLIM_GATEWAY_HOST", "localhost")
        gateway_port = get_env("SLIM_GATEWAY_PORT", "46357")
        endpoint = f"http://{gateway_host}:{gateway_port}"

    return SLIMConfig(
        endpoint=endpoint,
        local_id=get_env("SLIM_LOCAL_ID", "agntcy/tourist_scheduling/agent"),
        shared_secret=get_env("SLIM_SHARED_SECRET", "tourist-scheduling-demo-secret-key-32"),
        tls_insecure=get_env("SLIM_TLS_INSECURE", "true").lower() == "true",
    )


# =============================================================================
# GROUP-BASED SLIM TRANSPORT
# =============================================================================
# This implements a pub/sub pattern where:
# - A moderator (scheduler) creates a Group session
# - The moderator invites all agents to the group
# - All agents can publish/subscribe to messages in the group
# =============================================================================

@dataclass
class SLIMGroupConfig:
    """Configuration for SLIM Group transport.

    Attributes:
        endpoint: SLIM node endpoint
        local_id: Local agent identifier (org/namespace/agent)
        group_id: Group/channel identifier (org/namespace/group)
        shared_secret: MLS shared secret
        tls_insecure: Skip TLS verification
        is_moderator: Whether this agent is the group moderator
    """
    endpoint: str = "http://localhost:46357"
    local_id: str = "agntcy/tourist_scheduling/agent"
    group_id: str = "agntcy/tourist_scheduling/main-channel"
    shared_secret: str = "tourist-scheduling-demo-secret-key-32"
    tls_insecure: bool = True
    is_moderator: bool = False

    @property
    def slim_config(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "tls": {"insecure": self.tls_insecure},
        }


class SLIMGroupTransport:
    """Group-based SLIM transport for multi-agent pub/sub communication.

    This class provides:
    - Group session creation (for moderator)
    - Agent invitation to group
    - Pub/sub messaging within the group
    - Automatic reconnection handling
    """

    def __init__(self, config: SLIMGroupConfig):
        self.config = config
        self.slim_app = None
        self.group_session = None
        self.message_handlers = []
        self._running = False
        self._receive_task = None

    async def connect(self):
        """Connect to SLIM node and set up group participation."""
        import slim_bindings
        import datetime

        # Parse local_id into Name
        parts = self.config.local_id.split("/")
        if len(parts) != 3:
            raise ValueError(f"local_id must be org/namespace/agent format: {self.config.local_id}")

        # Create identity provider/verifier (identity is the local_id string, not the Name)
        provider = slim_bindings.IdentityProvider.SharedSecret(self.config.local_id, self.config.shared_secret)
        verifier = slim_bindings.IdentityVerifier.SharedSecret(self.config.local_id, self.config.shared_secret)

        # Create Slim app
        name = slim_bindings.Name(parts[0], parts[1], parts[2])
        self.slim_app = slim_bindings.Slim(name, provider, verifier, local_service=True)

        # Connect to gateway
        await self.slim_app.connect(self.config.slim_config)
        logger.info(f"[SLIMGroup] Connected as {self.config.local_id}")

        # Parse group_id into Name
        group_parts = self.config.group_id.split("/")
        if len(group_parts) != 3:
            raise ValueError(f"group_id must be org/namespace/group format: {self.config.group_id}")
        self._group_name = slim_bindings.Name(group_parts[0], group_parts[1], group_parts[2])

        # Subscribe to group topic
        await self.slim_app.subscribe(self._group_name)
        logger.info(f"[SLIMGroup] Subscribed to group {self.config.group_id}")

        # Set route for publishing to group
        await self.slim_app.set_route(self._group_name)

        if self.config.is_moderator:
            # Moderator creates the group session
            group_config = slim_bindings.SessionConfiguration.Group(
                timeout=datetime.timedelta(seconds=30),
                max_retries=10,
            )
            session, ack = await self.slim_app.create_session(
                destination=self._group_name,
                session_config=group_config,
            )
            await ack
            self.group_session = session
            logger.info(f"[SLIMGroup] Created group session as moderator: {session.id}")
        else:
            # Non-moderator agents subscribe to themselves to receive invitations
            self._local_name = slim_bindings.Name(parts[0], parts[1], parts[2])
            await self.slim_app.subscribe(self._local_name)
            await self.slim_app.set_route(self._local_name)
            logger.info(f"[SLIMGroup] Agent {self.config.local_id} subscribed to self, waiting for group invitation...")

    async def invite_agent(self, agent_id: str):
        """Invite an agent to the group (moderator only).

        Args:
            agent_id: Agent identifier in org/namespace/agent format
        """
        if not self.config.is_moderator:
            raise RuntimeError("Only moderator can invite agents")
        if not self.group_session:
            raise RuntimeError("Group session not created")

        import slim_bindings

        parts = agent_id.split("/")
        if len(parts) != 3:
            raise ValueError(f"agent_id must be org/namespace/agent format: {agent_id}")

        agent_name = slim_bindings.Name(parts[0], parts[1], parts[2])

        # Set route to agent so invitation can be delivered
        await self.slim_app.set_route(agent_name)

        # Invite and wait for acknowledgment
        invite_ack = await self.group_session.invite(agent_name)
        await invite_ack
        logger.info(f"[SLIMGroup] Invited {agent_id} to group (ack received)")

    async def remove_agent(self, agent_id: str):
        """Remove an agent from the group (moderator only)."""
        if not self.config.is_moderator:
            raise RuntimeError("Only moderator can remove agents")
        if not self.group_session:
            raise RuntimeError("Group session not created")

        import slim_bindings

        parts = agent_id.split("/")
        agent_name = slim_bindings.Name(parts[0], parts[1], parts[2])
        await self.group_session.remove(agent_name)
        logger.info(f"[SLIMGroup] Removed {agent_id} from group")

    async def publish(self, message: bytes, metadata: dict = None):
        """Publish a message to the group.

        Args:
            message: Raw message bytes
            metadata: Optional message metadata
        """
        if not self.group_session:
            # For non-moderators, we need to wait for invitation
            logger.warning("[SLIMGroup] No group session - waiting for invitation")
            return

        # Session.publish returns None directly (no ack awaitable in this version)
        await self.group_session.publish(message, metadata=metadata or {})
        logger.debug(f"[SLIMGroup] Published {len(message)} bytes to group")

    def add_message_handler(self, handler):
        """Add a callback for incoming messages.

        Args:
            handler: Async function(message_bytes, context) -> None
        """
        self.message_handlers.append(handler)

    async def start_receiving(self):
        """Start background task to receive group messages."""
        import asyncio

        self._running = True

        async def receive_loop():
            while self._running:
                try:
                    if not self.group_session:
                        # Wait for session (invitation)
                        session = await self.slim_app.listen_for_session()
                        self.group_session = session
                        logger.info(f"[SLIMGroup] Received group invitation: {session.id}")
                        continue

                    # Receive message from group
                    msg_ctx, msg_bytes = await self.group_session.get_message()

                    # Call all registered handlers
                    for handler in self.message_handlers:
                        try:
                            await handler(msg_bytes, msg_ctx)
                        except Exception as e:
                            logger.error(f"[SLIMGroup] Handler error: {e}")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[SLIMGroup] Receive error: {e}")
                    await asyncio.sleep(1)  # Backoff before retry

        self._receive_task = asyncio.create_task(receive_loop())
        logger.info(f"[SLIMGroup] Started message receiver for {self.config.local_id}")

    async def stop(self):
        """Stop receiving and disconnect."""
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self.slim_app:
            try:
                await self.slim_app.disconnect(self.config.endpoint)
            except Exception as e:
                logger.warning(f"[SLIMGroup] Disconnect error: {e}")
            logger.info(f"[SLIMGroup] Disconnected {self.config.local_id}")
