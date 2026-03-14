from core.interfaces.llm import BaseLLMClient
from core.features import is_available


def get_llm_client(name: str = "openai", **kwargs) -> BaseLLMClient:
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

    available = list(clients.keys()) or ["none — install kitsune-core[llm]"]
    raise ValueError(f"LLM client {name!r} not found. Available: {', '.join(available)}")
