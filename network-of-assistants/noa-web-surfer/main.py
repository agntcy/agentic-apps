# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import json
import argparse
import logging
from slim import SLIM
from llm import load_llm
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

from ioa_observe.sdk import Observe
from ioa_observe.sdk.decorators import agent
from ioa_observe.sdk.instrumentations.slim import SLIMInstrumentor
from ioa_observe.sdk.connectors.slim import process_slim_msg


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",  # Log message format
)
log = logging.getLogger(__name__)

@agent(name="web-surfer-agent", description="A web surfer agent that can browse the web and answer questions using a multimodal LLM.")
def get_web_surfer_agent(llm):
    # Define an agent
    web_surfer_agent = MultimodalWebSurfer(
        name="MultimodalWebSurfer",
        model_client=llm,
    )
    return web_surfer_agent

async def main(args):
    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        Observe.init(args.id, api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT"))
        SLIMInstrumentor().instrument()

    # Instantiate the slim class
    slim = SLIM(
        slim_endpoint=args.slim_endpoint,
        local_id=args.id,
        shared_space="chat",
        opentelemetry_endpoint=os.getenv("OTLP_GRPC_ENDPOINT"),
    )
    await slim.init()

    llm = load_llm(env_prefix="WEB_SURFER_LLM_")

    # Define an agent
    web_surfer_agent = get_web_surfer_agent(llm)
    agent_team = RoundRobinGroupChat([web_surfer_agent], max_turns=args.max_turns)

    lastquery = ""

    log.info("Web surfer agent is ready.")

    @process_slim_msg("noa-web-surfer")
    async def on_message_received(message: bytes):
        nonlocal lastquery, web_surfer_agent, agent_team
        # Decode the message from bytes to string
        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        if json_message["type"] == "ChatMessage":
            lastquery = json_message["message"]

        elif json_message["type"] == "RequestToSpeak" and json_message["target"] == args.id:
            try:
                # Run the team and stream messages to the console
                log.info(f"Processing request: {lastquery}")
                stream = agent_team.run_stream(task=lastquery)

                messages = []
                async for message in stream:
                    messages.append(message)

                response = message.messages[-1].content

                if isinstance(response, list):
                    response = response[0]

                # Close the browser controlled by the agent

                message = {
                    "type": "ChatMessage",
                    "author": args.id,
                    "message": str(response),
                }

                message_json = json.dumps(message)
                log.info(f"Responding with: {str(response)}")
                await slim.publish(msg=message_json.encode("utf-8"))

            finally:
                await web_surfer_agent.close()
                web_surfer_agent = MultimodalWebSurfer(
                    name="MultimodalWebSurfer",
                    model_client=llm,
                )
                agent_team = RoundRobinGroupChat([web_surfer_agent], max_turns=5)

    # Connect to the slim server and start receiving messages
    await slim.receive(callback=on_message_received)
    await slim.receive_task


def run():
    import asyncio

    parser = argparse.ArgumentParser(description="Start slim command interface.")
    parser.add_argument(
        "--slim-endpoint",
        type=str,
        default=os.getenv("SLIM_ENDPOINT", "http://localhost:12345"),
        help="SLIM endpoint URL (e.g., http://localhost:12345)",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=os.getenv("WEB_SURFER_ID", "noa-web-surfer-assistant"),
        help="Web Surfer assistant ID (e.g., noa-web-surfer-assistant)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=os.getenv("WEB_SURFER_MAX_TURNS", 10),
        help="Web Surfer assistant max number of iterations",
    )
    args = parser.parse_args()

    # Run the main function
    asyncio.run(main(args))


if __name__ == "__main__":
    run()
