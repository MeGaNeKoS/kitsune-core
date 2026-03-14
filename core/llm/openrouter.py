"""
OpenRouter LLM client.

Uses OpenRouter's OpenAI-compatible endpoint to access many models
(Claude, GPT, Llama, Gemini, Mistral, etc.) through one API.

Free models available. Get API key: https://openrouter.ai/keys

Usage:
    from core.llm import get_llm_client
    client = get_llm_client("openrouter", api_key="sk-or-...")
"""

from core.llm.openai_compatible import OpenAICompatibleClient

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient(OpenAICompatibleClient):
    _name = "openrouter"

    def __init__(self, api_key: str = "", model: str = "google/gemini-2.0-flash-exp:free",
                 base_url: str = _OPENROUTER_BASE_URL, **kwargs):
        super().__init__(base_url=base_url, api_key=api_key, model=model, **kwargs)
