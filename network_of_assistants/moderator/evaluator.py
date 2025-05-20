from langchain_openai import AzureChatOpenAI
import os
from langchain.prompts import ChatPromptTemplate
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel
from langchain_core.output_parsers import JsonOutputParser
from typing import Optional, List

from poirot.sdk.decorators import agent, workflow

SYSTEM_PROMPT = """
You are observing: a moderator agent in a chat with a user and several
specialized agents. The job of the moderator is to orchestrate these agents by
granting them the right to speak when needed until the moderator decides
the query is answered. Your job is to evaluate at each pass if the moderator 
is choosing the correct agent or not, to reach the answer for the query.
If the moderator is not granting speaking rights, you just answer "NA". 

The moderator is given a list of agents, a chat history, and an incoming
message. From this message, the moderator messages can:
- invite an agent to the chat (if not already present) with a brief summary of the ask
{{"type": "InviteToChat", "author": "moderator", "target": "<agent-id>", "summary": "<summary-of-ask>"}}
- grant an agent the right to speak by sending a RequestToSpeak message to an agent <agent-id>
{{"type": "RequestToSpeak", "author": "moderator", "target": "<agent-id>"}}
- decide the query was answered and send a RequestToSpeak to the user proxy 
{{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}
- directly answer yourself in a chat message otherwise
{{"type": "ChatMessage", "author": "moderator", "message": "<your-message>"}}

---

# Examples of moderator behavior:
Agent list:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

### Example 1: Invite an agent and ask it to speak

History: []
Query: {{"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"}}
Moderator answer:
{{"messages": [{{"type": "InviteToChat", "author": "moderator", "target": "weather-agent", "summary": "The user wants to know the weather in New York."}}, 
               {{"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}}]}}

### Example 2: Give the ball back to the user

History: [{{"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"}},
          {{"type": "InviteToChat", "author": "moderator", "target": "weather-agent", "summary": "The user wants to know the weather in New York."}},
          {{"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}}]
Query: {{"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"}},
Moderator answer:
{{"messages": [{{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}]}}

### Example 3: Answer yourself and give the ball back to the user

History: []
Query: {{"type": "ChatMessage", "author": "user-proxy", "message": "Hello!"}}
Moderator answer:
{{"messages": [{{"type": "ChatMessage", "author": "moderator", "message": "Hello user, how can I help?"}},
               {{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}}]}}

"""

INPUT_PROMPT = """
Agent list:
{agents_list}

History: {chat_history}
Query: {query_message}
Moderator answer: {moderator_answer}

Your final rating:
"""

PROMPT_TEMPLATE = ChatPromptTemplate([("system", SYSTEM_PROMPT), ("user", INPUT_PROMPT)])

@agent(name="evaluator-agent")
class EvaluatorAgent:
    def __init__(self):
        # class ModelConfig(BaseSettings):
        #     model_config = SettingsConfigDict(env_prefix="MODEL_")
        #     name: str = "gpt-4o"
        #     base_url: Optional[str] = None
        #     api_key: Optional[str] = None

        class SingleMessage(BaseModel):
            type: str
            author: str
            target: str

        class ModelAnswer(BaseModel):
            messages: List[SingleMessage]

        # model_config = ModelConfig()

        llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            # other params...
        )

        self.chain = PROMPT_TEMPLATE | llm

    @workflow(name="evaluator-agent-chatbot")
    def invoke(self, *args, **kwargs):
        return self.chain.invoke(*args, **kwargs)
