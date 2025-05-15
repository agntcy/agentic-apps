# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os

import gradio as gr
from marketing_campaign import mailcomposer
from marketing_campaign.email_reviewer import TargetAudience
from marketing_campaign.state import ConfigModel, OverallState

from agntcy_acp.acp_v0.async_client.api_client import ApiClient
from agntcy_acp import ApiClientConfiguration, AsyncACPClient
from agntcy_acp.models import (
    Config,
    RunCreateStateless,
    RunError,
    RunResult,
)

overall_state = OverallState(
    messages=[], operation_logs=[], has_composer_completed=False
)
client_config = None


async def chat_with_bot(api_client, message, history):
    marketing_campaign_id = os.environ.get("MARKETING_CAMPAIGN_ID", "")

    global overall_state
    overall_state.messages.append(
        mailcomposer.Message(content=message, type=mailcomposer.Type.human)
    )

    run_create = RunCreateStateless(
        agent_id=marketing_campaign_id,
        input=overall_state.model_dump(),
        config=Config(
            configurable=ConfigModel(
                recipient_email_address=os.environ["RECIPIENT_EMAIL_ADDRESS"],
                sender_email_address=os.environ["SENDER_EMAIL_ADDRESS"],
                target_audience=TargetAudience.academic,
            ).model_dump()
        ),
    )

    acp_client = AsyncACPClient(api_client=api_client)
    run_output = None

    run_output = await acp_client.create_and_wait_for_stateless_run_output(run_create)

    if run_output.output is None:
        raise Exception("Run output is None")
    actual_output = run_output.output.actual_instance

    if isinstance(actual_output, RunResult):
        run_result: RunResult = actual_output

    elif isinstance(actual_output, RunError):
        run_error: RunError = actual_output
        raise Exception(f"Run Failed: {run_error}")

    else:
        raise Exception(f"ACP Server returned a unsupported response: {run_output}")

    runState = run_result.values  # type: ignore
    outputState = OverallState.model_validate(runState)

    if len(outputState.operation_logs) > 0:
        print(outputState.operation_logs)
    else:
        print(outputState.messages[-1].content)
        history.append({"content": outputState.messages[-1].content, "role": "system"})

    overall_state = outputState

    return outputState.messages[-1].content


async def gradio_ui():
    client_config = ApiClientConfiguration.fromEnvPrefix("MARKETING_CAMPAIGN_")
    api_client = ApiClient(configuration=client_config)

    async with api_client:

        async def response(message, chat_history):
            chat_history.append({"role": "user", "content": message})
            answer = await chat_with_bot(
                api_client, message=message, history=chat_history
            )
            yield answer

        demo = gr.ChatInterface(response, title="LangGraph Chat", type="messages")

        demo.launch(server_port=7861)


def main():
    asyncio.run(gradio_ui())


if __name__ == "__main__":
    main()
