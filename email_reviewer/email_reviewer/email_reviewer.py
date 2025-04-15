# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import asyncio
from typing import Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from llama_index.core.agent.react import ReActChatFormatter, ReActOutputParser
from .state import EmailReviewerInput, EmailReview, ConfigSchema

from llama_index.core.llms.llm import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools.types import BaseTool
from llama_index.core.workflow import (
    Event,
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.llms.azure_openai import AzureOpenAI

load_dotenv()

class LogEvent(Event):
    msg: str
    delta: bool = False



EMAIL_REVIEWER_SYSTEM_PROMPT = "You are an email reviewer assistant, in charge of reviewing an email"

EMAIL_REVIEWER_USER_PROMPT = """Your tasks are:
1) Check whether the provided email has no writing errors
2) Check whether the provided email matches the target audience
3) If the email has writing errors or does not match the target audience below, correct the email.

The target audience:
{target_audience}

The email:
{email}
"""

AUDIENCE_DESCRIPTIONS_MAP = {
    "general": "General Audience",
    "technical": "Technical Audience. This audience is familiar with IT, software development, and programming.",
    "business": "Business Audience. This audience is familiar with business and management.",
    "academic": "Academic Audience. This audience is familiar with academic writing and research.",
}


class EmailReviewer(Workflow):
    def __init__(
        self,
        *args: Any,
        llm: LLM | None = None,
        tools: list[BaseTool] | None = None,
        extra_context: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tools = tools or []

        self.llm = llm or AzureOpenAI(
            model="gpt-4o",
            deployment_name="gpt-4o",
            api_version="2024-07-01-preview",
            temperature=0,
            seed=42,
        )

        self.memory = ChatMemoryBuffer.from_defaults(llm=llm)
        self.formatter = ReActChatFormatter.from_defaults(
            context=extra_context or ""
        )
        self.output_parser = ReActOutputParser()
        self.sources = []

    @step
    async def review_email(
        self, ctx: Context, ev: StartEvent
    ) -> StopEvent:
        if self._verbose:
            ctx.write_event_to_stream(
                LogEvent(msg=f"Reviewing email for audience {ev.target_audience}"))

        audience_descr = AUDIENCE_DESCRIPTIONS_MAP.get(
            ev.target_audience, "General Audience")

        prompt = ChatPromptTemplate.from_messages([
            ("system", EMAIL_REVIEWER_SYSTEM_PROMPT),
            ("user", EMAIL_REVIEWER_USER_PROMPT)
        ])
        review = await self.llm.astructured_predict(
            EmailReview,
            prompt,
            target_audience=audience_descr,
            email=ev.email,
        )
        return StopEvent(result=review.model_dump())


def email_reviewer_workflow() -> EmailReviewer:
    email_reviewer_workflow = EmailReviewer(timeout=120.0)
    return email_reviewer_workflow


async def main():
    audience_example = "technical"
    email_example = """
        Dear Team,

        I am writng to inform you that the server will be down for maintenance on Saturday, 25th December 2022 from 8:00 AM to 12:00 PM. During this time, the server won't not be accessible.

        We apologize for any inconvenience this may cause and appreciate your understandings.

        Best regards,
        John Doe
    """

    workflow = EmailReviewer(
        verbose=True,
    )

    # print(await workflow.run(email=email_example, target_audience=audience_example))


    handler = workflow.run(email=email_example, target_audience=audience_example)

    async for ev in handler.stream_events():
        print("ev: ", type(ev), ev)


    final_result = await handler
    print("Final result", final_result)

if __name__ == "__main__":
    asyncio.run(main())
