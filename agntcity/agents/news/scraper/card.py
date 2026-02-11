# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""
Agent Card for the Moltbook News Scraper Agent.

Defines the agent's identity, capabilities, and skills for A2A discovery.
"""

from a2a.types import (
    AgentCapabilities, 
    AgentCard,
    AgentSkill
)

AGENT_SKILL = AgentSkill(
    id="scrape_moltbook_community",
    name="Scrape Moltbook Community",
    description="Scrapes top posts from a Moltbook community (past 24 hours), analyzes sentiment and themes, and generates a summary report.",
    tags=["moltbook", "scraping", "news", "summarization", "ai-agents"],
    examples=[
        "Scrape and summarize the top 10 posts from: https://www.moltbook.com/m/technology",
    ]
)   

AGENT_CARD = AgentCard(
    name="News Scraper Agent",
    id='moltbook-news-scraper',
    description='An AI agent that scrapes Moltbook communities and generates summarized news reports. Analyzes top posts from the past 24 hours, identifies themes and sentiment, and produces a 1-2 paragraph summary.',
    url='',
    version='1.0.0',
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[AGENT_SKILL],
    supportsAuthenticatedExtendedCard=False,
)