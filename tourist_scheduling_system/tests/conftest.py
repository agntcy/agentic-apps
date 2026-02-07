# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Pytest configuration and shared fixtures for ADK agent tests.
"""

import pytest
import sys
import os
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "adk: marks tests that require google-adk (deselect with '-m \"not adk\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


@pytest.fixture(scope="session")
def adk_available():
    """Check if ADK is available."""
    try:
        from google.adk.agents.llm_agent import LlmAgent
        return True
    except ImportError:
        return False


@pytest.fixture
def reset_adk_state():
    """Reset ADK scheduler state before and after each test."""
    try:
        from agents.tools import clear_scheduler_state
        clear_scheduler_state()
        yield
        clear_scheduler_state()
    except ImportError:
        yield


@pytest.fixture
def sample_tourist_data():
    """Sample tourist registration data."""
    return {
        "tourist_id": "test_tourist_1",
        "availability_start": "2025-06-01T09:00:00",
        "availability_end": "2025-06-01T17:00:00",
        "preferences": ["culture", "history"],
        "budget": 100.0,
    }


@pytest.fixture
def sample_guide_data():
    """Sample guide registration data."""
    return {
        "guide_id": "test_guide_1",
        "categories": ["culture", "history", "food"],
        "available_start": "2025-06-01T10:00:00",
        "available_end": "2025-06-01T14:00:00",
        "hourly_rate": 50.0,
        "max_group_size": 5,
    }


@pytest.fixture
def multiple_tourists_data():
    """Sample data for multiple tourists."""
    return [
        {
            "tourist_id": f"tourist_{i}",
            "availability_start": "2025-06-01T09:00:00",
            "availability_end": "2025-06-01T17:00:00",
            "preferences": ["culture"] if i % 2 == 0 else ["history"],
            "budget": 80.0 + (i * 10),
        }
        for i in range(5)
    ]


@pytest.fixture
def multiple_guides_data():
    """Sample data for multiple guides."""
    return [
        {
            "guide_id": f"guide_{i}",
            "categories": ["culture"] if i % 2 == 0 else ["history"],
            "available_start": "2025-06-01T10:00:00",
            "available_end": "2025-06-01T14:00:00",
            "hourly_rate": 40.0 + (i * 5),
            "max_group_size": 2,
        }
        for i in range(3)
    ]
