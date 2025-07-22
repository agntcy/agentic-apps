# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.azure import AzureAIChatCompletionClient
from azure.core.credentials import AzureKeyCredential


def load_llm(env_prefix):
    class ModelConfig(BaseSettings):
        model_config = SettingsConfigDict(env_prefix=env_prefix)
        type: str
        model: str
        base_url: Optional[str] = None
        api_key: Optional[str] = None
        request_timeout: int = 60
        max_token: int = 1024
        temperature: float = 0

    model_config = ModelConfig()

    if model_config.type == "ollama":
        model = OllamaChatCompletionClient(
            model=model_config.model,
        )
    elif model_config.type == "openai":
        model = OpenAIChatCompletionClient(
            model=model_config.model,
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            timeout=model_config.request_timeout,
            max_tokens=model_config.max_token,
            temperature=model_config.temperature,
        )
    elif model_config.type == "azure":
        model = AzureAIChatCompletionClient(
            model=model_config.model,
            credential=AzureKeyCredential(model_config.api_key),
            model_info={
                "json_output": False,
                "function_calling": False,
                "vision": False,
                "family": "unknown",
                "structured_output": False,
            },
            endpoint=model_config.base_url,
            max_tokens=model_config.max_token,
            temperature=model_config.temperature,
        )
    else:
        raise ValueError(f"Unrecognized model type '{model_config.type}'. Must be one of (azure, ollama, openai).")

    return model
