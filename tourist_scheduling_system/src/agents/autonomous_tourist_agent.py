#!/usr/bin/env python3
"""
Autonomous Tourist Agent - A2A Client with OpenAI LLM

An intelligent tourist agent that uses OpenAI to make autonomous decisions
about travel preferences, budgets, and booking decisions. It continuously
operates and adapts to available offers.
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict

import click
import httpx
try:
    from openai import AsyncAzureOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AsyncAzureOpenAI = None
from a2a.client import ClientFactory, ClientConfig
from a2a.client.client_factory import minimal_agent_card
from a2a.client.helpers import create_text_message_object
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv():
        return None

from core.messages import TouristRequest, Window

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AutonomousTouristAgent:
    """Intelligent tourist agent with LLM decision-making capabilities"""

    def __init__(self, tourist_id: str, scheduler_url: str):
        self.tourist_id = tourist_id
        self.scheduler_url = scheduler_url
        # Use existing Azure OpenAI environment variables
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.llm_available = bool(AsyncAzureOpenAI and api_key and api_version and endpoint and self.deployment_name)
        if self.llm_available and AsyncAzureOpenAI:
            try:
                self.openai_client = AsyncAzureOpenAI(
                    api_key=api_key,
                    api_version=api_version,
                    azure_endpoint=endpoint,
                )
            except Exception as e:
                logger.warning("[Tourist %s] Failed to init OpenAI client: %s; fallback to heuristic", self.tourist_id, e)
                self.openai_client = None
                self.llm_available = False
        else:
            self.openai_client = None
            logger.warning("[Tourist %s] Azure OpenAI env vars missing; heuristic decisions only", self.tourist_id)
        self.persona = self._generate_persona()
        self.trip_context = self._generate_trip_context()
        self.booking_history = []
        self.received_offers = []

    def _generate_persona(self) -> Dict:
        """Generate a unique tourist persona"""
        personas = [
            {
                "type": "Cultural Explorer",
                "interests": ["culture", "history", "art", "museums"],
                "budget_style": "moderate",
                "base_budget": 200,
                "personality": "curious and educational-focused"
            },
            {
                "type": "Food Enthusiast",
                "interests": ["food", "culture", "local cuisine", "markets"],
                "budget_style": "generous",
                "base_budget": 300,
                "personality": "adventurous and social"
            },
            {
                "type": "Adventure Seeker",
                "interests": ["outdoors", "adventure", "nature", "sports"],
                "budget_style": "willing to pay for quality",
                "base_budget": 400,
                "personality": "active and thrill-seeking"
            },
            {
                "type": "Budget Traveler",
                "interests": ["culture", "history", "free activities"],
                "budget_style": "cost-conscious",
                "base_budget": 100,
                "personality": "practical and value-focused"
            },
            {
                "type": "Luxury Tourist",
                "interests": ["culture", "fine dining", "exclusive experiences"],
                "budget_style": "premium",
                "base_budget": 500,
                "personality": "sophisticated and quality-focused"
            }
        ]
        return random.choice(personas)

    def _generate_trip_context(self) -> Dict:
        """Generate trip context and constraints"""
        trip_purposes = ["vacation", "business trip", "family visit", "solo adventure", "romantic getaway"]
        durations = ["short visit", "day trip", "weekend", "week-long stay"]

        return {
            "purpose": random.choice(trip_purposes),
            "duration": random.choice(durations),
            "group_size": random.randint(1, 4),
            "flexibility": random.choice(["very flexible", "somewhat flexible", "strict schedule"])
        }

    async def make_budget_decision(self) -> float:
        """Use LLM to decide on budget based on persona and context"""
        prompt = f"""
        You are {self.tourist_id}, a {self.persona['type']} visiting a destination.

        Your characteristics:
        - Interests: {', '.join(self.persona['interests'])}
        - Budget style: {self.persona['budget_style']}
        - Personality: {self.persona['personality']}
        - Base budget: ${self.persona['base_budget']}

        Trip context:
        - Purpose: {self.trip_context['purpose']}
        - Duration: {self.trip_context['duration']}
        - Group size: {self.trip_context['group_size']} people
        - Schedule flexibility: {self.trip_context['flexibility']}

        Previous bookings: {len(self.booking_history)}
        Available offers: {len(self.received_offers)}

        Based on your persona and trip context, what's your maximum budget for a tour guide?
        Consider your financial comfort, the value you place on experiences, and your current trip situation.

        Respond with just a number (budget in dollars), no currency symbol or explanation.
        """

        if self.llm_available and self.openai_client is not None:
            try:
                client_chat = getattr(self.openai_client, "chat", None)
                if client_chat is None:
                    raise AttributeError("OpenAI client missing 'chat'")
                response = await client_chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50,
                    temperature=0.8
                )
                budget_text = response.choices[0].message.content.strip()
                import re
                budget_match = re.search(r'\d+(?:\.\d+)?', budget_text)
                if budget_match:
                    new_budget = float(budget_match.group())
                    min_budget = self.persona['base_budget'] * 0.5
                    max_budget = self.persona['base_budget'] * 3.0
                    new_budget = max(min_budget, min(max_budget, new_budget))
                    logger.info(f"[Tourist {self.tourist_id}] LLM budget decision: ${new_budget} (base: ${self.persona['base_budget']})")
                    return new_budget
            except Exception as e:
                logger.warning(f"[Tourist {self.tourist_id}] LLM budget failed, heuristic fallback: {e}")

        return self.persona['base_budget']

    async def decide_availability(self) -> Window:
        """Use LLM to decide on availability preferences"""
        now = datetime.now()

        prompt = f"""
        You are {self.tourist_id}, a {self.persona['type']} on a {self.trip_context['purpose']}.

        Your characteristics:
        - Personality: {self.persona['personality']}
        - Schedule flexibility: {self.trip_context['flexibility']}
        - Trip duration: {self.trip_context['duration']}
        - Group size: {self.trip_context['group_size']}

        It's currently {now.strftime('%A, %B %d, %Y at %I:%M %p')}.

        When would you prefer to take a guided tour? Consider:
        - Your energy levels and preferences
        - Optimal touring times for your interests
        - Your schedule flexibility
        - Group coordination needs

        Choose a time window for tomorrow that fits your travel style.
        Respond with start and end times in 24-hour format, like: "09:00-17:00"
        """

        if self.llm_available and self.openai_client is not None:
            try:
                client_chat = getattr(self.openai_client, "chat", None)
                if client_chat is None:
                    raise AttributeError("OpenAI client missing 'chat'")
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
                        end_time += timedelta(hours=4)
                    logger.info(f"[Tourist {self.tourist_id}] LLM availability decision: {start_time} to {end_time}")
                    return Window(start=start_time, end=end_time)
            except Exception as e:
                logger.warning(f"[Tourist {self.tourist_id}] LLM availability failed, heuristic fallback: {e}")

        # Default availability: tomorrow 9 AM to 5 PM
        tomorrow = now + timedelta(days=1)
        return Window(
            start=tomorrow.replace(hour=9, minute=0, second=0, microsecond=0),
            end=tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)
        )

    async def create_tourist_request(self) -> TouristRequest:
        """Create an intelligent tourist request based on LLM decisions"""
        # Get LLM decisions
        availability_window = await self.decide_availability()
        budget = await self.make_budget_decision()

        # Create the request
        request = TouristRequest(
            tourist_id=self.tourist_id,
            availability=[availability_window],
            preferences=self.persona['interests'][:2],  # Top 2 interests
            budget=budget
        )

        return request

    async def send_request_to_scheduler(self, request: TouristRequest):
        """Send the tourist request to the scheduler"""
        logger.info(f"[Tourist {self.tourist_id}] Sending request: {request}")

        async with httpx.AsyncClient():
            try:
                # Create A2A client
                client = ClientFactory(ClientConfig()).create(minimal_agent_card(self.scheduler_url))

                # Send message
                message = create_text_message_object(content=request.to_json())

                async for response in client.send_message(message):
                    logger.info(f"[Tourist {self.tourist_id}] Received response: {response}")

                    # Process schedule proposal
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
                                                if data.get("type") == "ScheduleProposal":
                                                    await self.evaluate_proposal(data)
                                            except json.JSONDecodeError:
                                                pass

            except Exception as e:
                logger.error(f"[Tourist {self.tourist_id}] Failed to send request: {e}")

    async def evaluate_proposal(self, proposal_data: Dict):
        """Use LLM to evaluate received schedule proposal"""
        prompt = f"""
        You are {self.tourist_id}, a {self.persona['type']} who just received a tour proposal.

        Your characteristics:
        - Budget: ${self.persona['base_budget']} (flexible based on value)
        - Interests: {', '.join(self.persona['interests'])}
        - Personality: {self.persona['personality']}

        Proposal received:
        {json.dumps(proposal_data, indent=2)}

        Based on your persona, would you accept this proposal? Consider:
        - Does it match your interests?
        - Is the price reasonable for the value?
        - Does the timing work for you?
        - Does it fit your travel style?

        Respond with just "ACCEPT" or "DECLINE" followed by a brief reason.
        """

        if self.llm_available and self.openai_client is not None:
            try:
                client_chat = getattr(self.openai_client, "chat", None)
                if client_chat is None:
                    raise AttributeError("OpenAI client missing 'chat'")
                response = await client_chat.completions.create(
                    model=self.deployment_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.7
                )
                decision = response.choices[0].message.content.strip()
                logger.info(f"[Tourist {self.tourist_id}] LLM evaluation: {decision}")
                if "ACCEPT" in decision.upper():
                    self.booking_history.append(proposal_data)
                    logger.info(f"[Tourist {self.tourist_id}] \u2705 Accepted proposal!")
                else:
                    logger.info(f"[Tourist {self.tourist_id}] \u274c Declined proposal")
                return
            except Exception as e:
                logger.warning(f"[Tourist {self.tourist_id}] LLM evaluation failed: {e}")
        # Heuristic evaluation fallback
        guide_rate = proposal_data.get("assignments", [{}])[0].get("hourly_rate", 0)
        budget_ok = guide_rate <= (self.persona['base_budget'] * 1.5)
        interests = set(self.persona['interests'])
        categories = set(proposal_data.get("assignments", [{}])[0].get("categories", []))
        interest_match = bool(interests & categories)
        if budget_ok and interest_match:
            self.booking_history.append(proposal_data)
            logger.info(f"[Tourist {self.tourist_id}] Heuristic ACCEPT (rate={guide_rate})")
        else:
            logger.info(f"[Tourist {self.tourist_id}] Heuristic DECLINE (rate={guide_rate}, match={interest_match})")

    async def autonomous_operation(self, duration_minutes: int = 60, min_interval: int = 60, max_interval: int = 180):
        """Run autonomous operations for specified duration"""
        logger.info(f"[Tourist {self.tourist_id}] Starting autonomous operation for {duration_minutes} minutes")
        logger.info(f"[Tourist {self.tourist_id}] Persona: {self.persona['type']} - {self.persona['personality']}")
        logger.info(f"[Tourist {self.tourist_id}] Trip: {self.trip_context['purpose']} ({self.trip_context['duration']})")

        end_time = datetime.now() + timedelta(minutes=duration_minutes)

        while datetime.now() < end_time:
            try:
                # Create and send request
                request = await self.create_tourist_request()
                await self.send_request_to_scheduler(request)

                # Wait before next request (interval configurable)
                if min_interval < 5:
                    min_interval = 5  # keep a small floor
                if max_interval < min_interval:
                    max_interval = min_interval
                wait_time = random.randint(min_interval, max_interval)
                logger.info(f"[Tourist {self.tourist_id}] Waiting {wait_time} seconds before next request...")
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"[Tourist {self.tourist_id}] Error in autonomous operation: {e}")
                await asyncio.sleep(60)  # Wait before retrying

        logger.info(f"[Tourist {self.tourist_id}] Autonomous operation completed")


async def _async_main(scheduler_url: str, tourist_id: str, duration: int, min_interval: int, max_interval: int):
    agent = AutonomousTouristAgent(tourist_id, scheduler_url)
    await agent.autonomous_operation(duration, min_interval=min_interval, max_interval=max_interval)


@click.command()
@click.option("--scheduler-url", default="http://localhost:10010", help="Scheduler A2A server URL")
@click.option("--tourist-id", default="tourist-ai-1", help="Tourist ID")
@click.option("--duration", default=60, type=int, help="Operation duration in minutes")
@click.option("--min-interval", default=60, type=int, help="Minimum seconds between requests")
@click.option("--max-interval", default=180, type=int, help="Maximum seconds between requests")
def main(scheduler_url: str, tourist_id: str, duration: int, min_interval: int, max_interval: int):
    """Run autonomous tourist agent (LLM optional)"""
    asyncio.run(_async_main(scheduler_url, tourist_id, duration, min_interval, max_interval))


if __name__ == "__main__":  # pragma: no cover
    main()