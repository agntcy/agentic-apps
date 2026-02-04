# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Shim module to extend langchain-litellm's ChatLiteLLM with a custom client while keeping the same interface.
This shim uses RefreshOAuth2OpenAIProvider under the hood to handle OAuth2 token fetching and chat completions.
But leverages the existing ChatLiteLLM message formatting and integration with LangChain.
"""
import logging
from typing import Any, Dict
from common.litellm_oauth2_openai_provider import RefreshOAuth2OpenAIProvider
from config.config import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, OAUTH2_TOKEN_URL, OAUTH2_BASE_URL, OAUTH2_APPKEY

logger = logging.getLogger(__name__)

_PROVIDER = RefreshOAuth2OpenAIProvider(
    client_id=OAUTH2_CLIENT_ID,
    client_secret=OAUTH2_CLIENT_SECRET,
    appkey=OAUTH2_APPKEY,
    token_url=OAUTH2_TOKEN_URL,
    base_url=OAUTH2_BASE_URL,
)

def completion(*, model: str, messages, **kwargs) -> Dict[str, Any]:
    """
    Signature compatible with litellm.completion. Return a ModelResponse-like dict.
    ChatLiteLLM will convert LangChain messages -> OpenAI dicts (we receive that here).
    """
    logger.debug(f"litellm_shim.completion called with model={model}, messages={messages}, kwargs={kwargs}")
    passthrough = {k: v for k, v in kwargs.items() if k not in ("model", "messages")}
    return _PROVIDER.completion(model=model, messages=messages, **passthrough)

def acompletion(*, model: str, messages, **kwargs) -> Dict[str, Any]:
    """
    Asynchronous version of completion.
    """
    logger.debug(f"litellm_shim.acompletion called with model={model}, messages={messages}, kwargs={kwargs}")
    passthrough = {k: v for k, v in kwargs.items() if k not in ("model", "messages")}
    return _PROVIDER.acompletion(model=model, messages=messages, **passthrough)

