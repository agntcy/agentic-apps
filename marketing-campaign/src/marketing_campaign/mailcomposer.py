# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
# Generated from ACP Descriptor org.agntcy.mailcomposer using datamodel_code_generator.

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ConfigSchema(BaseModel):
    test: bool = Field(..., title='Test')


class InputSchema(BaseModel):
    messages: Optional[List[Message]] = Field(None, title='Messages')
    is_completed: Optional[bool] = Field(None, title='Is Completed')


class Message(BaseModel):
    type: Type = Field(
        ...,
        description='indicates the originator of the message, a human or an assistant',
    )
    content: str = Field(..., description='the content of the message', title='Content')


class OutputSchema(BaseModel):
    messages: Optional[List[Message]] = Field(None, title='Messages')
    is_completed: Optional[bool] = Field(None, title='Is Completed')
    final_email: Optional[str] = Field(
        None,
        description='Final email produced by the mail composer',
        title='Final Email',
    )


class Type(Enum):
    human = 'human'
    assistant = 'assistant'
    ai = 'ai'
