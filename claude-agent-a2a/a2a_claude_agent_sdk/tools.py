"""Custom MCP tools exposed to Claude so it can attach A2A artifacts."""

from collections.abc import Awaitable, Callable
from typing import Any

from claude_agent_sdk import McpSdkServerConfig, SdkMcpTool, create_sdk_mcp_server, tool


def create_artifact_mcp_server(
    on_artifact: Callable[[dict[str, Any]], Awaitable[None]],
) -> McpSdkServerConfig:
    """Return an in-process MCP server with a single ``add_artifact`` tool.

    *on_artifact* is called immediately for each artifact so the executor can
    publish ``TaskArtifactUpdateEvent``s as Claude produces them.
    """

    @tool(
        "add_artifact",
        "Add a structured artifact to the A2A task response. "
        "Call this to attach output data (text, code, or any content) "
        "that will be delivered as an A2A artifact to the calling agent.",
        {"content": str, "name": str, "mime_type": str},
    )
    async def add_artifact(args: dict[str, Any]) -> dict[str, Any]:
        name = args.get("name", "response")
        await on_artifact(
            {
                "content": args["content"],
                "name": name,
                "mime_type": args.get("mime_type", "text/plain"),
            }
        )
        return {"content": [{"type": "text", "text": f"Artifact '{name}' added."}]}

    return create_sdk_mcp_server("a2a_artifacts", version="1.0.0", tools=[add_artifact])
