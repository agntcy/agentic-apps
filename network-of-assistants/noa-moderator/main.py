# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
import argparse
from slim import SLIM
from agent import ModeratorAgent
from langchain_core.exceptions import OutputParserException

from ioa_observe.sdk import Observe
from ioa_observe.sdk.tracing import session_start
from ioa_observe.sdk.instrumentations.slim import SLIMInstrumentor
from ioa_observe.sdk.connectors.slim import SLIMConnector, process_slim_msg


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
)
log = logging.getLogger(__name__)


async def main(args):
    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        Observe.init(args.id, api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT"))

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
        slim_connector.register("moderator_agent")
        SLIMInstrumentor().instrument()

    agents_dir = args.agents_dir

    chat_history = []
    moderator_agent = ModeratorAgent(agents_dir)
    log.info("Moderator agent is ready.")

    @process_slim_msg("noa-moderator")
    async def on_message_received(message: bytes):
        nonlocal chat_history, moderator_agent
        # Decode the message from bytes to string

        if chat_history == []:
            session_start()
            moderator_agent.init_run()

        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        log.info(f"Received message: {json_message}")

        if json_message["type"] == "ChatMessage":
            try:
                answers_list = moderator_agent.invoke(
                    input={
                        "chat_history": chat_history,
                        "query_message": json_message,
                    }
                )
                chat_history.append(json_message)

                if "messages" not in answers_list:
                    answers_list = {"messages": [answers_list]}

                for answer in answers_list["messages"]:
                    log.info(f"Sending answer: {answer}")
                    chat_history.append(answer)
                    answer_str = json.dumps(answer)
                    if answer["type"] == "RequestToSpeak" and answer["target"] == "noa-user-proxy":
                        chat_history = []
                    await slim.publish(msg=answer_str.encode("utf-8"))

            except OutputParserException as e:
                log.error(f"Wrong format from {args.id}: {e}")

                answer = {
                    "type": "ChatMessage",
                    "author": args.id,
                    "message": f"Moderator failed: {e}",
                }
                chat_history.append(answer)
                answer_str = json.dumps(answer)
                await slim.publish(msg=answer_str.encode("utf-8"))
                answer = {
                    "type": "RequestToSpeak",
                    "author": args.id,
                    "target": "noa-user-proxy",
                }
                chat_history.append(answer)
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
        "--agents-dir",
        type=str,
        default=os.getenv("AGENTS_DIR", "/app/dir/datamodels"),
        help="Directory of available agent specs",
    )
    parser.add_argument(
        "--id",
        type=str,
        default=os.getenv("MODERATOR_ID", "noa-moderator"),
        help="Moderator ID (e.g., noa-moderator)",
    )
    args = parser.parse_args()

    # Run the main function
    asyncio.run(main(args))


if __name__ == "__main__":
    run()
