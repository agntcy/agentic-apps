# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
from uuid import uuid4

from a2a.types import (
    SendMessageRequest,
    MessageSendParams,
    Message,
    Part,
    TextPart,
    Role,
)
from agntcy_app_sdk.semantic.a2a.protocol import A2AProtocol

from agents.news.scraper.card import AGENT_CARD as scraper_agent_card
from agents.supervisors.news.graph.shared import get_factory
from config.config import (
    DEFAULT_MESSAGE_TRANSPORT, 
    TRANSPORT_SERVER_ENDPOINT,
)

logger = logging.getLogger("lungo.news.supervisor.tools")

# Global factory and transport instances
factory = get_factory()
transport = factory.create_transport(
    DEFAULT_MESSAGE_TRANSPORT,
    endpoint=TRANSPORT_SERVER_ENDPOINT,
    name="default/default/news_graph"
)


class A2AAgentError(Exception):
    """Custom exception for errors related to A2A agent communication or status."""
    pass


async def assign_url_to_worker(url: str, worker_id: str) -> str:
    """
    YOUR RESPONSIBILITY #2: Assign URL to scraper worker agent
    
    This function:
    1. Creates A2A client to communicate with scraper worker
    2. Sends URL to worker
    3. Waits for response (scraped + summarized content)
    4. Returns result
    
    Args:
        url (str): The URL to scrape
        worker_id (str): Identifier for the worker (for logging)
    
    Returns:
        str: Scraped and summarized content from the worker
    
    Raises:
        A2AAgentError: If there's an issue communicating with the worker
    """
    logger.info(f"Assigning URL {url} to worker {worker_id}")
    
    try:
        # Create client to communicate with scraper worker
        client = await factory.create_client(
            "A2A",
            agent_topic=A2AProtocol.create_agent_topic(scraper_agent_card),
            transport=transport,
        )

        # Create message with URL to scrape
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                message=Message(
                    messageId=str(uuid4()),
                    role=Role.user,
                    parts=[Part(TextPart(text=f"Scrape and summarize: {url}"))],
                ),
            )
        )

        # Send to worker and wait for response
        logger.debug(f"Sending request to scraper worker for URL: {url}")
        response = await client.send_message(request)
        logger.info(f"Response received from A2A agent: {response}")
        
        # Extract result
        if response.root.result and response.root.result.parts:
            part = response.root.result.parts[0].root
            if hasattr(part, "text"):
                result = part.text.strip()
                logger.info(f"Successfully received result from worker for {url}")
                return result
            else:
                raise A2AAgentError(f"Worker returned a result without text content for {url}")
        elif response.root.error:
            error_msg = response.root.error.message
            logger.error(f"A2A error from worker for {url}: {error_msg}")
            raise A2AAgentError(f"Error from worker for {url}: {error_msg}")
        else:
            logger.error(f"Unknown response type from worker for {url}")
            raise A2AAgentError(f"Unknown response type from worker for {url}")
            
    except Exception as e:
        logger.error(f"Failed to communicate with worker for {url}: {e}")
        raise A2AAgentError(f"Failed to communicate with worker for {url}. Details: {e}")
