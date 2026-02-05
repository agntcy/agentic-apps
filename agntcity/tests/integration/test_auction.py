# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import re
from pathlib import Path
import pytest

from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)

# Reuse the same tests across transports (add/remove configs as needed)
TRANSPORT_MATRIX = [
    pytest.param(
        {"DEFAULT_MESSAGE_TRANSPORT": "SLIM", "TRANSPORT_SERVER_ENDPOINT": "http://127.0.0.1:46357"},
        id="SLIM"
    ),
    pytest.param(
        {"DEFAULT_MESSAGE_TRANSPORT": "NATS", "TRANSPORT_SERVER_ENDPOINT": "nats://127.0.0.1:4222"},
        id="NATS"
    ),
]

model = SentenceTransformer('all-MiniLM-L6-v2')

def get_semantic_similarity(text1, text2, model):
    embeddings1 = model.encode(text1, convert_to_tensor=True)
    embeddings2 = model.encode(text2, convert_to_tensor=True)
    cosine_score = util.cos_sim(embeddings1, embeddings2)
    return cosine_score.item()


def load_auction_prompt_cases():
    """Load auction prompt cases from JSON.

    Expects a file named 'auction_prompt_cases.json' in this directory with:
      { "cases": [ {"id", "prompt", "reference_responses", "expected_min_similarity"?}, ... ] }
    """
    data_file = Path(__file__).parent / "auction_prompt_cases.json"
    if not data_file.exists():
        raise FileNotFoundError(f"Prompt cases file not found: {data_file}")
    with data_file.open() as f:
        raw = json.load(f)

    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("auction_prompt_cases.json must have a non-empty 'cases' list")

    for c in cases:
        missing = [k for k in ("id", "prompt", "reference_responses") if k not in c]
        if missing:
            raise ValueError(f"Prompt case missing keys {missing}: {c}")
        if not c["reference_responses"]:
            raise ValueError(f"Prompt case '{c['id']}' has empty reference_responses")

    return cases


AUCTION_PROMPT_CASES = load_auction_prompt_cases()

@pytest.mark.parametrize("transport_config", TRANSPORT_MATRIX, indirect=True)
class TestAuctionFlows:
    @pytest.mark.agents(["brazil-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "brazil_inventory"],
        ids=["brazil_inventory"],
    )
    def test_auction_brazil_inventory(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_brazil_inventory ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        assert "response" in data
        assert re.search(r'\b[\d,]+\s*(pounds|lbs\.?)\b', data["response"]), "Expected '<number> pounds or <number> lbs or <number> units.' in string"

    @pytest.mark.agents(["weather-mcp", "colombia-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "colombia_inventory"],
        ids=["colombia_inventory"],
    )
    def test_auction_colombia_inventory(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_colombia_inventory ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        assert "response" in data
        assert re.search(r'\b[\d,]+\s*(pounds|lbs\.?)\b', data["response"]), "Expected '<number> pounds or <number> lbs or <number> units.' in string"

    @pytest.mark.agents(["vietnam-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "vietnam_inventory"],
        ids=["vietnam_inventory"],
    )
    def test_auction_vietnam_inventory(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_vietnam_inventory ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data) 
        assert "response" in data
        assert re.search(r'\b[\d,]+\s*(pounds|lbs\.?)\b', data["response"]), "Expected '<number> pounds or <number> lbs or <number> units.' in string"


    @pytest.mark.agents(["weather-mcp", "brazil-farm", "colombia-farm", "vietnam-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "all_farms_yield"],
        ids=["all_farms_yield"],
    )
    def test_auction_all_farms_inventory(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_all_farms_inventory ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        assert "response" in data
        assert "brazil" in data["response"].lower()
        assert "colombia" in data["response"].lower()
        assert "vietnam" in data["response"].lower()

    @pytest.mark.agents(["brazil-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "brazil_create_order"],
        ids=["brazil_create_order"],
    )
    def test_auction_create_order_brazil(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_create_order_brazil ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code in [200, 500]
        
        # If 500, expect identity verification failure for Brazil Coffee Farm
        if resp.status_code == 500:
            data = resp.json()
            logger.info(f"Error response: {data}")
            assert "detail" in data
            detail_lower = data["detail"].lower()
            assert "identity verification failed" in detail_lower
            assert "brazil" in detail_lower

    @pytest.mark.agents(["weather-mcp","colombia-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "colombia_create_order"],
        ids=["colombia_create_order"],
    )
    def test_auction_create_order_colombia(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_create_order_colombia ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        assert "response" in data
        response = data["response"].lower()
        assert "successful" in response
        assert "order id" in response, "Expected order id in response"
        assert "tracking number" in response, "Expected tracking number in response"

    @pytest.mark.agents(["vietnam-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "vietnam_create_order"],
        ids=["vietnam_create_order"],
    )
    def test_auction_create_order_vietnam(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_create_order_vietnam ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        response = data["response"].lower()
        assert "successful" in response
        assert "order id" in response, "Expected order id in response"
        assert "tracking number" in response, "Expected tracking number in response"

    @pytest.mark.agents(["brazil-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "invalid_prompt"],
        ids=["invalid_prompt"],
    )
    def test_auction_invalid_prompt(self, auction_supervisor_client, transport_config, prompt_case):
        logger.info(f"\n---Test: test_auction_invalid_prompt ({prompt_case['id']}) with transport {transport_config}---")
        resp = auction_supervisor_client.post(
            "/agent/prompt",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info(data)
        assert "I'm not sure how to handle that" in data["response"]

    @pytest.mark.agents(["weather-mcp", "brazil-farm", "colombia-farm", "vietnam-farm"])
    @pytest.mark.usefixtures("agents_up")
    @pytest.mark.parametrize(
        "prompt_case",
        [c for c in AUCTION_PROMPT_CASES if c["id"] == "all_farms_yield"],
        ids=["all_farms_yield_streaming"],
    )
    def test_auction_all_farms_inventory_streaming(self, auction_supervisor_client, transport_config, prompt_case):
        """Test the streaming endpoint returns multiple chunks with all farm data."""
        logger.info(f"\n---Test: test_auction_all_farms_inventory_streaming ({prompt_case['id']}) with transport {transport_config}---")
        
        resp = auction_supervisor_client.post(
            "/agent/prompt/stream",
            json={"prompt": prompt_case["prompt"]}
        )
        assert resp.status_code == 200
        
        # Collect all chunks from the stream
        chunks = []
        for line in resp.iter_lines():
            if line:
                chunk_data = json.loads(line)
                if "response" in chunk_data:
                    chunks.append(chunk_data["response"])
                    logger.info(f"Chunk: {chunk_data['response']}")
        
        # Validate streaming behavior and farm coverage
        assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
        full_response = "\n".join(chunks).lower()
        assert "brazil" in full_response
        assert "colombia" in full_response
        assert "vietnam" in full_response

    