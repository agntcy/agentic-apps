# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import os
import asyncio
import uuid
from marketing_campaign.app import graph
from marketing_campaign.state import OverallState, ConfigModel
from marketing_campaign import mailcomposer
from marketing_campaign.email_reviewer import TargetAudience
from langchain_core.runnables.config import RunnableConfig
from langgraph.types import Command


async def main():
    print("What marketing campaign do you want to create?")
    inputState = OverallState(
        messages=[], operation_logs=[], has_composer_completed=False
    )
    while True:
        thread_id = uuid.uuid4()
        usermsg = input("YOU [Type OK when you are happy with the email proposed] >>> ")

        inputState.messages.append(
            mailcomposer.Message(content=usermsg, type=mailcomposer.Type.human)
        )

        config = ConfigModel(
            recipient_email_address=os.environ["RECIPIENT_EMAIL_ADDRESS"],
            sender_email_address=os.environ["SENDER_EMAIL_ADDRESS"],
            target_audience=TargetAudience.academic,
            thread_id=str(thread_id),
        ).model_dump()
        thread = RunnableConfig(configurable=config)

        output = await graph.ainvoke(inputState, thread)

        curr_state = graph.get_state(thread)

        # Check if graph is interrupted by mailcomposer
        while len(curr_state.tasks) and len(curr_state.tasks[0].interrupts) > 0:
            commad = Command(
                resume=mailcomposer.Message(
                    content="I need it in html", type=mailcomposer.Type.human
                ).model_dump()
            )
            # Send a signal to the graph to resume execution
            await graph.ainvoke(commad, config=thread)
            curr_state = graph.get_state(thread)

        curr_state = graph.get_state(thread)
        outputState = OverallState.model_validate(output)

        if len(outputState.operation_logs) > 0:
            print(outputState.operation_logs)
            break
        else:
            print(outputState.messages[-1].content)
        inputState = outputState


if __name__ == "__main__":
    asyncio.run(main())
