#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Autonomous Guide Agent - A2A Client with OpenAI LLM

An intelligent tour guide agent that uses OpenAI to make autonomous decisions
about availability, pricing, and specialties. It continuously operates and
responds to market conditions.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List

import click
import httpx
try:
    from openai import AsyncAzureOpenAI  # type: ignore
except Exception:  # pragma: no cover - openai optional for demo
    AsyncAzureOpenAI = None  # fallback sentinel
from a2a.client import ClientFactory, ClientConfig
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv():  # fallback no-op
        return None

from core.messages import GuideOffer, Window
from pydantic import BaseModel
from a2a.types import Task, Message

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AutonomousGuideAgent:
    """Intelligent guide agent with LLM decision-making capabilities"""

    def __init__(self, guide_id: str, scheduler_url: str):
        self.guide_id = guide_id
        self.scheduler_url = scheduler_url
        # Conditionally create Azure OpenAI client if env vars present (simple env based config)
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.llm_available = bool(AsyncAzureOpenAI and api_key and api_version and endpoint and self.deployment_name)
        if self.llm_available:
            try:
                self.openai_client = AsyncAzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint,
                )
            except Exception as e:  # pragma: no cover
                logger.warning("[Guide %s] Failed to initialize OpenAI client: %s; using heuristic decisions", self.guide_id, e)
                self.openai_client = None
                self.llm_available = False
        else:
            self.openai_client = None
            logger.warning("[Guide %s] Azure OpenAI env vars missing; falling back to heuristic decisions", self.guide_id)
        self.personality = self._generate_personality()
        self.market_conditions = {"demand": "medium", "competition": 0, "season": "peak"}
        self.booking_history = []

    def _generate_personality(self) -> Dict:
        """Generate a unique personality for this guide"""
        personalities = [
            {
                "name": "Cultural Enthusiast",
                "specialties": ["culture", "history", "art"],
                "style": "passionate and knowledgeable",
                "base_rate": 75.0
            },
            {
                "name": "Foodie Expert",
                "specialties": ["food", "culture", "local cuisine"],
                "style": "friendly and engaging",
                "base_rate": 85.0
            },
            {
                "name": "Adventure Guide",
                "specialties": ["outdoors", "adventure", "nature"],
                "style": "energetic and safety-focused",
                "base_rate": 95.0
            },
            {
                "name": "History Scholar",
                "specialties": ["history", "archaeology", "museums"],
                "style": "scholarly and detailed",
                "base_rate": 80.0
            }
        ]
        return random.choice(personalities)

    async def make_pricing_decision(self, base_rate: float) -> float:
        """Use LLM (if available) or heuristic to decide on dynamic pricing."""
        prompt = (
            f"You are an autonomous tour guide agent named {self.guide_id} with the personality: {self.personality['name']}.\n"
            f"Specialties: {', '.join(self.personality['specialties'])}\n"
            f"Base hourly rate: ${base_rate}\n"
            f"Demand: {self.market_conditions['demand']} | Competition: {self.market_conditions['competition']} | Season: {self.market_conditions['season']}\n"
            f"Recent bookings: {len(self.booking_history)}\n"
            "Respond with just a number (hourly rate)."
        )
        if self.openai_client:
            # Structured output via pydantic model (OpenAI SDK parse API)
            class PricingDecision(BaseModel):
                hourly_rate: float
            try:
                response = await self.openai_client.chat.completions.parse(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.7,
                    response_format=PricingDecision,
                )
                decision = response.choices[0].message.parsed  # type: ignore[attr-defined]
                new_rate = float(decision.hourly_rate)
                new_rate = max(base_rate * 0.5, min(base_rate * 2.0, new_rate))
                logger.info(
                    f"[Guide {self.guide_id}] LLM pricing decision (structured): ${new_rate}/hr (was ${base_rate}/hr)"
                )
                return new_rate
            except Exception as e:  # pragma: no cover
                logger.warning(
                    f"[Guide {self.guide_id}] Structured pricing parse failed; regex fallback: {e}"
                )
                # Fallback to original unstructured approach
                try:
                    response = await self.openai_client.chat.completions.create(
                        model=self.deployment_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=50,
                        temperature=0.7,
                    )
                    rate_text = response.choices[0].message.content.strip()
                    import re
                    match = re.search(r"\d+(?:\.\d+)?", rate_text)
                    if match:
                        new_rate = float(match.group())
                        new_rate = max(base_rate * 0.5, min(base_rate * 2.0, new_rate))
                        logger.info(
                            f"[Guide {self.guide_id}] LLM pricing decision (fallback): ${new_rate}/hr (was ${base_rate}/hr)"
                        )
                        return new_rate
                except Exception as e2:  # pragma: no cover
                    logger.warning(
                        f"[Guide {self.guide_id}] LLM pricing fallback failed; heuristic: {e2}"
                    )
        # Heuristic fallback
        multiplier = {"low": 0.8, "medium": 1.0, "high": 1.2}.get(self.market_conditions["demand"], 1.0)
        competition_factor = max(0.8, 1.2 - 0.05 * self.market_conditions["competition"])
        season_factor = {"off-peak": 0.9, "shoulder": 1.0, "peak": 1.15}.get(self.market_conditions["season"], 1.0)
        rate = round(base_rate * multiplier * competition_factor * season_factor, 2)
        logger.info(f"[Guide {self.guide_id}] Heuristic pricing decision: ${rate}/hr (base ${base_rate}/hr)")
        return rate

    async def decide_availability(self) -> Window:
        """Use LLM (if available) or heuristics to choose next availability window."""
        now = datetime.now()
        prompt = (
            f"You are {self.guide_id}, a {self.personality['name']} ({self.personality['style']}).\n"
            f"Current time: {now.isoformat()}\nDemand: {self.market_conditions['demand']} | Season: {self.market_conditions['season']} | Recent bookings: {len(self.booking_history)}\n"
            "Return a time window in 24h format like 10:00-16:00 for tomorrow."  # concise instruction
        )
        if self.openai_client:
            try:
                response = await self.openai_client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.8,
                )
                time_text = response.choices[0].message.content.strip()
                import re
                m = re.search(r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", time_text)
                if m:
                    sh, sm, eh, em = map(int, m.groups())
                    tomorrow = now + timedelta(days=1)
                    start_time = tomorrow.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    end_time = tomorrow.replace(hour=eh, minute=em, second=0, microsecond=0)
                    if end_time <= start_time:
                        end_time = start_time + timedelta(hours=4)
                    logger.info(
                        f"[Guide {self.guide_id}] LLM availability decision: {start_time} to {end_time}"
                    )
                    return Window(start=start_time, end=end_time)
            except Exception as e:  # pragma: no cover
                logger.warning(f"[Guide {self.guide_id}] LLM availability failed; heuristic fallback: {e}")
        # Heuristic fallback window selection
        tomorrow = now + timedelta(days=1)
        start_hour, end_hour = (9, 17) if self.market_conditions["demand"] == "high" else (11, 15) if self.market_conditions["demand"] == "low" else (10, 16)
        start_time = tomorrow.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = tomorrow.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        logger.info(f"[Guide {self.guide_id}] Heuristic availability: {start_time} to {end_time}")
        return Window(start=start_time, end=end_time)

    async def create_guide_offer(self) -> GuideOffer:
        """Create an intelligent guide offer based on LLM decisions"""
        # Get LLM decisions
        availability_window = await self.decide_availability()
        hourly_rate = await self.make_pricing_decision(self.personality['base_rate'])

        # Create the offer
        offer = GuideOffer(
            guide_id=self.guide_id,
            categories=self.personality['specialties'],
            available_window=availability_window,
            hourly_rate=hourly_rate,
            max_group_size=random.randint(4, 8)  # Random group size preference
        )

        return offer

    async def send_offer_to_scheduler(self, offer: GuideOffer):
        """Send the guide offer to the scheduler"""
        logger.info(f"[Guide {self.guide_id}] Sending offer: {offer}")

        async with httpx.AsyncClient() as httpx_client:
            try:
                # Create A2A client
                # NOTE: prefer factory + create with minimal_card for consistency with other agents
                client = ClientFactory(ClientConfig()).create(minimal_agent_card(self.scheduler_url))

                # Send message
                message = create_text_message_object(content=offer.to_json())

                async for response in client.send_message(message):
                    # Normalize task extraction (streaming/non-streaming)
                    task_obj = None
                    if isinstance(response, Task):
                        task_obj = response
                    elif isinstance(response, tuple) and len(response) == 2:
                        task_obj, _update = response
                    elif isinstance(response, Message):
                        logger.warning("[Guide %s] Unexpected bare Message response", self.guide_id)
                        continue
                    else:
                        continue
                    history = getattr(task_obj, "history", []) or []
                    if not history:
                        continue
                    for msg in history:
                        if getattr(msg.role, "value", None) == "agent" and getattr(msg, "parts", None):
                            for part in msg.parts:
                                raw = getattr(getattr(part, "root", None), "text", None)
                                if not raw:
                                    continue
                                try:
                                    data = json.loads(raw)
                                except json.JSONDecodeError:
                                    continue
                                if data.get("type") == "Acknowledgment":
                                    logger.info(f"[Guide {self.guide_id}] ✅ {data['message']}")

            except Exception as e:
                logger.error(f"[Guide {self.guide_id}] Failed to send offer: {e}")

    async def update_market_conditions(self):
        """Simulate market condition updates"""
        demand_levels = ["low", "medium", "high"]
        seasons = ["off-peak", "shoulder", "peak"]

        self.market_conditions["demand"] = random.choice(demand_levels)
        self.market_conditions["competition"] = random.randint(0, 5)
        self.market_conditions["season"] = random.choice(seasons)

        logger.info(f"[Guide {self.guide_id}] Market update: {self.market_conditions}")

    async def autonomous_operation(self, duration_minutes: int = 60, min_interval: int = 30, max_interval: int = 120):
        """Run autonomous operations for specified duration"""
        logger.info(f"[Guide {self.guide_id}] Starting autonomous operation for {duration_minutes} minutes")
        logger.info(f"[Guide {self.guide_id}] Personality: {self.personality['name']} - {self.personality['style']}")

        end_time = datetime.now() + timedelta(minutes=duration_minutes)

        while datetime.now() < end_time:
            try:
                # Update market understanding
                await self.update_market_conditions()

                # Create and send offer
                offer = await self.create_guide_offer()
                await self.send_offer_to_scheduler(offer)

                # Wait before next offer (simulate realistic timing)
                # Interval bounds configurable via CLI; enforce sanity (>=1 and max>=min)
                if min_interval < 1:
                    min_interval = 1
                if max_interval < min_interval:
                    max_interval = min_interval
                wait_time = random.randint(min_interval, max_interval)
                logger.info(f"[Guide {self.guide_id}] Waiting {wait_time} seconds before next offer...")
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"[Guide {self.guide_id}] Error in autonomous operation: {e}")
                await asyncio.sleep(30)  # Wait before retrying

        logger.info(f"[Guide {self.guide_id}] Autonomous operation completed")


async def _async_main(scheduler_url: str, guide_id: str, duration: int, min_interval: int, max_interval: int):
    agent = AutonomousGuideAgent(guide_id, scheduler_url)
    await agent.autonomous_operation(duration, min_interval=min_interval, max_interval=max_interval)


@click.command()
@click.option("--scheduler-url", default="http://localhost:10010", help="Scheduler A2A server URL")
@click.option("--guide-id", default="guide-ai-1", help="Guide ID")
@click.option("--duration", default=60, type=int, help="Operation duration in minutes")
@click.option("--min-interval", default=30, type=int, help="Minimum seconds between offers")
@click.option("--max-interval", default=120, type=int, help="Maximum seconds between offers")
def main(scheduler_url: str, guide_id: str, duration: int, min_interval: int, max_interval: int):
    """Run autonomous guide agent (LLM optional)"""
    asyncio.run(_async_main(scheduler_url, guide_id, duration, min_interval, max_interval))


if __name__ == "__main__":  # pragma: no cover
    main()