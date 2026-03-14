# LLM

The LLM module provides integration with LLM endpoints for intelligent title parsing, complex rule evaluation, and future AI-powered features.

**Important:** This module is endpoint-only. It calls external LLM APIs — it does not spawn or host models locally.

## Architecture

```
┌───────────────┐
│ BaseLLMClient │ (core/interfaces/llm/base.py)
└──────┬────────┘
       │
  ┌────┴──────────────┐
  │                   │
  ▼                   ▼
OpenAI-Compatible   (future providers)
```

## Interface

**File:** `core/interfaces/llm/base.py` → `BaseLLMClient`

### Methods

| Method | Description |
|--------|-------------|
| `complete(prompt, system?)` | Send a text completion request |
| `complete_json(prompt, schema?)` | Request JSON-structured output |

### LLMResponse

```python
class LLMResponse(TypedDict, total=False):
    content: str    # the generated text
    model: str      # model that produced the response
    usage: dict     # token usage (prompt_tokens, completion_tokens, total_tokens)
```

## Implementations

### OpenAI-Compatible Client

**Extra:** `llm`

Uses [httpx](https://pypi.org/project/httpx/) to call any OpenAI-compatible API endpoint. This covers:

- OpenAI API
- Local servers (llama.cpp, ollama, vLLM, LM Studio)
- Azure OpenAI
- Any service implementing the OpenAI chat completions format

**Configuration:**
```python
from core.llm import get_llm_client

client = get_llm_client("openai",
    base_url="http://localhost:11434/v1",  # ollama
    api_key="not-needed",
    model="llama3"
)
```

## Use Cases

### Title Recognition

When aniparse fails on non-standard filenames, the LLM recognizer falls back to an LLM:

```python
prompt = """Parse this anime filename into JSON:
"Sousou no Frieren S01E05 The Hero's Party Sets Out 1080p WEB-DL"

Return: {"anime_title": "...", "episode_number": ..., "season_number": ...}"""

result = client.complete_json(prompt)
```

### Complex Rule Evaluation (Future)

Users can define rules in natural language:

```
"If this anime is from studio MAPPA and has score > 8, download in 1080p"
"Skip any release from [BadSubs]"
```

The LLM evaluates these rules against anime metadata.

### Browser Extension Relay

The LLM endpoint is also exposed via the [Server](Server.md) API, allowing browser extensions to use it directly without needing the full kitsune-core stack. This enables standalone extension operation where the extension sends streaming page titles to the LLM for recognition.

## Implementing a New Provider

```python
from core.interfaces.llm import BaseLLMClient, LLMResponse

class AnthropicClient(BaseLLMClient):
    _name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model

    def complete(self, prompt, system=None, **kwargs) -> LLMResponse:
        # Call Anthropic Messages API
        ...

    def complete_json(self, prompt, schema=None, **kwargs) -> dict:
        # Call with JSON mode
        ...
```
