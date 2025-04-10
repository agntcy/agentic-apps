import argparse
import asyncio
from agp import AGP
import json


class color:
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


# Queue for receiving responses
request_to_speak_event = asyncio.Event()


async def command_callback(response):
    decoded_message = response.decode("utf-8")
    data = json.loads(decoded_message)

    if data["type"] == "ChatMessage":
        print(color.BOLD + f"{data['author']}:" + color.END + f" {data['message']}")
    elif data["type"] == "RequestToSpeak":
        print(f"Moderator requested {data['target']} to speak.")
        if data["target"] == "user-proxy":
            request_to_speak_event.set()


async def main(args):
    agp = AGP(
        agp_endpoint=args.endpoint,
        local_id="user-proxy",
        shared_space="chat",
    )

    print("Welcome to the NoA! Type your message. Type 'quit' to exit.")
    await agp.init()
    asyncio.create_task(agp.receive(callback=command_callback))

    while True:
        inputMessage = input(color.BOLD + "Message: " + color.END).strip().lower()
        if inputMessage == "quit":
            print("Exiting the application. Goodbye!")
            break

        message = {
            "type": "ChatMessage",
            "author": "user-proxy",
            "message": inputMessage,
        }

        # clean the request to speak event ready to be told to speak again
        request_to_speak_event.clear()

        await agp.publish(msg=json.dumps(message).encode("utf-8"))

        # wait until we're told to speak again
        await request_to_speak_event.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start AGP command interface.")
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:46357",
        help="AGP endpoint URL (e.g., http://localhost:46357)",
    )

    args = parser.parse_args()
    asyncio.run(main(args))
