from agent import ModeratorAgent


def agents_list_to_string(agents_list):
    output_strings = []
    for agent in agents_list:
        output_strings += f"- {agent['name']}: {agent['description']}"
    return "\n".join(output_strings)


def main():
    moderator_agent = ModeratorAgent()

    agents_list = [
        {"name": "webex-agent", "description": "An agent answering Webex related questions"},
        {"name": "catalyst-agent", "description": "An agent answering Catalyst related questions"},
    ]

    query = "How can I configure my router?"

    agents_list_string = agents_list_to_string(agents_list)

    result = moderator_agent.invoke(input={"agents_list": agents_list_string, "query": query})

    print(result.content)


if __name__ == "__main__":
    main()
