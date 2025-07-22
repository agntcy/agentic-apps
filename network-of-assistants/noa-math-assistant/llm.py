# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

from typing import Optional
from langchain_ollama import ChatOllama
from langchain_mistralai import ChatMistralAI
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        model = ChatOllama(
            model=model_config.model,
            temperature=model_config.temperature,
        )
    elif model_config.type == "openai":
        model = ChatOpenAI(
            model=model_config.model,
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            timeout=model_config.request_timeout,
            max_completion_tokens=model_config.max_token,
            temperature=model_config.temperature,
        )
    elif model_config.type == "azure":
        model = AzureChatOpenAI(
            model=model_config.model,
            api_version="2024-08-01-preview",
            api_key=model_config.api_key,
            azure_endpoint=model_config.base_url,
            request_timeout=model_config.request_timeout,
            max_tokens=model_config.max_token,
            temperature=model_config.temperature,
        )
    elif model_config.type == "mistralai":
        model = ChatMistralAI(
            model_name=model_config.model,
            api_key=model_config.api_key,
            base_url=model_config.base_url,
            timeout=model_config.request_timeout,
            max_tokens=model_config.max_token,
            temperature=model_config.temperature,
        )
    else:
        raise ValueError(
            f"Unrecognized model type '{model_config.type}'. Must be one of (azure, mistralai, ollama, openai)."
        )

    return model
