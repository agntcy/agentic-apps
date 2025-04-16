# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
from enum import Enum
from typing import Any, Optional
from pydantic import Field
from dotenv import load_dotenv

from llama_index.core.llms.llm import LLM
from llama_index.core.workflow import (
    Event,
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)
from llama_index.core.prompts import RichPromptTemplate
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.llms.openai import OpenAI

load_dotenv()

class TargetAudience(str, Enum):
    general = 'general'
    technical = 'technical'
    business = 'business'
    academic = 'academic'


class LogEvent(Event):
    msg: str
    delta: bool = False


class EmailReviewerInput(StartEvent):
    email: str = Field(
        ..., description='The email content to be reviewed and corrected'
    )
    target_audience: TargetAudience = Field(
        ...,
        description='The target audience for the email, affecting the style of review',
    )


class EmailReview(StopEvent):
    correct: bool = Field(
        ...,
        description='Indicates whether the email is correct and requires no changes',
    )
    corrected_email: Optional[str] = Field(
        None,
        description='The corrected version of the email, if changes were necessary',
    )


EMAIL_REVIEWER_PROMPT_TEMPLATE = RichPromptTemplate(
"""
{% chat role="system" %}
You are an email reviewer assistant, in charge of reviewing an email
{% endchat %}

{% chat role="user" %}
Your tasks are:
1) Check whether the provided email has no writing errors
2) Check whether the provided email matches the target audience
3) If the email has writing errors or does not match the target audience below, correct the email.

The target audience:
{{ target_audience }}

The email:
{{ email }}
{% endchat %}
"""
)

AUDIENCE_DESCRIPTIONS_MAP = {
    "general": "General Audience",
    "technical": "Technical Audience. This audience is familiar with IT, software development, and programming.",
    "business": "Business Audience. This audience is familiar with business and management.",
    "academic": "Academic Audience. This audience is familiar with academic writing and research.",
}


class EmailReviewer(Workflow):
    def __init__(
        self,
        llm: LLM | None = None,
        verbose: bool = False,
        **workflow_kwargs: Any,
    ) -> None:
        super().__init__(verbose=verbose, **workflow_kwargs)

        # Can use Azure OpenAI or OpenAI based on the environment variables
        if os.getenv("AZURE_OPENAI_MODEL"):
            self.llm = llm or AzureOpenAI(
                model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini"),
                deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-07-01-preview"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "https://<your-resource-name>.openai.azure.com/"),
            )
        else:
            self.llm = llm or OpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY", "Fake"),
            )

    @step
    async def review_email(
        self, ctx: Context, ev: EmailReviewerInput
    ) -> EmailReview:
        if self._verbose:
            ctx.write_event_to_stream(
                LogEvent(msg=f"Reviewing email for audience {ev.target_audience}"))

        audience_descr = AUDIENCE_DESCRIPTIONS_MAP.get(
            ev.target_audience, "General Audience"
        )

        review: EmailReview = await self.llm.astructured_predict(
            EmailReview,
            EMAIL_REVIEWER_PROMPT_TEMPLATE,
            target_audience=audience_descr,
            email=ev.email,
        )

        return review


async def main():
    start_event = EmailReviewerInput(
        target_audience="technical",
        email="""
Dear Team,

I am writng to inform you that the server will be down for maintenance on Saturday, 25th December 2022 from 8:00 AM to 12:00 PM. During this time, the server won't not be accessible.

We apologize for any inconvenience this may cause and appreciate your understandings.

Best regards,
John Doe"""
    )

    workflow = EmailReviewer(
        verbose=True,
    )

    handler = workflow.run(start_event=start_event)

    async for ev in handler.stream_events():
        if isinstance(ev, LogEvent):
            print(ev.msg)


    final_result: EmailReview = await handler
    print(f"Reviewed Email:\nCorrect: {final_result.correct}\nCorrected Email:\n{final_result.corrected_email}")

if __name__ == "__main__":
    asyncio.run(main())
