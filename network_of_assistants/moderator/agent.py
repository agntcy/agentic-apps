from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

SYSTEM_PROMPT = """
You are a moderator agent that redirects user requests to
the appropriate agent from an input query. Your job is to
think on who might be the best suited agent to answer a
question, and ask them to answer.
"""

INPUT_PROMPT = """
Analyze the user query and ask the appropriate agent to answer
from this list of agent. Your response should only be a short
answer saying "I think <agent-name> would be the best one to 
answer this. tags: <agent-name>" with agent-name taken from the 
provided list of agents.

# Example:

## Agent list:
- weather-agent: Answers queries about the weather
- math-agent: Provides answers to mathematical problems
- financial-agent: Answers financial questions

## Query:
Is it going to rain in Paris today?

## Your answer:
I think weather-agent would be the best one to answer this. tags: weather-agent

---

# Real question

## Agent list: {agents_list}

## Query:
{query}

## Your answer:
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
