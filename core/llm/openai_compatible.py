import json
import logging
from typing import Optional

from devlog import log_on_start, log_on_error

from core.features import require

require("llm")
import httpx

from core.interfaces.llm import BaseLLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(BaseLLMClient):
    """
    LLM client for any OpenAI-compatible API endpoint.
    Works with OpenAI, ollama, llama.cpp, vLLM, LM Studio, etc.
    """

    _name = "openai"

    def __init__(self, base_url: str = "http://localhost:11434/v1",
                 api_key: str = "", model: str = "llama3",
                 timeout: float = 60.0, **kwargs):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @log_on_error(logging.ERROR, "LLM completion failed: {error!r}",
                  sanitize_params={"api_key"})
    def complete(self, prompt: str, system: Optional[str] = None,
                 **kwargs) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": kwargs.get("model", self._model),
            "messages": messages,
            **{k: v for k, v in kwargs.items() if k not in ("model",)},
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", self._model),
            usage=data.get("usage", {}),
        )

    @log_on_error(logging.ERROR, "LLM JSON completion failed: {error!r}",
                  sanitize_params={"api_key"})
    def complete_json(self, prompt: str, schema: Optional[dict] = None,
                      **kwargs) -> dict:
        extra = {}
        if schema:
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": schema},
            }
        else:
            extra["response_format"] = {"type": "json_object"}

        response = self.complete(prompt, **{**kwargs, **extra})
        return json.loads(response["content"])

    @log_on_error(logging.ERROR, "LLM tool call failed: {error!r}",
                  sanitize_params={"api_key"})
    def complete_with_tools(self, messages: list[dict], tools: list[dict],
                            **kwargs) -> dict:
        payload = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            "tools": tools,
            **kwargs,
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]
