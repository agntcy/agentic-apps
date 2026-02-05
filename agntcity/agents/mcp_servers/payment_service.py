# Copyright 2025 AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import asyncio
import os
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from agntcy_app_sdk.app_sessions import AppContainer
from agntcy_app_sdk.factory import AgntcyFactory
from config.config import DEFAULT_MESSAGE_TRANSPORT, TRANSPORT_SERVER_ENDPOINT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment_service")

mcp = FastMCP(
  transport_security=TransportSecuritySettings(
    enable_dns_rebinding_protection=False, # Disabling this as we are managing security at a different layer of our infrastructure
  )
)

factory = AgntcyFactory("lungo.payment_mcp_server", enable_tracing=False)

@mcp.tool()
def create_payment() -> dict:
  """
  Creating a payment.
  Note: This is a sensitive operation that should enforce access control in a real-world payment system.
  """
  return {
    "ok": True,
    "status": "payment created",
    "payment_id": "stub_payment_id",  # fake payment ID
    "amount": 100.00,
    "currency": "USD"
  }

@mcp.tool()
def list_transactions() -> dict:
  """
  Listing transactions.
  Note: This is a sensitive operation that should enforce access control in a real-world payment system.
  """
  return {
    "ok": True,
    "status": "transactions retrieved",
    "transactions": [
      {"transaction_id": "txn_001", "amount": 50.00, "currency": "USD"},
      {"transaction_id": "txn_002", "amount": 75.00, "currency": "USD"}
    ]
  }


async def main():
  transport = factory.create_transport(
    DEFAULT_MESSAGE_TRANSPORT,
    endpoint=TRANSPORT_SERVER_ENDPOINT,
    name="default/default/lungo_payment_service",
  )

  app_session = factory.create_app_session(max_sessions=1)
  app_container = AppContainer(
    mcp,
    transport=transport,
    topic="lungo_payment_service",
  )
  app_session.add_app_container("default_session", app_container)
  await app_session.start_all_sessions(keep_alive=True)

if __name__ == "__main__":
  asyncio.run(main())