# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio
from slim import SLIM
import json
import os


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


request_to_speak_event = asyncio.Event()  # Queue for receiving responses


async def command_callback(response):
    """Handle incoming commands and print chat messages."""
    decoded_message = response.decode("utf-8")
    data = json.loads(decoded_message)

    if data.get("type") == "ChatMessage":
        print(
            Color.BOLD
            + Color.DARKCYAN
            + f"{convert_to_title_case(data['author'])}:"
            + Color.END
            + f" {data['message']}"
        )
    elif data.get("type") == "RequestToSpeak" and data.get("target") == "noa-user-proxy":
        request_to_speak_event.set()


async def main(args):
    """Main function to initialize SLIM and handle user input."""
    slim = SLIM(
        slim_endpoint=args.endpoint,
        local_id="noa-user-proxy",
        shared_space="chat",
        opentelemetry_endpoint=os.getenv("OTLP_GRPC_ENDPOINT"),
    )

    print("Welcome to the NoA! Type your message. Type 'quit' to exit.")
    await slim.init()
    asyncio.create_task(slim.receive(callback=command_callback))

    while True:
        input_message = input(Color.BOLD + "Message: " + Color.END).strip().lower()
        if input_message:
            if input_message == "quit":
                print("Exiting the application. Goodbye!")
                break

            message = {
                "type": "ChatMessage",
                "author": "noa-user-proxy",
                "message": input_message,
            }

            request_to_speak_event.clear()  # Prepare for the next message
            await slim.publish(msg=json.dumps(message).encode("utf-8"))

            await request_to_speak_event.wait()  # Wait to be allowed to speak again


def run():
    """Parse arguments and run the main event loop."""
    parser = argparse.ArgumentParser(description="Start SLIM command interface.")
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("SLIM_ENDPOINT", "http://localhost:12345"),
        help="SLIM endpoint URL (e.g., http://localhost:46357)",
    )

    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    run()
