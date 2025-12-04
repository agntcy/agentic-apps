#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
A2A Agent Card Loader

Utility module to load and use A2A agent cards from JSON files stored in the
a2a_cards directory. This enables agents to use standardized agent cards with
consistent metadata, skills definitions, and capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from a2a.types import AgentCard, AgentCapabilities, AgentSkill

logger = logging.getLogger(__name__)

# Path to the a2a_cards directory (relative to project root)
A2A_CARDS_DIR = Path(__file__).parent.parent.parent / "a2a_cards"


def load_agent_card_json(card_name: str) -> dict:
    """
    Load an agent card JSON file by name.

    Args:
        card_name: Name of the agent card file (without .json extension)
                   e.g., "scheduler_agent", "guide_agent"

    Returns:
        Dictionary containing the agent card data

    Raises:
        FileNotFoundError: If the card file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    card_path = A2A_CARDS_DIR / f"{card_name}.json"

    if not card_path.exists():
        raise FileNotFoundError(f"Agent card not found: {card_path}")

    with open(card_path, "r") as f:
        return json.load(f)


def load_agent_card(
    card_name: str,
    url_override: Optional[str] = None,
) -> AgentCard:
    """
    Load an A2A AgentCard from a JSON file.

    Args:
        card_name: Name of the agent card file (without .json extension)
        url_override: Optional URL to override the default in the card

    Returns:
        Configured AgentCard instance

    Raises:
        FileNotFoundError: If the card file doesn't exist
    """
    data = load_agent_card_json(card_name)

    # Override URL if provided
    if url_override:
        data["url"] = url_override

    # Convert skills to AgentSkill objects
    skills = []
    for skill_data in data.get("skills", []):
        skill = AgentSkill(
            id=skill_data.get("id", ""),
            name=skill_data.get("name", ""),
            description=skill_data.get("description"),
            tags=skill_data.get("tags"),
            examples=skill_data.get("examples"),
            inputModes=skill_data.get("inputModes"),
            outputModes=skill_data.get("outputModes"),
        )
        skills.append(skill)

    # Build capabilities
    caps_data = data.get("capabilities", {})
    capabilities = AgentCapabilities(
        streaming=caps_data.get("streaming", False),
        pushNotifications=caps_data.get("pushNotifications", False),
        stateTransitionHistory=caps_data.get("stateTransitionHistory", False),
    )

    # Create agent card
    agent_card = AgentCard(
        name=data.get("name", ""),
        description=data.get("description"),
        url=data.get("url", ""),
        version=data.get("version", "1.0.0"),
        protocolVersion=data.get("protocolVersion", "0.3.0"),
        capabilities=capabilities,
        skills=skills if skills else None,
        defaultInputModes=data.get("defaultInputModes"),
        defaultOutputModes=data.get("defaultOutputModes"),
        supportsAuthenticatedExtendedCard=data.get("supportsAuthenticatedExtendedCard", False),
    )

    logger.debug(f"Loaded agent card: {agent_card.name} from {card_name}.json")
    return agent_card


def get_scheduler_card(host: str = "localhost", port: int = 10000) -> AgentCard:
    """
    Get the scheduler agent card with the specified URL.

    Args:
        host: Host for the A2A server
        port: Port for the A2A server

    Returns:
        Configured AgentCard for the scheduler
    """
    url = f"http://{host}:{port}/"
    return load_agent_card("scheduler_agent", url_override=url)


def get_guide_card(guide_id: str = "guide", host: str = "localhost", port: int = 10001) -> AgentCard:
    """
    Get a guide agent card with the specified URL.

    Args:
        guide_id: Unique identifier for the guide
        host: Host for the A2A server
        port: Port for the A2A server

    Returns:
        Configured AgentCard for the guide
    """
    url = f"http://{host}:{port}/"
    card = load_agent_card("guide_agent", url_override=url)
    # Update name to include guide ID
    card.name = f"Tour Guide {guide_id}"
    return card


def get_tourist_card(tourist_id: str = "tourist", host: str = "localhost", port: int = 10002) -> AgentCard:
    """
    Get a tourist agent card with the specified URL.

    Args:
        tourist_id: Unique identifier for the tourist
        host: Host for the A2A server
        port: Port for the A2A server

    Returns:
        Configured AgentCard for the tourist
    """
    url = f"http://{host}:{port}/"
    card = load_agent_card("tourist_agent", url_override=url)
    # Update name to include tourist ID
    card.name = f"Tourist {tourist_id}"
    return card


def get_ui_card(host: str = "localhost", port: int = 10021) -> AgentCard:
    """
    Get the UI/dashboard agent card with the specified URL.

    Args:
        host: Host for the UI server
        port: Port for the UI server

    Returns:
        Configured AgentCard for the UI agent
    """
    url = f"http://{host}:{port}/"
    return load_agent_card("ui_agent", url_override=url)


def list_available_cards() -> list[str]:
    """
    List all available agent card names.

    Returns:
        List of card names (without .json extension)
    """
    if not A2A_CARDS_DIR.exists():
        return []

    return [
        f.stem for f in A2A_CARDS_DIR.glob("*.json")
        if f.is_file()
    ]
