# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
import logging
from pathlib import Path
import pytest

logger = logging.getLogger(__name__)
 
def load_logistics_prompt_cases():
    """Load logistics prompt cases from JSON in this directory.

        Expected schema:
            { "cases": [ {"id", "prompt"}, ... ] }
    """
    data_file = Path(__file__).parent / "logistics_prompt_cases.json"
    if not data_file.exists():
        raise FileNotFoundError(f"Prompt cases file not found: {data_file}")
    with data_file.open() as f:
        raw = json.load(f)

    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("logistics_prompt_cases.json must have a non-empty 'cases' list")

    for c in cases:
        missing = [k for k in ("id", "prompt") if k not in c]
        if missing:
            raise ValueError(f"Prompt case missing keys {missing}: {c}")

    return cases

LOGISTICS_PROMPT_CASES = load_logistics_prompt_cases()
    
# Reuse the same tests across transports (add/remove configs as needed)
TRANSPORT_MATRIX = [
    pytest.param(
        {"DEFAULT_MESSAGE_TRANSPORT": "SLIM", "TRANSPORT_SERVER_ENDPOINT": "http://127.0.0.1:46357"},
        id="SLIM"
    )
]

@pytest.mark.parametrize("transport_config", TRANSPORT_MATRIX, indirect=True)
class TestLogisticsHealth:
    @pytest.mark.agents(["shipper"])
    @pytest.mark.usefixtures("agents_up")

    def test_logistics_supervisor_health(self, logistics_supervisor_client, transport_config):
        logger.info(f"\n---Test: test_logistics_supervisor_health with transport {transport_config}---")
        health_resp = logistics_supervisor_client.get("/v1/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data.get("status") == "alive", "Logistics supervisor health check failed"


@pytest.mark.parametrize("transport_config", TRANSPORT_MATRIX, indirect=True)
class TestLogisticsSupervisorFlows:
    @pytest.mark.agents(["logistics-farm", "accountant", "shipper"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in LOGISTICS_PROMPT_CASES if c["id"] == "logistics_order"],
        ids=["logistics_order"],
    )
    def test_logistics_order(self, logistics_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_logistics_order ({prompt_case['id']}) with transport {transport_config}---")
        resp = logistics_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "successfully delivered" in data["response"], "Expected successful delivery message in response"

    @pytest.mark.agents(["logistics-farm", "accountant", "shipper"])
    @pytest.mark.usefixtures("agents_up")
    def test_logistics_order_streaming(self, logistics_supervisor_client, transport_config):
        logger.info(f"\n---Test: test_logistics_order_streaming with transport {transport_config}---")
        
        prompt = "I want to order 5000 lbs of coffee for 3.52 $ from the Tatooine farm."
        
        with logistics_supervisor_client.stream(
            "POST",
            "/agent/prompt/stream",
            json={"prompt": prompt}
        ) as resp:
            assert resp.status_code == 200
            
            events = []
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    assert "response" in data
                    events.append(data["response"])
            
            # Should have multiple events (at least 6)
            assert len(events) >= 6, f"Expected at least 6 events, got {len(events)}"
            
            # Final message should contain delivery confirmation
            final_message = str(events[-1])
            assert "successfully delivered" in final_message.lower()
