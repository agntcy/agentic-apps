# Generated from ACP Descriptor org.agntcy.mail_reviewer using datamodel_code_generator.

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, RootModel


class ConfigSchema(RootModel[Any]):
    root: Any = Field(..., title='ConfigSchema')


class InputSchema(BaseModel):
    email: str = Field(
        ..., description='The email content to be reviewed and corrected', title='Email'
    )
    target_audience: TargetAudience = Field(
        ...,
        description='The target audience for the email, affecting the style of review',
    )


class OutputSchema(BaseModel):
    correct: bool = Field(
        ...,
        description='Indicates whether the email is correct and requires no changes',
        title='Correct',
    )
    corrected_email: Optional[str] = Field(
        None,
        description='The corrected version of the email, if changes were necessary',
        title='Corrected Email',
    )


class TargetAudience(Enum):
    general = 'general'
    technical = 'technical'
    business = 'business'
    academic = 'academic'
