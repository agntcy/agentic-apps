#!/usr/bin/env python3
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

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AutonomousGuideAgent:
    """Intelligent guide agent with LLM decision-making capabilities"""

    def __init__(self, guide_id: str, scheduler_url: str):
        self.guide_id = guide_id
        self.scheduler_url = scheduler_url
        # Conditionally create Azure OpenAI client if env vars present
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
        self.market_conditions = {
            "demand": "medium",
            "competition": 0,
            "season": "peak"
        }
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
        """Use LLM to decide on dynamic pricing"""
        prompt = f"""
        You are an autonomous tour guide agent named {self.guide_id} with the personality: {self.personality['name']}.

        Your specialties are: {', '.join(self.personality['specialties'])}
        Your base hourly rate is: ${base_rate}

        Current market conditions:
        - Demand: {self.market_conditions['demand']}
        - Competition: {self.market_conditions['competition']} other guides
        - Season: {self.market_conditions['season']}

        Recent bookings: {len(self.booking_history)} in the last period

        Based on these factors, what hourly rate should you charge? Consider:
        - Market demand and competition
        - Your unique value proposition
        - Seasonal factors
        - Your booking success rate

        Respond with just a number (the hourly rate in dollars), no currency symbol or explanation.
        """

        if self.llm_available and self.openai_client is not None:
            try:
                client_chat = getattr(self.openai_client, "chat", None)
                if client_chat is None:
                    raise AttributeError("OpenAI client missing 'chat' attribute; falling back to heuristic")
                response = await client_chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.7
                )
                rate_text = response.choices[0].message.content.strip()
                import re
                rate_match = re.search(r'\d+(?:\.\d+)?', rate_text)
                if rate_match:
                    new_rate = float(rate_match.group())
                    new_rate = max(base_rate * 0.5, min(base_rate * 2.0, new_rate))
                    logger.info(f"[Guide {self.guide_id}] LLM pricing decision: ${new_rate}/hr (was ${base_rate}/hr)")
                    return new_rate
            except Exception as e:
                logger.warning(f"[Guide {self.guide_id}] LLM pricing failed, using heuristic: {e}")

        # Heuristic fallback: adjust by market demand
        multiplier = {"low": 0.8, "medium": 1.0, "high": 1.2}.get(self.market_conditions["demand"], 1.0)
        competition_factor = max(0.8, 1.2 - 0.05 * self.market_conditions["competition"])  # fewer competitors -> higher price
        season_factor = {"off-peak": 0.9, "shoulder": 1.0, "peak": 1.15}.get(self.market_conditions["season"], 1.0)
        heuristic_rate = round(base_rate * multiplier * competition_factor * season_factor, 2)
        logger.info(f"[Guide {self.guide_id}] Heuristic pricing decision: ${heuristic_rate}/hr (base ${base_rate}/hr)")
        return heuristic_rate

    async def decide_availability(self) -> Window:
        """Use LLM to decide on availability window"""
        now = datetime.now()

        prompt = f"""
        You are {self.guide_id}, a {self.personality['name']} tour guide.
        Your style is: {self.personality['style']}

        It's currently {now.strftime('%A, %B %d, %Y at %I:%M %p')}.

        Market conditions:
        - Demand: {self.market_conditions['demand']}
        - Season: {self.market_conditions['season']}
        - Your recent bookings: {len(self.booking_history)}

        When should you be available for tours today/tomorrow? Consider:
        - Popular tour times for your specialties
        - Your work-life balance preferences
        - Market demand patterns
        - Your energy levels and optimal performance times

        Respond with start and end times in 24-hour format, like: "10:00-16:00"
        """

        if self.llm_available and self.openai_client is not None:
            try:
                client_chat = getattr(self.openai_client, "chat", None)
                if client_chat is None:
                    raise AttributeError("OpenAI client missing 'chat' attribute; falling back to heuristic")
                response = await client_chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.8
                )
                time_text = response.choices[0].message.content.strip()
                import re
                time_match = re.search(r'(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})', time_text)
                if time_match:
                    start_hour, start_min, end_hour, end_min = map(int, time_match.groups())
                    tomorrow = now + timedelta(days=1)
                    start_time = tomorrow.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                    end_time = tomorrow.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
                    if end_time <= start_time:
                        end_time += timedelta(days=1)
                    logger.info(f"[Guide {self.guide_id}] LLM availability decision: {start_time} to {end_time}")
                    return Window(start=start_time, end=end_time)
            except Exception as e:
                logger.warning(f"[Guide {self.guide_id}] LLM availability failed, using heuristic: {e}")

        # Heuristic fallback: choose a window based on demand
        tomorrow = now + timedelta(days=1)
        if self.market_conditions["demand"] == "high":
            start_hour, end_hour = 9, 17
        elif self.market_conditions["demand"] == "low":
            start_hour, end_hour = 11, 15
        else:
            start_hour, end_hour = 10, 16
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
                    logger.info(f"[Guide {self.guide_id}] Received response: {response}")

                    # Process acknowledgment
                    if isinstance(response, tuple):
                        task, update = response
                        if task.history:
                            for msg in task.history:
                                if msg.role.value == "agent" and msg.parts:
                                    for part in msg.parts:
                                        text_value = getattr(part.root, "text", None)
                                        if text_value:
                                            try:
                                                data = json.loads(text_value)
                                                if data.get("type") == "Acknowledgment":
                                                    logger.info(f"[Guide {self.guide_id}] ✅ {data['message']}")
                                            except json.JSONDecodeError:
                                                pass

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