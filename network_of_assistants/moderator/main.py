import json
from agp import AGP
from agent import ModeratorAgent
from langchain_core.exceptions import OutputParserException
from evaluator import EvaluatorAgent

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
            try:
                answers_list = moderator_agent.invoke(
                    input={
                        "agents_list": agents_list_string,
                        "chat_history": chat_history,
                        "query_message": json_message,
                    }
                )
                for answer in answers_list["messages"]:
                    print(f"Sending answer: {answer}")
                    chat_history.append(answer)
                    answer_str = json.dumps(answer)
                    evaluator_score = evaluator_agent.invoke(
                        input={
                            "agents_list": agents_list_string,
                            "chat_history": chat_history,
                            "query_message": json_message,
                            "moderator_answer": answer_str
                        }
                    )
                    if not "NA" in evaluator_score:
                        if "0" in evaluator_score:
                            print(f"The evaluator judges that the moderator did not choose the best-fitting agent.")
                        else:
                            print(f"The evaluator judges that moderator chose the best-fitting agent.")
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

    moderator_agent = ModeratorAgent()
    evaluator_agent = EvaluatorAgent()

    agents_list = [
        {
            "name": "catalyst-assistant",
            "description": "An assistant agent specialized in Cisco Catalyst products.",
        },
        {
            "name": "meraki-assistant",
            "description": "An assistant agent specialized in Cisco Meraki products.",
        },
        {
            "name": "splunk-assistant",
            "description": "An assistant agent specialized in Splunk integration with Cisco products.",
        },
        {
            "name": "thousandeyes-assistant",
            "description": "An assistant agent specialized in Cisco Thousand Eyes products.",
        },
        {
            "name": "webex-assistant",
            "description": "An assistant agent specialized in Cisco Webex products.",
        },
    ]
    agents_list_string = agents_list_to_string(agents_list)

    # Run the main function
    asyncio.run(main())
