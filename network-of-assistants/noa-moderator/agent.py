# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Literal, Union, Annotated

from llm import load_llm

from ioa_observe.sdk.decorators import agent, workflow, graph

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are a noa-moderator agent in a chat with a user and several
specialized agents. Your job is to orchestrate these agents by
granting them the right to speak when needed until you decide
the query is answered, and you answer following the requested
format when provided.

You will be given a list of agents, a chat history, and an incoming
message. From this message, you always answer with a directory
containing a list of messages. These messages can:
- directly answer in the chat message
{{"type": "ChatMessage", "author": "noa-moderator", "message": "<your-message>"}}
- grant an agent the right to speak by sending a RequestToSpeak message to an agent <agent-id>, with the question addressed to this agent
{{"type": "RequestToSpeak", "author": "noa-moderator", "target": "<agent-id>", "message": "<query-for-agent>}}
- decide the query was answered and give the ball back to the user (by sending a RequestToSpeak to the user proxy with an empty message)
{{"type": "RequestToSpeak", "author": "noa-moderator", "target": "noa-user-proxy", "message": ""}}

---

# Example flow:

Given an agent list:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

### Example 1: Answer yourself and give the ball back to the user

History: []
Query: {{"type": "ChatMessage", "author": "noa-user-proxy", "message": "Hello!"}}
Your answer:
{{"messages": [{{"type": "ChatMessage", "author": "noa-moderator", "message": "Hello user, how can I help?"}}, {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "noa-user-proxy", "message": ""}}]}}

### Example 2: Break down a task into several smaller queries that agents can answer

History: []
Query: {{"type": "ChatMessage", "author": "noa-user-proxy", "message": "What is the temperature difference between New York and Paris?"}}
Your answer:
{{"messages": [{{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in New York?"}}]}}

### Example 3: Receive an answer and continue your process with another agent

History: [{{"type": "ChatMessage", "author": "noa-user-proxy", "message": "What is the temperature difference between New York and Paris?"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in New York?"}}]
Query: {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"}}
Your answer:
{{"messages": [{{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in Paris?"}}]}}

### Example 4: Combine answers for another agent

History: [{{"type": "ChatMessage", "author": "noa-user-proxy", "message": "What is the temperature difference between New York and Paris?"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in New York?"}},
          {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in Paris?"}}]
Query: {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 80F in Paris"}}
Your answer:
{{"messages": [{{"type": "RequestToSpeak", "author": "noa-moderator", "target": "math-agent", "message": "What is 95-80?"}}]}}

### Example 5: Combine answer, reply back to the user, and give the ball back to the user

History: [{{"type": "ChatMessage", "author": "noa-user-proxy", "message": "What is the temperature difference between New York and Paris?"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in New York?"}},
          {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "weather-agent", "message": "What is the weather in Paris?"}},
          {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 80F in Paris"}},
          {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "math-agent", "message": "What is 95-80?"}}]
Query: {{"type": "ChatMessage", "author": "math-agent", "message": "15"}}
Your answer:
{{"messages": [{{"type": "ChatMessage", "author": "noa-moderator", "message": "15F"}}, {{"type": "RequestToSpeak", "author": "noa-moderator", "target": "noa-user-proxy", "message": ""}}]}}

Note: it is important that you always finish by sending a RequestToSpeak after sending your answer to the user-proxy to give the ball back to the user. Reply according to best effort and don't insist too many times if an agent is unable to answer.

"""

INPUT_PROMPT = """
Agent list:
{agents_list}

History: {chat_history}
Query: {query_message}
Your answer:
"""

PROMPT_TEMPLATE = ChatPromptTemplate([("system", SYSTEM_PROMPT), ("user", INPUT_PROMPT)])


@agent(name="moderator-agent", description="Orchestrates the agents in the chat, granting them the right to speak when needed.")
class ModeratorAgent:
    def __init__(self, assistants_dir):
        class ChatMessage(BaseModel):
            type: Literal["ChatMessage"]
            author: str
            message: str = ""

        class RequestToSpeak(BaseModel):
            type: Literal["RequestToSpeak"]
            author: str
            target: str

        class ModelAnswer(BaseModel):
            messages: List[Annotated[Union[ChatMessage, RequestToSpeak], Field(discriminator="type")]]

        self.assistants_dir = assistants_dir
        self.assistants = {}

        llm = load_llm(env_prefix="MODERATOR_LLM_")

        parser = JsonOutputParser(pydantic_object=ModelAnswer)

        self.chain = PROMPT_TEMPLATE | llm | parser

    #@workflow(name="moderator-agent-chatbot")
    def invoke(self, input):
        input["agents_list"] = self.assistants
        return self.chain.invoke(input=input)

    @graph(name="noa-flow")
    def init_run(self):
        available_agents_list = []

        for filename in os.listdir(self.assistants_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.assistants_dir, filename)
                try:
                    with open(file_path, "r") as file:
                        data = json.load(file)
                        available_agents_list.append(
                            {
                                "name": "noa-" + data["name"].lower().strip().replace(" ", "-"),
                                "description": data["description"],
                            }
                        )
                except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                    log.error(f"Error reading {file_path}: {e}")

        output_strings = []
        output_graph = {"noa-moderator": "noa-moderator"}
        for agt in available_agents_list:
            output_strings.append(f"- {agt['name']}: {agt['description']}")
            output_graph[agt["name"]] = agt["name"]

        self.assistants = "\n".join(output_strings)

        return output_graph
