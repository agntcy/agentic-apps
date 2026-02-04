# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import logging
import os

from config.config import LLM_MODEL
import litellm
from langchain_litellm import ChatLiteLLM
from langchain_openai import ChatOpenAI

logger = logging.getLogger("lungo.common.llm")
import common.chat_lite_llm_shim as chat_lite_llm_shim # our drop-in client

def get_llm(streaming: bool = True):
  """
    Get the LLM provider based on the configuration using ChatLiteLLM
    
    Args:
      streaming: Enable streaming mode. Set to False when using with_structured_output()
  """
  litellm_proxy_base_url = os.getenv("LITELLM_PROXY_BASE_URL")
  litellm_proxy_api_key = os.getenv("LITELLM_PROXY_API_KEY")

  if litellm_proxy_base_url and litellm_proxy_api_key:
    logger.info(f"Using LLM via LiteLLM proxy: {litellm_proxy_base_url}")
    llm = ChatOpenAI(
      base_url=litellm_proxy_base_url,
      model=LLM_MODEL,
      api_key=litellm_proxy_api_key,
      streaming=streaming
    )
  else:
    llm = ChatLiteLLM(model=LLM_MODEL)


  if LLM_MODEL.startswith("oauth2/"):
      llm.client = chat_lite_llm_shim
  return llm