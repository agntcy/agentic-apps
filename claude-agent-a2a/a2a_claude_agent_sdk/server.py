"""FastAPI application factory and CLI entry point for the A2A Claude Agent server."""

from __future__ import annotations

import argparse
import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
)

from .config import AgentConfig, load_config
from .executor import ClaudeAgentExecutor

logger = logging.getLogger(__name__)


def _build_agent_card(cfg: AgentConfig, interfaces: list[AgentInterface]) -> AgentCard:
    http_cfg = cfg.bindings.jsonrpc
    base_url = f"http://{http_cfg.host}:{http_cfg.port}"
    return AgentCard(
        name=cfg.name,
        description=cfg.description,
        version=cfg.version,
        provider=AgentProvider(organization=cfg.organization, url=base_url),
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="general",
                name="General Assistant",
                description="General-purpose AI agent that can reason, write code, and use tools",
                tags=["general", "code", "reasoning"],
            )
        ],
        supported_interfaces=interfaces,
    )


async def _run_http(
    handler: DefaultRequestHandler,
    agent_card: AgentCard,
    cfg: AgentConfig,
) -> None:
    http_cfg = cfg.bindings.jsonrpc
    app = FastAPI(title=cfg.name, version=cfg.version)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc"),
        rest_routes=create_rest_routes(handler, path_prefix="/a2a/rest"),
    )
    config = uvicorn.Config(app, host=http_cfg.host, port=http_cfg.port)
    server = uvicorn.Server(config)
    logger.info("Starting HTTP server on %s:%d", http_cfg.host, http_cfg.port)
    await server.serve()


async def _run_slimrpc(
    handler: DefaultRequestHandler,
    agent_card: AgentCard,
    slim_cfg: object,
) -> None:
    import asyncio

    import slim_bindings
    from slima2a.handler import SRPCHandler
    from slima2a.types.v1.a2a_pb2_slimrpc import add_A2AServiceServicer_to_server

    slim_bindings.uniffi_set_event_loop(asyncio.get_running_loop())
    slim_app = await slim_bindings.get_global_service().create_app_from_slim_config_async(slim_cfg)
    local_name = slim_bindings.Name.from_str(slim_cfg.app.name)
    conn_id = await slim_app.connect(slim_cfg.node.address)
    await slim_app.subscribe(local_name, conn_id)

    server = slim_bindings.Server.new_with_connection(slim_app, local_name, conn_id)
    add_A2AServiceServicer_to_server(SRPCHandler(agent_card, handler), server)

    logger.info("Starting SLIM RPC server as %s", slim_cfg.app.name)
    await server.serve_async()


async def _run(cfg: AgentConfig) -> None:
    interfaces: list[AgentInterface] = []
    coroutines = []

    http_cfg = cfg.bindings.jsonrpc
    if http_cfg.enabled:
        base_url = f"http://{http_cfg.host}:{http_cfg.port}"
        interfaces += [
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"{base_url}/a2a/jsonrpc",
            ),
            AgentInterface(
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
                url=f"{base_url}/a2a/rest",
            ),
        ]

    slim_cfg = None
    if cfg.bindings.slimrpc.enabled:
        try:
            import slim_bindings

            slim_bindings.initialize_with_defaults()
            slim_cfg = slim_bindings.load_slim_config()
            interfaces.append(
                AgentInterface(
                    protocol_binding="slimrpc",
                    protocol_version="1.0",
                    url=slim_cfg.app.name,
                )
            )
        except Exception as exc:
            logger.warning("Could not load slim.yaml for agent card interface: %s", exc)

    if not http_cfg.enabled and slim_cfg is None:
        raise RuntimeError("No bindings are enabled. Set at least one binding to enabled: true.")

    agent_card = _build_agent_card(cfg, interfaces)
    handler = DefaultRequestHandler(
        agent_executor=ClaudeAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    if http_cfg.enabled:
        coroutines.append(_run_http(handler, agent_card, cfg))
    if slim_cfg is not None:
        coroutines.append(_run_slimrpc(handler, agent_card, slim_cfg))

    await asyncio.gather(*coroutines)


def main() -> None:
    parser = argparse.ArgumentParser(description="A2A Claude Agent server")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to agent.yaml config file (default: ./agent.yaml)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    asyncio.run(_run(cfg))
