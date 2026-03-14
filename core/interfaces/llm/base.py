from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class LLMResponse(TypedDict, total=False):
    content: str
    model: str
    usage: dict  # token counts


class BaseLLMClient(ABC):
    """
    Abstract interface for LLM endpoint integration.
    Endpoint-only — no local model spawning.
    """

    _name: str = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls._name is None:
            raise NotImplementedError("Subclasses must define a '_name' attribute")

    @classmethod
    def get_name(cls) -> str:
        return cls._name

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None,
                 **kwargs) -> LLMResponse:
        """Send a completion request to the LLM endpoint."""
        ...

    @abstractmethod
    def complete_json(self, prompt: str, schema: Optional[dict] = None,
                      **kwargs) -> dict:
        """
        Send a completion request expecting JSON output.
        Optionally provide a JSON schema for structured output.
        """
        ...

    @abstractmethod
    def complete_with_tools(self, messages: list[dict], tools: list[dict],
                            **kwargs) -> dict:
        """
        Send a completion request with tool/function definitions.
        Returns the raw response including any tool_calls.

        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            tools: OpenAI-format tool definitions
            **kwargs: Extra params (model, temperature, etc.)

        Returns:
            The assistant message dict, which may contain:
            - "content": text response (if no tool call)
            - "tool_calls": list of tool calls to execute
        """
        ...
