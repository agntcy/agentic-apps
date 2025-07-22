# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import json
import asyncio
import logging
import uvicorn
import argparse
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from ioa_observe.sdk.connectors.slim import SLIMConnector
from ioa_observe.sdk import Observe
from slim import SLIM
from ioa_observe.sdk.instrumentations.slim import SLIMInstrumentor

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
)
log = logging.getLogger(__name__)


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def convert_to_title_case(input_string):
    """Convert hyphen-separated words to title case."""
    words = input_string.split("-")
    capitalized_words = [word.capitalize() for word in words]
    return " ".join(capitalized_words)


request_to_speak_event = asyncio.Event()
app = FastAPI()

with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
if with_obs:
    Observe.init(
        "noa-user-proxy",
        api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT"),
    )

slim = None
last_slim_answer = None


class MessageModel(BaseModel):
    message: str


async def command_callback(response):
    """Handle incoming commands and print chat messages."""
    global last_slim_answer
    try:
        decoded_message = response.decode("utf-8")

        # Try parsing the JSON message first
        message_data = json.loads(decoded_message)
        print(f"Received message: {message_data}")
        # Check if this is a wrapped message with headers and payload
        if "payload" in message_data:
            # Extract and parse the payload which could be a JSON string
            payload = message_data["payload"]
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = {"message": payload}  # Treat as simple message if not JSON
            else:
                data = payload  # Use payload directly if not a string
        else:
            # If not wrapped, use the message directly
            data = message_data

        if data.get("type") == "ChatMessage":
            log.info(
                Color.BOLD
                + Color.DARKCYAN
                + f"{convert_to_title_case(data['author'])}:"
                + Color.END
                + f" {data['message']}"
            )
            if data.get("author") == "noa-moderator":
                last_slim_answer = data["message"]
        elif data.get("type") == "RequestToSpeak" and data.get("target") == "noa-user-proxy":
            request_to_speak_event.set()
    except Exception as e:
        print(f"Error in command_callback: {e}")


@app.post("/ask")
async def send_message(message: MessageModel):
    """Endpoint to handle incoming messages."""
    if not slim:
        raise HTTPException(status_code=500, detail="SLIM not initialized.")

    # Prepare message to send
    message_data = {
        "type": "ChatMessage",
        "author": "noa-user-proxy",
        "message": message.message.strip().lower(),
    }

    # Clear the event and send the message
    request_to_speak_event.clear()
    await slim.publish(msg=json.dumps(message_data).encode("utf-8"))

    # Wait for the next request-to-speak signal
    await request_to_speak_event.wait()

    return {"answer": last_slim_answer}


@app.get("/health")
async def health():
    return {"status": "healthy"}


async def initialize_slim(args):
    """Initialize the SLIM instance asynchronously."""
    global slim

    slim = SLIM(
        slim_endpoint=args.endpoint,
        local_id="noa-user-proxy",
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
        slim_connector.register("user_proxy_agent")

        SLIMInstrumentor().instrument()

    # Start receiving messages from SLIM
    asyncio.create_task(slim.receive(callback=command_callback))


def run():
    """Parse arguments, initialize SLIM, and run the FastAPI server."""
    parser = argparse.ArgumentParser(description="Start SLIM FastAPI interface.")
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("SLIM_ENDPOINT", "http://localhost:12345"),
        help="SLIM endpoint URL (e.g., http://localhost:46357)",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=int(os.getenv("PORT", 8000)),
        help="Server port (default 8000)",
    )
    args = parser.parse_args()

    # Use asyncio.run() for the initialization of SLIM and FastAPI server
    async def start_server():
        await initialize_slim(args)  # Initialize SLIM
        config = uvicorn.Config(app, host="0.0.0.0", port=args.port)
        server = uvicorn.Server(config)
        await server.serve()  # Start FastAPI server

    asyncio.run(start_server())


if __name__ == "__main__":
    run()
