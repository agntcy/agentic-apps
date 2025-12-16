#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tests for A2A agent card loader.
"""

import pytest
from pathlib import Path


class TestA2ACardLoader:
    """Test suite for A2A card loading functionality."""

    def test_a2a_cards_dir_exists(self):
        """Test that the a2a_cards directory exists."""
        from src.core.a2a_cards import A2A_CARDS_DIR
        assert A2A_CARDS_DIR.exists(), f"A2A cards directory not found: {A2A_CARDS_DIR}"

    def test_list_available_cards(self):
        """Test listing available agent cards."""
        from src.core.a2a_cards import list_available_cards

        cards = list_available_cards()
        assert isinstance(cards, list)
        assert "scheduler_agent" in cards
        assert "guide_agent" in cards
        assert "tourist_agent" in cards
        assert "ui_agent" in cards

    def test_load_scheduler_card_json(self):
        """Test loading scheduler card as JSON dict."""
        from src.core.a2a_cards import load_agent_card_json

        data = load_agent_card_json("scheduler_agent")
        assert isinstance(data, dict)
        assert data["name"] == "Tourist Scheduling Coordinator"
        assert data["protocolVersion"] == "0.3.0"
        assert data["version"] == "2.0.0"
        assert "skills" in data
        assert len(data["skills"]) == 4  # 4 scheduler skills

    def test_load_scheduler_card(self):
        """Test loading scheduler card as AgentCard object."""
        from src.core.a2a_cards import load_agent_card
        from a2a.types import AgentCard

        card = load_agent_card("scheduler_agent")
        assert isinstance(card, AgentCard)
        assert card.name == "Tourist Scheduling Coordinator"
        assert card.version == "2.0.0"
        assert card.skills is not None
        assert len(card.skills) == 4

    def test_load_card_with_url_override(self):
        """Test loading card with URL override."""
        from src.core.a2a_cards import load_agent_card

        custom_url = "http://custom-host:9999/"
        card = load_agent_card("scheduler_agent", url_override=custom_url)
        assert card.url == custom_url

    def test_get_scheduler_card(self):
        """Test get_scheduler_card helper."""
        from src.core.a2a_cards import get_scheduler_card

        card = get_scheduler_card(host="myhost", port=8080)
        assert card.url == "http://myhost:8080/"
        assert card.name == "Tourist Scheduling Coordinator"

    def test_get_guide_card(self):
        """Test get_guide_card helper."""
        from src.core.a2a_cards import get_guide_card

        card = get_guide_card(guide_id="marco", host="localhost", port=10001)
        assert card.url == "http://localhost:10001/"
        assert "marco" in card.name.lower()

    def test_get_tourist_card(self):
        """Test get_tourist_card helper."""
        from src.core.a2a_cards import get_tourist_card

        card = get_tourist_card(tourist_id="alice", host="localhost", port=10002)
        assert card.url == "http://localhost:10002/"
        assert "alice" in card.name.lower()

    def test_get_ui_card(self):
        """Test get_ui_card helper."""
        from src.core.a2a_cards import get_ui_card

        card = get_ui_card(host="0.0.0.0", port=10021)
        assert card.url == "http://0.0.0.0:10021/"
        assert "Dashboard" in card.name or "Monitor" in card.name

    def test_load_nonexistent_card_raises(self):
        """Test that loading a non-existent card raises FileNotFoundError."""
        from src.core.a2a_cards import load_agent_card_json

        with pytest.raises(FileNotFoundError):
            load_agent_card_json("nonexistent_agent")

    def test_card_capabilities(self):
        """Test that card capabilities are loaded correctly."""
        from src.core.a2a_cards import load_agent_card

        card = load_agent_card("scheduler_agent")
        assert card.capabilities is not None
        assert hasattr(card.capabilities, 'streaming')
        # Note: a2a-sdk uses snake_case (push_notifications)
        assert hasattr(card.capabilities, 'push_notifications')

    def test_card_skills_structure(self):
        """Test that card skills have correct structure."""
        from src.core.a2a_cards import load_agent_card

        card = load_agent_card("scheduler_agent")
        assert card.skills is not None

        for skill in card.skills:
            assert skill.id is not None
            assert skill.name is not None
            # Description is optional but should be present
            assert skill.description is not None

    def test_guide_card_skills(self):
        """Test guide card has expected skills."""
        from src.core.a2a_cards import load_agent_card

        card = load_agent_card("guide_agent")
        assert card.skills is not None
        skill_ids = [s.id for s in card.skills]
        assert "offer_tour" in skill_ids

    def test_tourist_card_skills(self):
        """Test tourist card has expected skills."""
        from src.core.a2a_cards import load_agent_card

        card = load_agent_card("tourist_agent")
        assert card.skills is not None
        skill_ids = [s.id for s in card.skills]
        assert "request_tour" in skill_ids

    def test_ui_card_skills(self):
        """Test UI card has expected skills."""
        from src.core.a2a_cards import load_agent_card

        card = load_agent_card("ui_agent")
        assert card.skills is not None
        skill_ids = [s.id for s in card.skills]
        assert "dashboard_summary" in skill_ids
        assert "recent_events" in skill_ids


class TestA2ACardIntegration:
    """Integration tests for A2A cards with agents."""

    @pytest.mark.skipif(
        not bool(pytest.importorskip("google.adk", reason="google-adk not installed")),
        reason="google-adk not installed"
    )
    def test_scheduler_uses_loaded_card(self):
        """Test that scheduler agent uses the loaded card."""
        from agents.scheduler_agent import create_scheduler_a2a_components

        agent_card, request_handler = create_scheduler_a2a_components(
            host="localhost", port=10000
        )

        # Verify the card was loaded from JSON
        assert agent_card.name == "Tourist Scheduling Coordinator"
        assert agent_card.version == "2.0.0"
        assert agent_card.url == "http://localhost:10000/"

    @pytest.mark.skipif(
        not bool(pytest.importorskip("google.adk", reason="google-adk not installed")),
        reason="google-adk not installed"
    )
    def test_ui_uses_loaded_card(self):
        """Test that UI agent uses the loaded card."""
        from agents.ui_agent import create_ui_a2a_components

        agent_card, request_handler = create_ui_a2a_components(
            host="0.0.0.0", port=10021
        )

        # Verify the card was loaded from JSON
        assert "Dashboard" in agent_card.name or "Monitor" in agent_card.name
        assert agent_card.version == "2.0.0"
