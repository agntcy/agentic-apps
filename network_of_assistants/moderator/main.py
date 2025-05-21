import os
import json
import argparse
from agp import AGP
from agent import ModeratorAgent
from langchain_core.exceptions import OutputParserException
from evaluator import EvaluatorAgent

from poirot.sdk.decorators import agent, graph
from poirot.sdk import Poirot
from poirot.sdk.connectors.agp import AGPConnector, process_agp_msg

Poirot.init("moderator-agent", api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT", "http://host.docker.internal:4318"))

def list_available_agents(agents_dir):
    available_agents = {}

    for filename in os.listdir(agents_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(agents_dir, filename)
            try:
                with open(file_path, "r") as file:
                    data = json.load(file)
                    available_agents[data["name"].lower().strip().replace(" ", "-")] = (
                        data["description"]
                    )
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                print(f"Error reading {file_path}: {e}")

    return available_agents


def agents_to_string(agents):
    output_strings = []
    for name, description in agents.items():
        output_strings.append(f"- {name}: {description}")
    return "\n".join(output_strings)

class SupervisorAgent:
    def __init__(self):
        self.evaluator_agent, self.moderator_agent = None, None
        self.agp = AGP(
            agp_endpoint=os.getenv("AGP_ENDPOINT", "http://localhost:12345"),
            local_id="moderator",
            shared_space="chat",
        )

    @graph(name="moderator_evaluator_workflow")
    def get_agents(self):
        # Initialize the agents
        self.evaluator_agent = EvaluatorAgent()
        self.moderator_agent = ModeratorAgent()
        
        # Still return the individual agents as a dictionary
        return {
            "evaluator": self.evaluator_agent, 
            "moderator": self.moderator_agent        
        }

async def main(args):
   
    supervisor_agent = SupervisorAgent()

    await supervisor_agent.agp.init()

    # initialize the AGP connector
    agp_connector = AGPConnector(
        remote_org="organization",
        remote_namespace="namespace",
        shared_space="chat",
    )
    # register the agent with the AGP connector
    agp_connector.register("moderator_agent")
    
    agents = supervisor_agent.get_agents()
    evaluator_agent = agents["evaluator"]
    moderator_agent = agents["moderator"]

    agents_dir = args.agents_dir

    chat_history = []

    chat_agents = set()

    @process_agp_msg("moderator_agent")
    async def on_message_received(message: bytes):
        # Decode the message from bytes to string
        decoded_message = message.decode("utf-8")
        json_message = json.loads(decoded_message)

        print(f"Received message: {json_message}")
        chat_history.append(json_message)

        if json_message["type"] == "ChatMessage":
            try:
                available_agents = list_available_agents(agents_dir)
                chat_agents_with_desc = {
                    name: desc
                    for name, desc in available_agents.items()
                    if name in chat_agents
                }

                answers_list = moderator_agent.invoke(
                    input={
                        "agents_list": agents_to_string(available_agents),
                        "chat_agent_list": agents_to_string(chat_agents_with_desc),
                        "chat_history": chat_history,
                        "query_message": json_message,
                    }
                )
                for answer in answers_list["messages"]:
                    if answer["type"] == "InviteToChat":
                        chat_agents.add(answer["target"])

                    print(f"Sending answer: {answer}")
                    chat_history.append(answer)
                    answer_str = json.dumps(answer)

                    evaluator_score = evaluator_agent.invoke(
                        input={
                            "agents_list": list_available_agents(agents_dir),
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

                    await supervisor_agent.agp.publish(msg=answer_str.encode("utf-8"))

            except OutputParserException as e:
                print(f"Wrong format from moderator: {e}")

                answer = {
                    "type": "ChatMessage",
                    "author": "moderator",
                    "message": f"Moderator failed: {e}",
                }
                chat_history.append(answer)
                answer_str = json.dumps(answer)
                await supervisor_agent.agp.publish(msg=answer_str.encode("utf-8"))
                answer = {
                    "type": "RequestToSpeak",
                    "author": "moderator",
                    "target": "user-proxy",
                }
                chat_history.append(answer)
                answer_str = json.dumps(answer)
                await supervisor_agent.agp.publish(msg=answer_str.encode("utf-8"))

    # Connect to the AGP server and start receiving messages
    await supervisor_agent.agp.receive(callback=on_message_received)
    await supervisor_agent.agp.receive_task


def run():
    import asyncio

    parser = argparse.ArgumentParser(description="Start AGP command interface.")
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.environ.get("MODERATOR_AGP_ENDPOINT", "http://localhost:12345"),
        help="AGP endpoint URL (e.g., http://localhost:12345)",
    )
    parser.add_argument(
        "--agents-dir",
        type=str,
        default=os.environ.get("MODERATOR_AGENTS_DIR", "../ads/datamodels"),
        help="Directory of available agent specs",
    )
    args = parser.parse_args()

    # Run the main function
    asyncio.run(main(args))

if __name__ == "__main__":
    run()
