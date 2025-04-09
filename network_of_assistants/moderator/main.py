import json
from agp import AGP
from agent import ModeratorAgent


def agents_list_to_string(agents_list):
    output_strings = []
    for agent in agents_list:
        output_strings += f"- {agent['name']}: {agent['description']}"
    return "\n".join(output_strings)


async def main():
    # Instantiate the AGP class
    agp = AGP(
        agp_endpoint="http://localhost:12345",
        local_id="moderator",
        shared_space="chat",
    )

    await agp.init()

    chat_history = []

    async def on_message_received(message: bytes):
        # Decode the message from bytes to string
        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        print(f"Received message: {json_message}")
        chat_history.append(json_message)

        if json_message["type"] == "ChatMessage":
            answer = moderator_agent.invoke(
                input={
                    "agents_list": agents_list_string,
                    "chat_history": chat_history,
                    "query_message": json_message,
                }
            )
            print(f"Sending answer: {answer}")
            chat_history.append(answer)
            await agp.publish(msg=str(answer).encode("utf-8"))

    # Connect to the AGP server and start receiving messages
    await agp.connect_and_receive(callback=on_message_received)
    await agp.receive_task


if __name__ == "__main__":
    import asyncio

    moderator_agent = ModeratorAgent()

    agents_list = [
        {"name": "catalyst-assistant", "description": "An assistant agent specialized in Cisco Catalyst products."},
        {"name": "meraki-assistant", "description": "An assistant agent specialized in Cisco Meraki products."},
        {
            "name": "splunk-assistant",
            "description": "An assistant agent specialized in Splunk integration with Cisco products.",
        },
        {
            "name": "thousandeyes-assistant",
            "description": "An assistant agent specialized in Cisco Thousand Eyes products.",
        },
        {"name": "webex-assistant", "description": "An assistant agent specialized in Cisco Webex products."},
    ]
    agents_list_string = agents_list_to_string(agents_list)

    # Run the main function
    asyncio.run(main())
