#!/usr/bin/env python3
"""
Multi-Agent Autonomous Demo Runner

Runs multiple autonomous guide and tourist agents simultaneously,
each with their own OpenAI-powered decision making.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Add src directory to path so we can import our agents
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from a2a_summit_demo.agents.autonomous_guide_agent import AutonomousGuideAgent
from a2a_summit_demo.agents.autonomous_tourist_agent import AutonomousTouristAgent

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def run_autonomous_demo():
    """Run a demonstration with multiple autonomous agents"""

    scheduler_url = "http://localhost:10010"
    demo_duration = 10  # Run for 10 minutes    logger.info("🚀 Starting Autonomous Multi-Agent Demo")
    logger.info(f"📍 Scheduler URL: {scheduler_url}")
    logger.info(f"⏱️  Duration: {demo_duration} minutes")
    logger.info("🤖 Using Azure OpenAI for agent decision-making")
    print()

    # Create 3 autonomous guide agents
    guide_agents = [
        AutonomousGuideAgent("guide-ai-florence", scheduler_url),
        AutonomousGuideAgent("guide-ai-marco", scheduler_url),
        AutonomousGuideAgent("guide-ai-sofia", scheduler_url)
    ]

    # Create 2 autonomous tourist agents
    tourist_agents = [
        AutonomousTouristAgent("tourist-ai-alice", scheduler_url),
        AutonomousTouristAgent("tourist-ai-bob", scheduler_url)
    ]

    # Start all agents concurrently
    tasks = []

    # Add guide agent tasks
    for guide in guide_agents:
        task = asyncio.create_task(guide.autonomous_operation(demo_duration))
        tasks.append(task)
        logger.info(f"✅ Started autonomous guide: {guide.guide_id}")

    # Add tourist agent tasks
    for tourist in tourist_agents:
        task = asyncio.create_task(tourist.autonomous_operation(demo_duration))
        tasks.append(task)
        logger.info(f"✅ Started autonomous tourist: {tourist.tourist_id}")

    print()
    logger.info("🔄 All agents running autonomously...")
    logger.info("📊 Check the UI dashboard at http://localhost:10011 for real-time updates!")
    print()

    # Wait for all agents to complete
    try:
        await asyncio.gather(*tasks)

        logger.info("🎉 Autonomous demo completed successfully!")
        logger.info("📈 Check the dashboard for final statistics")

    except KeyboardInterrupt:
        logger.info("🛑 Demo interrupted by user")
        # Cancel all tasks
        for task in tasks:
            task.cancel()

        # Wait for cancellation to complete
        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_autonomous_demo())