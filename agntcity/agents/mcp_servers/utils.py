# Copyright 2025 AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Literal
from agntcy_app_sdk.factory import AgntcyFactory
from agents.exceptions import AuthError
from config.config import DEFAULT_MESSAGE_TRANSPORT, TRANSPORT_SERVER_ENDPOINT
import os

async def invoke_payment_mcp_tool(tool_name: Literal["create_payment", "list_transactions"]) -> dict:
  # don't invoke if identity auth is not enabled
  if os.getenv("IDENTITY_AUTH_ENABLED", "").lower() not in ["true", "enabled"]:
    return {}

  factory = AgntcyFactory()

  transport_instance = factory.create_transport(
    transport=DEFAULT_MESSAGE_TRANSPORT,
    endpoint=TRANSPORT_SERVER_ENDPOINT,
    name="default/default/fast_mcp_client",
  )

  client = await factory.create_client(
    "FastMCP",
    agent_topic="lungo_payment_service",
    transport=transport_instance,
    agent_url=os.getenv("MCP_PAYMENT_SERVICE_URL", "http://localhost:8081/mcp"),
  )

  try:
    async with client as c:
      result = await c.call_tool(tool_name, {})
      return result
  except Exception as e:
    error_message = str(e).lower()
    if any(keyword in error_message for keyword in ["authentication failed", "unauthorized"]):
      tool_action = "creating a payment" if tool_name == "create_payment" else "listing transactions"
      raise AuthError(
        f"Authentication failed or unauthorized access detected while {tool_action}. "
      ) from e
    raise
