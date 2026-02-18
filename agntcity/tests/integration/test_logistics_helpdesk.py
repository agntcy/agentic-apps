# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import time
import json
import logging
import pytest
import httpx

logger = logging.getLogger(__name__)

TRANSPORT_MATRIX = [
  pytest.param(
    {
      "DEFAULT_MESSAGE_TRANSPORT": "SLIM",
      "TRANSPORT_SERVER_ENDPOINT": "http://127.0.0.1:46357",
    },
    id="SLIM",
  )
]

@pytest.mark.parametrize("transport_config", TRANSPORT_MATRIX, indirect=True)
class TestHelpdeskFlows:
  @pytest.mark.agents(["logistics-farm", "accountant", "shipper", "helpdesk"])
  @pytest.mark.usefixtures("agents_up")
  def test_helpdesk_health(
          self,
          helpdesk_client,
          transport_config,
  ):
    logger.info(
      f"--- Test: test_helpdesk_health with transport {transport_config} ---"
    )

    # test helpdesk health endpoint
    health_resp = helpdesk_client.get("/v1/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data.get("status") == "alive", "Helpdesk health check failed"
