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
from openai import AsyncAzureOpenAI
from a2a.client import ClientFactory
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object
from dotenv import load_dotenv

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
        # Use existing Azure OpenAI environment variables
        self.openai_client = AsyncAzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
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

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.7
            )

            rate_text = response.choices[0].message.content.strip()
            # Extract number from response
            import re
            rate_match = re.search(r'\d+(?:\.\d+)?', rate_text)
            if rate_match:
                new_rate = float(rate_match.group())
                # Keep within reasonable bounds (50% to 200% of base rate)
                new_rate = max(base_rate * 0.5, min(base_rate * 2.0, new_rate))
                logger.info(f"[Guide {self.guide_id}] LLM pricing decision: ${new_rate}/hr (was ${base_rate}/hr)")
                return new_rate

        except Exception as e:
            logger.warning(f"[Guide {self.guide_id}] LLM pricing failed, using base rate: {e}")

        return base_rate

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

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.8
            )

            time_text = response.choices[0].message.content.strip()
            # Parse time range like "10:00-16:00"
            import re
            time_match = re.search(r'(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})', time_text)
            if time_match:
                start_hour, start_min, end_hour, end_min = map(int, time_match.groups())

                # Use tomorrow's date for availability
                tomorrow = now + timedelta(days=1)
                start_time = tomorrow.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                end_time = tomorrow.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

                if end_time <= start_time:
                    end_time += timedelta(days=1)  # Handle overnight availability

                logger.info(f"[Guide {self.guide_id}] LLM availability decision: {start_time} to {end_time}")
                return Window(start=start_time, end=end_time)

        except Exception as e:
            logger.warning(f"[Guide {self.guide_id}] LLM availability failed, using default: {e}")

        # Default availability: tomorrow 10 AM to 4 PM
        tomorrow = now + timedelta(days=1)
        return Window(
            start=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
            end=tomorrow.replace(hour=16, minute=0, second=0, microsecond=0)
        )

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
                client = await ClientFactory.connect(
                    agent=minimal_agent_card(self.scheduler_url),
                    client_config=None,
                )

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
                                        if hasattr(part.root, "text"):
                                            try:
                                                data = json.loads(part.root.text)
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

    async def autonomous_operation(self, duration_minutes: int = 60):
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
                wait_time = random.randint(30, 120)  # 30 seconds to 2 minutes
                logger.info(f"[Guide {self.guide_id}] Waiting {wait_time} seconds before next offer...")
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"[Guide {self.guide_id}] Error in autonomous operation: {e}")
                await asyncio.sleep(30)  # Wait before retrying

        logger.info(f"[Guide {self.guide_id}] Autonomous operation completed")


@click.command()
@click.option("--scheduler-url", default="http://localhost:10010", help="Scheduler A2A server URL")
@click.option("--guide-id", default="guide-ai-1", help="Guide ID")
@click.option("--duration", default=60, help="Operation duration in minutes")
async def main(scheduler_url: str, guide_id: str, duration: int):
    """Run autonomous guide agent with Azure OpenAI decision-making"""

    # Create and run autonomous agent (Azure OpenAI env vars already set)
    agent = AutonomousGuideAgent(guide_id, scheduler_url)
    await agent.autonomous_operation(duration)


if __name__ == "__main__":
    asyncio.run(main())