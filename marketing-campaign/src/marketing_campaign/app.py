# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import os
import copy

from agntcy_iomapper import FieldMetadata
from agntcy_acp.langgraph.api_bridge import APIBridgeAgentNode
from agntcy_acp.langgraph.io_mapper import (
    add_io_mapped_conditional_edge,
    add_io_mapped_edge,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from marketing_campaign import mailcomposer
from marketing_campaign import state
from agntcy_acp.langgraph.acp_node import ACPNode
from agntcy_acp import ApiClientConfiguration
from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables import RunnableConfig
from langchain_openai.chat_models.azure import AzureChatOpenAI
from marketing_campaign import email_reviewer
from marketing_campaign.state import MailComposerState
from langgraph.checkpoint.memory import MemorySaver


# Fill in client configuration for the remote agent
MAILCOMPOSER_AGENT_ID = os.environ.get("MAILCOMPOSER_ID", "")
EMAIL_REVIEWER_AGENT_ID = os.environ.get("EMAIL_REVIEWER_ID", "")
SENDGRID_HOST = os.environ.get("SENDGRID_HOST", "http://localhost:8080")
MAILCOMPOSER_CLIENT_CONFIG = ApiClientConfiguration.fromEnvPrefix("MAILCOMPOSER_")
EMAIL_REVIEWER_CONFIG = ApiClientConfiguration.fromEnvPrefix("EMAIL_REVIEWER_")

# Set to True to generate a mermaid graph
GENERATE_MERMAID_GRAPH = (
    os.environ.get("GENERATE_MERMAID_GRAPH", "False").lower() == "true"
)


def process_inputs(
    state: state.OverallState, config: RunnableConfig
) -> state.OverallState:
    cfg = config.get("configurable", {})

    user_message = state.messages[-1].content
    if "recipient_email_address" not in cfg or "sender_email_address" not in cfg:
        raise ValueError(
            """
            recipient_email_address and/or sender_email_address not provided. 
            You can set them as environment variables 
            RECIPIENT_EMAIL_ADDRESS SENDER_EMAIL_ADDRESS
            """
        )
    state.recipient_email_address = cfg["recipient_email_address"]
    state.sender_email_address = cfg["sender_email_address"]

    if user_message.upper() == "OK":
        state.has_composer_completed = True

    else:
        state.has_composer_completed = False

    state.target_audience = email_reviewer.TargetAudience(cfg["target_audience"])

    state.mailcomposer_state = MailComposerState(
        input=mailcomposer.InputSchema(
            messages=copy.deepcopy(state.messages),
            is_completed=state.has_composer_completed,
        )
    )
    return state


def prepare_output(
    state: state.OverallState, config: RunnableConfig
) -> state.OverallState:
    state.messages = copy.deepcopy(
        state.mailcomposer_state.output.messages
        if (
            state.mailcomposer_state
            and state.mailcomposer_state.output
            and state.mailcomposer_state.output.messages
        )
        else []
    )
    if (
        state.sendgrid_state
        and state.sendgrid_state.output
        and state.sendgrid_state.output.result
    ):
        state.operation_logs.append(
            f"Email Send Operation: {state.sendgrid_state.output.result}"
        )

    return state


def check_final_email(state: state.OverallState):
    return (
        "done"
        if (
            state.mailcomposer_state
            and state.mailcomposer_state.output
            and state.mailcomposer_state.output.final_email
        )
        else "user"
    )


def build_graph() -> CompiledStateGraph:
    llm = AzureChatOpenAI(
        model="gpt-4o-mini",
        api_version="2024-07-01-preview",
        seed=42,
        temperature=0,
    )

    # Instantiate the local ACP node for the remote agent
    acp_mailcomposer = ACPNode(
        name="mailcomposer",
        agent_id=MAILCOMPOSER_AGENT_ID,
        client_config=MAILCOMPOSER_CLIENT_CONFIG,
        input_path="mailcomposer_state.input",
        input_type=mailcomposer.InputSchema,
        output_path="mailcomposer_state.output",
        output_type=mailcomposer.OutputSchema,
    )

    acp_email_reviewer = ACPNode(
        name="email_reviewer",
        agent_id=EMAIL_REVIEWER_AGENT_ID,
        client_config=EMAIL_REVIEWER_CONFIG,
        input_path="email_reviewer_state.input",
        input_type=email_reviewer.InputSchema,
        output_path="email_reviewer_state.output",
        output_type=email_reviewer.OutputSchema,
    )

    # Instantiate APIBridge Agent Node
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY", None)
    if sendgrid_api_key is None:
        raise ValueError("SENDGRID_API_KEY environment variable is not set")

    send_email = APIBridgeAgentNode(
        name="sendgrid",
        input_path="sendgrid_state.input",
        output_path="sendgrid_state.output",
        service_api_key=sendgrid_api_key,
        hostname=SENDGRID_HOST,
        service_name="sendgrid",
    )

    # Create the state graph
    sg = StateGraph(state.OverallState)

    # Add nodes
    sg.add_node(process_inputs)
    sg.add_node(acp_mailcomposer)
    sg.add_node(acp_email_reviewer)
    sg.add_node(send_email)
    sg.add_node(prepare_output)

    # Add edges
    sg.add_edge(START, "process_inputs")
    sg.add_edge("process_inputs", acp_mailcomposer.get_name())
    ## Add conditional edge between mailcomposer and either send_email or END, adding io_mappers between them
    add_io_mapped_conditional_edge(
        sg,
        start=acp_mailcomposer,
        path=check_final_email,
        iomapper_config_map={
            "done": {
                "end": acp_email_reviewer,
                "metadata": {
                    "input_fields": [
                        "mailcomposer_state.output.final_email",
                        "target_audience",
                    ]
                },
            },
            "user": {"end": "prepare_output", "metadata": None},
        },
        llm=llm,
    )

    ## Add conditional edge between mail reviewer and either send_email or END, adding io_mappers between them

    add_io_mapped_edge(
        sg,
        start=acp_email_reviewer,
        end=send_email,
        iomapper_config={
            "input_fields": [
                "sender_email_address",
                "recipient_email_address",
                "mailcomposer_state.output.final_email",
            ],
            "output_fields": [
                FieldMetadata(
                    json_path="sendgrid_state",
                    description="An object that has A prompt asking to send an email. It specifies the email address of the sender, the email address of the recipient and the content of the email.",
                    examples=[
                        "Please send an email from master@info.com to xxx@acme.com: The content of the email should be:\n Dear xxx, I am writing to you the say hello. Best Regards. Alessandro\n",
                        "Write an email from alessandro@company.com  to the reipient 'someone@company.com' : The content of the email should be:\n Hello someone, How are you? Bye. Frank\n",
                    ],
                )
            ],
        },
        llm=llm,
    )

    sg.add_edge(send_email.get_name(), "prepare_output")
    sg.add_edge("prepare_output", END)

    memory = MemorySaver()
    g = sg.compile(checkpointer=memory)
    g.name = "Marketing Campaign Manager"
    if GENERATE_MERMAID_GRAPH:
        with open("___graph.png", "wb") as f:
            f.write(
                g.get_graph().draw_mermaid_png(
                    draw_method=MermaidDrawMethod.API,
                )
            )
    return g


graph = build_graph()
