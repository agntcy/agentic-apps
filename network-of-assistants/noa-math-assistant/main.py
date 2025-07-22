# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
import argparse
from slim import SLIM
from agent import MathAssistant

from ioa_observe.sdk import Observe
from ioa_observe.sdk.instrumentations.slim import SLIMInstrumentor
from ioa_observe.sdk.connectors.slim import SLIMConnector, process_slim_msg


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",  # Log message format
)
log = logging.getLogger(__name__)


async def main(args):
    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        Observe.init(args.id, api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT"))
        SLIMInstrumentor().instrument()

    # Instantiate the SLIM class
    slim = SLIM(
        slim_endpoint=args.slim_endpoint,
        local_id=args.id,
        shared_space="chat",
        opentelemetry_endpoint=os.getenv("OTLP_GRPC_ENDPOINT"),
    )
    await slim.init()

    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        # initialize the SLIM connector
        slim_connector = SLIMConnector(
            remote_org="organization",
            remote_namespace="namespace",
            shared_space="chat",
        )
        # register the agent with the SLIM connector
        slim_connector.register("math_assistant")

    # Define an agent
    math_assistant = MathAssistant()

    lastquery = ""

    log.info("Math assistant is ready.")

    @process_slim_msg("noa-math-assistant")
    async def on_message_received(message: bytes):
        nonlocal lastquery, math_assistant
        # Decode the message from bytes to string
        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        if json_message["type"] == "ChatMessage":
            lastquery = json_message["message"]

        elif json_message["type"] == "RequestToSpeak" and json_message["target"] == args.id:
            # Run the team and stream messages to the console
            log.info(f"Processing request: {lastquery}")

            try:
                response = math_assistant.ask_math_question(json_message["message"])

                message = {
                    "type": "ChatMessage",
                    "author": args.id,
                    "message": str(response),
                }

                message_json = json.dumps(message)
                log.info(f"Responding with: {str(response)}")
                await slim.publish(msg=message_json.encode("utf-8"))

            except Exception as e:
                log.error(f"Error from {args.id}: {str(e)}")

                answer = {
                    "type": "ChatMessage",
                    "author": args.id,
                    "message": f"There was an error with the {args.id}: {str(e)}",
                }
                answer_str = json.dumps(answer)
                await slim.publish(msg=answer_str.encode("utf-8"))

    # Connect to the SLIM server and start receiving messages
    await slim.receive(callback=on_message_received)
    await slim.receive_task


def run():
    import asyncio

    parser = argparse.ArgumentParser(description="Start SLIM command interface.")
    parser.add_argument(
        "--slim-endpoint",
        type=str,
        default=os.getenv("SLIM_ENDPOINT", "http://localhost:12345"),
        help="SLIM endpoint URL (e.g., http://localhost:12345)",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=os.getenv("MATH_ASSISTANT_ID", "noa-math-assistant"),
        help="Math assistant ID (e.g., noa-math-assistant)",
    )
    args = parser.parse_args()

    # Run the main function
    asyncio.run(main(args))


if __name__ == "__main__":
    run()
