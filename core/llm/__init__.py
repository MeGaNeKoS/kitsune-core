from core.interfaces.llm import BaseLLMClient
from core.features import is_available


def get_llm_client(name: str = None, **kwargs) -> BaseLLMClient:
    """
    Get an LLM client. Reads config from .env if not provided.

    .env keys:
        LLM_PROVIDER=openrouter          # or: openai, gemini
        LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
        LLM_API_KEY=sk-or-...
        LLM_BASE_URL=                    # optional, override endpoint

    Or pass explicitly:
        get_llm_client("openrouter", api_key="...", model="...")
    """
    from core import env

    # Read from .env if not provided
    if name is None:
        name = env.get("LLM_PROVIDER", "openai")
    if "api_key" not in kwargs:
        # Try provider-specific key first, then generic
        provider_key = env.get(f"{name.upper()}_API_KEY")
        generic_key = env.get("LLM_API_KEY")
        if provider_key:
            kwargs["api_key"] = provider_key
        elif generic_key:
            kwargs["api_key"] = generic_key
    if "model" not in kwargs:
        env_model = env.get("LLM_MODEL")
        if env_model:
            kwargs["model"] = env_model
    if "base_url" not in kwargs:
        env_url = env.get("LLM_BASE_URL")
        if env_url:
            kwargs["base_url"] = env_url

    clients = {}
    if is_available("llm"):
        from core.llm.openai_compatible import OpenAICompatibleClient
        from core.llm.gemini import GeminiClient
        from core.llm.openrouter import OpenRouterClient
        clients[OpenAICompatibleClient.get_name()] = OpenAICompatibleClient
        clients[GeminiClient.get_name()] = GeminiClient
        clients[OpenRouterClient.get_name()] = OpenRouterClient

    client_cls = clients.get(name)
    if client_cls:
        return client_cls(**kwargs)

    available = list(clients.keys()) or ["none -- install kitsune-core[llm]"]
    raise ValueError(f"LLM client {name!r} not found. Available: {', '.join(available)}")
