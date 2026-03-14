"""
Google Gemini LLM client.

Uses Gemini's OpenAI-compatible endpoint, so this is just a preset
on top of OpenAICompatibleClient with the right defaults.

Free API key: https://aistudio.google.com/apikey
"""

from core.llm.openai_compatible import OpenAICompatibleClient

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiClient(OpenAICompatibleClient):
    """
    Gemini client — OpenAI-compatible with Gemini defaults.

    Free tier: 15 RPM, 1500 RPD, no credit card needed.

    Usage:
        from core.llm import get_llm_client
        client = get_llm_client("gemini", api_key="your-key")
    """

    _name = "gemini"

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash",
                 base_url: str = _GEMINI_BASE_URL, **kwargs):
        super().__init__(base_url=base_url, api_key=api_key, model=model, **kwargs)
