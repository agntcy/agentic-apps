import os
import json
import argparse
from agp import AGP
from agent import ModeratorAgent
from langchain_core.exceptions import OutputParserException


def list_available_agents(agents_dir):
    available_agents_list = []

    for filename in os.listdir(agents_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(agents_dir, filename)
            try:
                with open(file_path, "r") as file:
                    data = json.load(file)
                    available_agents_list.append(
                        {"name": data["name"].lower().strip().replace(" ", "-"), "description": data["description"]}
                    )
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                print(f"Error reading {file_path}: {e}")

    output_strings = []
    for agent in available_agents_list:
        output_strings.append(f"- {agent['name']}: {agent['description']}")
    return "\n".join(output_strings)


async def main(args):
    # Instantiate the AGP class
    agp = AGP(
        agp_endpoint=args.endpoint,
        local_id="moderator",
        shared_space="chat",
    )
    await agp.init()

    agents_dir = args.agents_dir

    moderator_agent = ModeratorAgent()

    chat_history = []

    async def on_message_received(message: bytes):
        # Decode the message from bytes to string
        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        print(f"Received message: {json_message}")
        chat_history.append(json_message)

        if json_message["type"] == "ChatMessage":
            try:
                answers_list = moderator_agent.invoke(
                    input={
                        "agents_list": list_available_agents(agents_dir),
                        "chat_history": chat_history,
                        "query_message": json_message,
                    }
                )
                for answer in answers_list["messages"]:
                    print(f"Sending answer: {answer}")
                    chat_history.append(answer)
                    answer_str = json.dumps(answer)
                    await agp.publish(msg=answer_str.encode("utf-8"))

            except OutputParserException as e:
                print(f"Wrong format from moderator: {e}")

                answer = {
                    "type": "ChatMessage",
                    "author": "moderator",
                    "message": f"Moderator failed: {e}",
                }
                chat_history.append(answer)
                answer_str = json.dumps(answer)
                await agp.publish(msg=answer_str.encode("utf-8"))
                answer = {
                    "type": "RequestToSpeak",
                    "author": "moderator",
                    "target": "user-proxy",
                }
                chat_history.append(answer)
                answer_str = json.dumps(answer)
                await agp.publish(msg=answer_str.encode("utf-8"))

    # Connect to the AGP server and start receiving messages
    await agp.receive(callback=on_message_received)
    await agp.receive_task


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Start AGP command interface.")
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:12345",
        help="AGP endpoint URL (e.g., http://localhost:12345)",
    )
    parser.add_argument(
        "--agents-dir",
        type=str,
        default="../ads/datamodels",
        help="Directory of available agent specs",
    )
    args = parser.parse_args()

    # Run the main function
    asyncio.run(main(args))
