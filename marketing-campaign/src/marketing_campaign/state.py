# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
from agntcy_acp.langgraph.api_bridge import APIBridgeOutput, APIBridgeInput
from pydantic import BaseModel, Field
from typing import List, Optional
from marketing_campaign import mailcomposer
from marketing_campaign import email_reviewer

class ConfigModel(BaseModel):
    recipient_email_address: str = Field(..., description="Email address of the email recipient")
    sender_email_address: str = Field(..., description="Email address of the email sender")
    target_audience: email_reviewer.TargetAudience = Field(..., description="Target audience for the marketing campaign")

class MailComposerState(BaseModel):
    input: Optional[mailcomposer.InputSchema] = None
    output: Optional[mailcomposer.OutputSchema] = None

class MailReviewerState(BaseModel):
    input: Optional[email_reviewer.InputSchema] = None
    output: Optional[email_reviewer.OutputSchema] = None

class SendGridState(BaseModel):
    input: Optional[APIBridgeInput] = None
    output: Optional[APIBridgeOutput]= None

class OverallState(BaseModel):
    messages: List[mailcomposer.Message] = Field([], description="Chat messages")
    operation_logs: List[str] = Field([],
                                      description="An array containing all the operations performed and their result. Each operation is appended to this array with a timestamp.",
                                      examples=[["Mar 15 18:10:39 Operation performed: email sent Result: OK",
                                                 "Mar 19 18:13:39 Operation X failed"]])

    has_composer_completed: Optional[bool] = Field(None, description="Flag indicating if the mail composer has succesfully completed its task")
    has_reviewer_completed: Optional[bool] = None
    has_sender_completed: Optional[bool] = None
    mailcomposer_state: Optional[MailComposerState] = None
    email_reviewer_state: Optional[MailReviewerState] = None
    target_audience: Optional[email_reviewer.TargetAudience] = None
    sendgrid_state: Optional[SendGridState] = None
    recipient_email_address: Optional[str] = Field(
        None, description="Email address of the email recipient"
    )
    sender_email_address: Optional[str] = Field(
        None, description="Email address of the email sender"
    )
