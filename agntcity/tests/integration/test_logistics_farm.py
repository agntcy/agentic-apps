# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
import logging
from pathlib import Path
import pytest

logger = logging.getLogger(__name__)


# Reuse the same tests across transports (add/remove configs as needed)
TRANSPORT_MATRIX = [
    pytest.param(
        {"DEFAULT_MESSAGE_TRANSPORT": "SLIM","TRANSPORT_SERVER_ENDPOINT": "http://127.0.0.1:46357"},
        id="SLIM"
    )
]


@pytest.mark.parametrize("transport_config", TRANSPORT_MATRIX, indirect=True)
class TestLogisticsFarmHealth:
    @pytest.mark.agents(["shipper"])
    @pytest.mark.usefixtures("agents_up")
    def test_logistics_farm_health(self, logistics_farm_client, transport_config):
        logger.info(f"\n---Test: test_logistics_farm_health with transport {transport_config}---")
        health_resp = logistics_farm_client.get("/v1/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data.get("status") == "alive", "Logistics farm health check failed"
