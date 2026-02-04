import aiohttp
import time
import json
import logging
import requests
from typing import Any, Dict, List, Optional, AsyncIterator, Union


from litellm import CustomLLM
from litellm.utils import ModelResponse

logger = logging.getLogger(__name__)

class RefreshOAuth2OpenAIProvider(CustomLLM):
    """
    LiteLLM custom provider that:
      - gets a OAuth2 client_credentials token
      - sends chat completions to OpenAI-compatible proxy
      - returns a LiteLLM ModelResponse
    """
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        base_url: str,
        appkey: Optional[str],
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.base_url = base_url

        self._cached_token: Optional[str] = None
        self._token_expiry_ts: float = 0.0

        if appkey:
            self.appkey = appkey


    # ---------- LiteLLM required methods ----------

    def completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs,
    ) -> ModelResponse:
        """
        Called by litellm.completion() / ChatLiteLLM. Must return a ModelResponse.
        """
        logger.info(f"completion called with model={model}, messages={messages}, kwargs={kwargs}")

        token = self._get_token()
        url = self.base_url

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": token,
        }

        payload = {
            "messages": messages,
            "stream": stream,
        }
        if self.appkey is not None:
            payload["user"] = json.dumps({"appkey": self.appkey})

        for k, v in kwargs.items():
            if k == "tool_choice" and v == "any":
                v = "auto"
            payload[k] = v
        
        # ---------- NON-STREAM ----------
        if not stream:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            # Convert OpenAI-style response to LiteLLM ModelResponse
            mr = ModelResponse()
            mr.model = model
            mr.created = data.get("created")
            mr.id = data.get("id")
            mr.choices = data.get("choices", [])
            mr.usage = data.get("usage", {})
            mr._hidden_params = {}  # optional
            return mr
    
        # ---------- STREAM ----------
        return self._stream(
                url=url,
                model=model,
                headers=headers,
                payload=payload,
            )
       
    async def acompletion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs,
    ) -> Union[ModelResponse, AsyncIterator[ModelResponse]]:
        """
        Called by litellm.acompletion(). If stream=True, returns an async iterator
        yielding ModelResponse chunks. Otherwise returns a single ModelResponse.
        """
        logger.info(f"acompletion called with model={model}, messages={messages}, kwargs={kwargs}")
        token = self._get_token()

        url = self.base_url
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": token,
        }

        payload = {
            "messages": messages,
            "stream": stream,
        }
        if self.appkey is not None:
            payload["user"] = json.dumps({"appkey": self.appkey})

        for k, v in kwargs.items():
            if k == "tool_choice" and v == "any":
                v = "auto"
            if v is not None:
                payload[k] = v

        # ---------- NON-STREAM ----------
        if not stream:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            mr = ModelResponse()
            mr.model = model
            mr.created = data.get("created")
            mr.id = data.get("id")
            mr.choices = data.get("choices", [])
            mr.usage = data.get("usage", {})
            mr._hidden_params = {}
            return mr

        # ---------- STREAM ----------
        return self._astream(
            url=url,
            model=model,
            headers=headers,
            payload=payload,
        )

    def _stream(
            self,
            url: str,
            model: str,
            headers: Dict[str, str],
            payload: Dict[str, Any],
    ):
        yielded_text = False
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
            r.raise_for_status()

            for line in r.iter_lines(decode_unicode=True):
                if not line or line.startswith(":"):
                    continue
                
                yielded_text = True

                if line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                else:
                    data_str = line.strip()

                if data_str == "[DONE]":
                    break

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    # metadata / prompt_filter_results / keepalive
                    continue

                first = choices[0]

                # streaming delta content (OpenAI-style)
                delta = (first.get("delta") or {}).get("content")

                # fallback for non-delta final chunk
                msg_content = (first.get("message") or {}).get("content")

                if delta:
                    yielded_text = True
                elif msg_content and not yielded_text:
                    yielded_text = True

                mr = ModelResponse()
                mr.model = model
                mr.created = event.get("created")
                mr.id = event.get("id")
                mr.choices = event.get("choices", [])
                mr.usage = event.get("usage", {})
                mr._hidden_params = {}  # optional
                yield mr
        if not yielded_text:
            raise ValueError("No generations found in stream (only metadata/usage, no text).")   
        
    async def _astream(
    self,
    url: str,
    model: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    ) -> AsyncIterator[ModelResponse]:
        """
        Async SSE stream reader yielding LiteLLM ModelResponse chunks.
        """
        yielded_text = False
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as r:
                r.raise_for_status()

                buffer = ""
                async for chunk in r.content.iter_chunked(1024):
                    # decode bytes -> str
                    buffer += chunk.decode("utf-8", errors="ignore")

                    # process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line or line.startswith(":"):
                            continue

                        if line.startswith("data:"):
                            data_str = line[len("data:"):].strip()
                        else:
                            data_str = line

                        if data_str == "[DONE]":
                            if not yielded_text:
                                raise ValueError("No generations found in stream (only metadata/usage, no text).")
                            return

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = event.get("choices") or []
                        if not choices:
                            continue

                        first = choices[0]
                        delta = (first.get("delta") or {}).get("content")
                        msg_content = (first.get("message") or {}).get("content")

                        if delta:
                            yielded_text = True
                        elif msg_content and not yielded_text:
                            yielded_text = True

                        mr = ModelResponse()
                        mr.model = model
                        mr.created = event.get("created")
                        mr.id = event.get("id")
                        mr.choices = event.get("choices", [])
                        mr.usage = event.get("usage", {})
                        mr._hidden_params = {}
                        yield mr

        if not yielded_text:
            raise ValueError("No generations found in stream (only metadata/usage, no text).")


    def _get_token(self) -> str:
        now = time.time()
        if self._cached_token and now < self._token_expiry_ts:
            return self._cached_token

        # client_credentials with HTTP Basic
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {"grant_type": "client_credentials"}
        r = requests.post(self.token_url, headers=headers, data=payload, auth=auth, timeout=30)
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data["access_token"]
        # Default to 55 min if expires_in not provided
        expires_in = int(token_data.get("expires_in", 3300))
        self._cached_token = access_token
        # Refresh a bit before expiry but never less than 30s
        self._token_expiry_ts = now + max(30, expires_in - 30)
        return access_token