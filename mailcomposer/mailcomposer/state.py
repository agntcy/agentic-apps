# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
from enum import Enum
from typing import Optional, Annotated

from pydantic import BaseModel, Field
import operator
class Type(Enum):
    human = 'human'
    assistant = 'assistant'
    ai = 'ai'


class Message(BaseModel):
    type: Type = Field(
        ...,
        description='indicates the originator of the message, a human or an assistant',
    )
    content: str = Field(..., description='the content of the message')


class ConfigSchema(BaseModel):
    test: bool


class AgentState(BaseModel):
    messages: Annotated[Optional[list[Message]], operator.add] = []
    is_completed: Optional[bool] = None

class StatelessAgentState(BaseModel):
    messages: Optional[list[Message]] = []
    is_completed: Optional[bool] = None


class OutputState(AgentState):
    final_email: Optional[str] = Field(
        default=None,
        description="Final email produced by the mail composer, in html format"
    )

class StatelessOutputState(StatelessAgentState):
    final_email: Optional[str] = Field(
        default=None,
        description="Final email produced by the mail composer, in html format"
    )
