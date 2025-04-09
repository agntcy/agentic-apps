from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

SYSTEM_PROMPT = """
You are a moderator agent in a chat with a user and several
specialized agents. Your job is to orchestrate these agents by
granting them the right to speak when needed until you decide
the query is answered.
"""

INPUT_PROMPT = """
You will be given a list of agents, a chat history, and an incoming
message. From this message, you can either:
- grant an agent the right to speak by sending a RequestToSpeak message to an agent <agent-id>
{"type": "RequestToSpeak", "author": "moderator", "target": "<agent-id>"}
- decide the query was answered and send a RequestToSpeak to the user proxy 
{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}

---

# Examples:

Agent list:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

### Example 1:

History: []
Query: {"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"}
Your answer:
{"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}

### Example 2:

History: [{"type": "ChatMessage", "author": "user-proxy", "message": "What is the weather like in New York?"},
          {"type": "RequestToSpeak", "author": "moderator", "target": "weather-agent"}]
Query: {"type": "ChatMessage", "author": "weather-agent", "message": "It is currently sunny and 95F in New York"},
Your answer:
{"type": "RequestToSpeak", "author": "moderator", "target": "user-proxy"}

---

# REAL QUESTION

Agent list:
{agents_list}

History: {chat_history}
Query: {query_message}
Your answer:
"""

PROMPT_TEMPLATE = ChatPromptTemplate([("system", SYSTEM_PROMPT), ("user", INPUT_PROMPT)])


class ModeratorAgent:
    def __init__(self):
        class ModelConfig(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="MODEL_")
            name: str = "gpt-4o"
            base_url: Optional[str] = None
            api_key: Optional[str] = None

        model_config = ModelConfig()

        llm = ChatOpenAI(
            model=model_config.name,
            base_url=model_config.base_url,
            api_key=model_config.api_key,
        )

        self.chain = PROMPT_TEMPLATE | llm

    def invoke(self, *args, **kwargs):
        return self.chain.invoke(*args, **kwargs)
