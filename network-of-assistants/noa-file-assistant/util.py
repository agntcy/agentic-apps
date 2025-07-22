# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import uuid
from typing import List, Sequence, cast

from llama_index.core.agent.react.types import ActionReasoningStep, BaseReasoningStep
from llama_index.core.agent.workflow.workflow_events import AgentInput, AgentOutput, AgentStream
from llama_index.core.bridge.pydantic import BaseModel
from llama_index.core.llms import ChatMessage
from llama_index.core.llms.llm import ToolSelection
from llama_index.core.memory import BaseMemory
from llama_index.core.tools import AsyncBaseTool
from llama_index.core.workflow import Context
import requests


async def take_step(
    self,
    ctx: Context,
    llm_input: List[ChatMessage],
    tools: Sequence[AsyncBaseTool],
    memory: BaseMemory,
) -> AgentOutput:
    """Take a single step with the React agent."""
    # remove system prompt, since the react prompt will be combined with it
    if llm_input[0].role == "system":
        system_prompt = llm_input[0].content or ""
        llm_input = llm_input[1:]
    else:
        system_prompt = ""

    output_parser = self.output_parser
    react_chat_formatter = self.formatter
    react_chat_formatter.context = system_prompt

    # Format initial chat input
    current_reasoning: list[BaseReasoningStep] = await ctx.get(self.reasoning_key, default=[])
    input_chat = react_chat_formatter.format(
        tools,
        chat_history=llm_input,
        current_reasoning=current_reasoning,
    )
    ctx.write_event_to_stream(AgentInput(input=input_chat, current_agent_name=self.name))

    # Initial LLM call
    response = await self.llm.achat(input_chat)
    # last_chat_response will be used later, after the loop.
    # We initialize it so it's valid even when 'response' is empty
    # last_chat_response = ChatResponse(message=ChatMessage())
    for last_chat_response in [response]:
        raw = (
            last_chat_response.raw.model_dump()
            if isinstance(last_chat_response.raw, BaseModel)
            else last_chat_response.raw
        )
        ctx.write_event_to_stream(
            AgentStream(
                delta=last_chat_response.delta or "",
                response=last_chat_response.message.content or "",
                tool_calls=[],
                raw=raw,
                current_agent_name=self.name,
            )
        )

    # Parse reasoning step and check if done
    message_content = last_chat_response.message.content
    if not message_content:
        raise ValueError("Got empty message")

    try:
        reasoning_step = output_parser.parse(message_content, is_streaming=False)
    except ValueError as e:
        error_msg = (
            f"Error: Could not parse output. Please follow the thought-action-input format. Try again. Details: {e!s}"
        )
        await memory.aput(last_chat_response.message)
        await memory.aput(ChatMessage(role="user", content=error_msg))

        raw = (
            last_chat_response.raw.model_dump()
            if isinstance(last_chat_response.raw, BaseModel)
            else last_chat_response.raw
        )
        return AgentOutput(
            response=last_chat_response.message,
            tool_calls=[],
            raw=raw,
            current_agent_name=self.name,
        )

    # add to reasoning if not a handoff
    current_reasoning.append(reasoning_step)
    await ctx.set(self.reasoning_key, current_reasoning)

    # If response step, we're done
    raw = (
        last_chat_response.raw.model_dump() if isinstance(last_chat_response.raw, BaseModel) else last_chat_response.raw
    )
    if reasoning_step.is_done:
        return AgentOutput(
            response=last_chat_response.message,
            tool_calls=[],
            raw=raw,
            current_agent_name=self.name,
        )

    reasoning_step = cast(ActionReasoningStep, reasoning_step)
    if not isinstance(reasoning_step, ActionReasoningStep):
        raise ValueError(f"Expected ActionReasoningStep, got {reasoning_step}")

    # Create tool call
    tool_calls = [
        ToolSelection(
            tool_id=str(uuid.uuid4()),
            tool_name=reasoning_step.action,
            tool_kwargs=reasoning_step.action_input,
        )
    ]

    return AgentOutput(
        response=last_chat_response.message,
        tool_calls=tool_calls,
        raw=raw,
        current_agent_name=self.name,
    )
