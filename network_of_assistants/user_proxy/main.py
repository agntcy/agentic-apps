import argparse
import asyncio
from agp import AGP
import json

# Queue for receiving responses
response_queue = asyncio.Queue()

async def command_callback(response):
    decoded_message = response.decode("utf-8")
    data = json.loads(decoded_message)

    if data["type"] == "ChatMessage":
        print('author:', data["author"])
        print('message;', data["message"])
    elif data["type"] == "RequestToSpeak":
        print('debug:', data["type"], data["author"], data["target"])
        if data["target"] == 'user-proxy':
            response_queue.put_nowait(decoded_message)


async def main(args):
    agp = AGP(
        agp_endpoint=args.endpoint,
        local_id=args.local_id,
        shared_space=args.shared_space,
    )

    print("Welcome to the NoA! Type your message. Type 'quit' to exit.")
    await agp.init()
    asyncio.create_task(agp.receive(callback=command_callback))

    while True:
        inputMessage = input("Message: ").strip().lower()
        if inputMessage == "quit":
            print("Exiting the application. Goodbye!")
            break

        print("Sending message...")

        message = {

            "type": "ChatMessage",
            "author":"user-proxy",
            "message": inputMessage,

        }

        await agp.publish(msg=json.dumps(message).encode("utf-8"))

        print("Waiting for response...")
        response = await response_queue.get()
        print(f"Received message: {response}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start AGP command interface.")
    parser.add_argument("--endpoint", type=str, default="http://localhost:46357" , help="AGP endpoint URL (e.g., http://localhost:46357)")
    parser.add_argument("--local-id", type=str, default="localid", help="Local ID to identify this instance")
    parser.add_argument("--shared-space", type=str, default="chat", help="Shared space name for communication")

    args = parser.parse_args()
    asyncio.run(main(args))
