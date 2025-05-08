# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import os
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langchain_openai import AzureChatOpenAI
from pydantic import SecretStr
from langchain.prompts import PromptTemplate

from .state import OutputState, AgentState, Message, Type as MsgType

# Initialize the Azure OpenAI model
api_key = os.getenv("AZURE_OPENAI_API_KEY")
if not api_key:
    raise ValueError("AZURE_OPENAI_API_KEY must be set as an environment variable.")

azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not azure_endpoint:
    raise ValueError("AZURE_OPENAI_ENDPOINT must be set as an environment variable.")

llm = AzureChatOpenAI(
    api_key=SecretStr(api_key),
    azure_endpoint=azure_endpoint,
    model="gpt-4o",
    openai_api_type="azure_openai",
    api_version="2024-07-01-preview",
    temperature=0,
    max_retries=10,
    seed=42,
)

# Writer and subject role prompts
MARKETING_EMAIL_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """
You are a highly skilled writer and you are working for a marketing company.
Your task is to write formal and professional emails. We are building a publicity campaign and we need to send a massive number of emails to many clients.
The email must be compelling and adhere to our marketing standards.

If you need more details to complete the email, please ask me.
Once you have all the necessary information, please create the email body. The email must be engaging and persuasive. The subject that cannot exceed 5 words (no bold).
The email should be in the following format
{{separator}}
subject
body
{{separator}}
DO NOT FORGET TO ADD THE SEPARATOR BEFORE THE SUBECT AND AFTER THE EMAIL BODY!
SHOULD NEVER HAPPPEN TO HAVE THE SEPARATOR AFTER THE SUBJECT AND BEFORE THE EMAIL BODY! NEVER AFTER THE SUBJECT!
""",
    template_format="jinja2",
)

# HELLO_MSG = ("Hello! I'm here to assist you in crafting a compelling marketing email "
#     "that resonates with your audience. To get started, could you please provide "
#     "some details about your campaign, such as the target audience, key message, "
#     "and any specific goals you have in mind?")

EMPTY_MSG_ERROR = (
    "Oops! It seems like you're trying to start a conversation with silence. ",
    "An empty message is only allowed if your email is marked complete. Otherwise, let's keep the conversation going! ",
    "Please share some details about the email you want to get.",
)

SEPARATOR = "**************"


def format_email(state):
    answer = interrupt(
        Message(
            type=MsgType.assistant,
            content="In what format would like your email to be?",
        )
    )
    state.messages = (state.messages or []) + [Message(**answer)]
    state_after_formating = generate_email(state)

    new_answer = interrupt(
        Message(type=MsgType.assistant, content="The email is formated, please confirm")
    )

    print(new_answer)

    return final_output(state_after_formating)


def extract_mail(messages) -> str:
    for m in reversed(messages):
        splits: list[str] = []
        if isinstance(m, Message):
            if m.type == MsgType.human:
                continue
            splits = m.content.split(SEPARATOR)
        if isinstance(m, dict):
            if m.get("type", "") == "human":
                continue
            splits = m.get("content", "").split(SEPARATOR)
        if len(splits) >= 3:
            return splits[len(splits) - 2].strip()
        elif len(splits) == 2:
            return splits[1].strip()
    return ""


def should_format_email(state: AgentState):
    if state.is_completed:
        return "format_email"
    return END


def convert_messages(messages: list) -> list[BaseMessage]:
    converted = []
    for m in messages:
        if isinstance(m, Message):
            mdict = m.model_dump()
        else:
            mdict = m
        if mdict["type"] == "human":
            converted.append(HumanMessage(content=mdict["content"]))
        else:
            converted.append(AIMessage(content=mdict["content"]))

    return converted


# Define mail_agent function
def email_agent(state: AgentState) -> OutputState | AgentState:
    """This agent is a skilled writer for a marketing company, creating formal and professional emails for publicity campaigns.
    It interacts with users to gather the necessary details.
    Once the user approves by sending "is_completed": true, the agent outputs the finalized email in "final_email".
    """
    # Check subsequent messages and handle completion
    return final_output(state) if state.is_completed else generate_email(state)


def final_output(state: AgentState) -> OutputState:
    final_mail = extract_mail(state.messages)
    output_state: OutputState = OutputState(
        messages=state.messages,
        is_completed=state.is_completed,
        final_email=final_mail,
    )
    return output_state


def generate_email(state: AgentState) -> AgentState:
    # Generate the email
    llm_messages = [
        Message(
            type=MsgType.human,
            content=MARKETING_EMAIL_PROMPT_TEMPLATE.format(separator=SEPARATOR),
        ),
    ] + (state.messages or [])

    state.messages = (state.messages or []) + [
        Message(
            type=MsgType.ai,
            content=str(llm.invoke(convert_messages(llm_messages)).content),
        )
    ]
    return state


# Create the graph and add the agent node
graph_builder = StateGraph(AgentState, output=OutputState)
graph_builder.add_node("email_agent", email_agent)
graph_builder.add_node("format_email", format_email)

graph_builder.add_edge(START, "email_agent")
graph_builder.add_conditional_edges("email_agent", should_format_email)
graph_builder.add_edge("format_email", END)
graph_builder.add_edge("email_agent", END)

# Set up memory
memory = MemorySaver()

# Compile the graph
graph = graph_builder.compile(checkpointer=memory)
