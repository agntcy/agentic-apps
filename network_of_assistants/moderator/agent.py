from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from typing import Optional, List, Literal, Union, Annotated

SYSTEM_PROMPT = """
You are a moderator agent in a chat with a user and several
specialized agents. Your job is to orchestrate these agents by
granting them the right to speak when needed until you decide
the query is answered. To do so, you produce a list of either
messages or requests to speak to the chat.

You will be given:
- a list of available agents
- a list of agents in this chat
- a chat history
- an incoming message

From this message, you can:
- invite an agent to the chat (if not already present) with a brief summary of the ask
{{"type": "InviteToChat", "author": "moderator", "target": "<agent-id>", "summary": "<summary-of-ask>"}}

- grant an agent the right to speak by sending a RequestToSpeak message to an agent <agent-id>.
  IMPORTANT: Only ever grant one agent to speak at a time.
{{"type": "RequestToSpeak", "author": "moderator", "target": "<agent-id>"}}

- decide the query was answered and send a RequestToSpeak to the user proxy 
{{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}

- directly answer yourself in a chat message otherwise
{{"type": "ChatMessage", "author": "moderator", "message": "<your-message>"}}

---

# Examples:

### Example 1: Invite an agent and ask it to speak

All Available Agents:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

Agents Currently in this chat:
- math-agent: Provides answers to mathematical problems

History: []
Query: {{"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"}}
Your answer:
{{"messages": [{{"type": "InviteToChat", "author": "moderator", "target": "weather-agent", "summary": "The user wants to know the weather in New York."}}, 
               {{"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}}]}}

### Example 2: Give the ball back to the user

All Available Agents:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

Agents Currently in this chat:
- weather-agent: Answers queries about the weather

History: [{{"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"}},
          {{"type": "InviteToChat", "author": "moderator", "target": "weather-agent", "summary": "The user wants to know the weather in New York."}},
          {{"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}}]
Query: {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"}},
Your answer:
{{"messages": [{{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}]}}

### Example 3: Answer yourself and give the ball back to the user

All Available Agents:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

Agents Currently in this chat:
- weather-agent: Answers queries about the weather

History: []
Query: {{"type": "ChatMessage", "author": "user-proxy", "message": "Hello!"}}
Your answer:
{{"messages": [{{"type": "ChatMessage", "author": "moderator", "message": "Hello user, how can I help?"}},
               {{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}]}}

"""

INPUT_PROMPT = """
All Available Agents:
{agents_list}

Agents Currently in this chat:
{chat_agent_list}

History: {chat_history}
Query: {query_message}
Your answer:
"""

PROMPT_TEMPLATE = ChatPromptTemplate(
    [("system", SYSTEM_PROMPT), ("user", INPUT_PROMPT)]
)


class ModeratorAgent:
    def __init__(self):
        class ModelConfig(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="MODEL_")
            name: str = "gpt-4o"
            base_url: Optional[str] = None
            api_key: Optional[str] = None

        class ChatMessage(BaseModel):
            type: Literal["ChatMessage"]
            author: str
            message: str = ""

        class RequestToSpeak(BaseModel):
            type: Literal["RequestToSpeak"]
            author: str
            target: str

        class InviteToChat(BaseModel):
            type: Literal["InviteToChat"]
            author: str
            target: str
            summary: str

        class ModelAnswer(BaseModel):
            messages: List[
                Annotated[
                    Union[ChatMessage, RequestToSpeak, InviteToChat],
                    Field(discriminator="type"),
                ]
            ]

        model_config = ModelConfig()

        llm = ChatOpenAI(
            model=model_config.name,
            base_url=model_config.base_url,
            api_key=model_config.api_key,
        )

        parser = JsonOutputParser(pydantic_object=ModelAnswer)

        self.chain = PROMPT_TEMPLATE | llm | parser

    def invoke(self, *args, **kwargs):
        return self.chain.invoke(*args, **kwargs)
