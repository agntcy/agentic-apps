# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import os
import asyncio
from marketing_campaign.state import OverallState, ConfigModel
from marketing_campaign import mailcomposer
from marketing_campaign.email_reviewer import TargetAudience
from agntcy_acp import AsyncACPClient, ApiClientConfiguration
from agntcy_acp.acp_v0.async_client.api_client import ApiClient as AsyncApiClient

from agntcy_acp.models import (
    RunCreateStateless,
    RunResult,
    RunError,
    Config,
)


async def main():
    print("What marketing campaign do you want to create?")
    inputState = OverallState(
        messages=[],
        operation_logs=[],
        has_composer_completed=False
    )

    marketing_campaign_id = os.environ.get("MARKETING_CAMPAIGN_ID", "")
    client_config = ApiClientConfiguration.fromEnvPrefix("MARKETING_CAMPAIGN_")

    while True:
        usermsg = input("YOU [Type OK when you are happy with the email proposed] >>> ")
        inputState.messages.append(mailcomposer.Message(content=usermsg, type=mailcomposer.Type.human))
        run_create = RunCreateStateless(
            agent_id=marketing_campaign_id,
            input=inputState.model_dump(),
            config=Config(configurable=ConfigModel(
                recipient_email_address=os.environ["RECIPIENT_EMAIL_ADDRESS"],
                sender_email_address=os.environ["SENDER_EMAIL_ADDRESS"],
                target_audience=TargetAudience.academic
            ).model_dump())
        )
        async with AsyncApiClient(configuration=client_config) as api_client:
            acp_client = AsyncACPClient(api_client=api_client)
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

            runState = run_result.values # type: ignore
            outputState = OverallState.model_validate(runState)
            if len(outputState.operation_logs) > 0:
                print(outputState.operation_logs)
                break
            else:
                print(outputState.messages[-1].content)
            inputState = outputState



if __name__ == "__main__":
    asyncio.run(main())