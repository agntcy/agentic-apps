# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from langgraph.prebuilt import create_react_agent

# from langchain_core.tools import tool
import math

from llm import load_llm
from ioa_observe.sdk.decorators import agent, tool, workflow


@tool(name="evaluate_expression")
def evaluate_expression(query: str) -> str:
    """
    This tool evaluates mathematical expressions provided in string format.
    Input: A string containing a Python formatted mathematical expression (e.g., "3**2 + 1").
    Output: The result of evaluating the expression (e.g., "10").
    """
    try:
        # Use Python's eval to compute the expression safely
        result = eval(query, {"__builtins__": None}, {"math": math})
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


@agent(name="math-assistant", description="A math assistant agent that evaluates mathematical expressions.")
class MathAssistant:
    def __init__(self):
        # Load the LLM with the appropriate environment prefix
        self.llm = load_llm(env_prefix="MATH_ASSISTANT_LLM_")

        if self.llm is None:
            raise ValueError("LLM must be loaded before initializing the agent.")

        # Use create_react_agent to initialize the agent with tools and LLM
        self.agent = create_react_agent(
            model=self.llm,
            tools=[evaluate_expression],
            prompt="You are a helpful math assistant.",
        )

    #@workflow(name="math_workflow")
    def ask_math_question(self, query: str) -> str:
        """
        Ask a math question to the agent and get the response.
        """
        if self.agent is None:
            raise ValueError("Agent must be initialized before asking questions.")

        # Use the agent to process the query
        return self.agent.invoke({"messages": [{"role": "user", "content": query}]})["messages"][-1].content
