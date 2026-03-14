"""
LLM Agent — tool-calling loop for complex tasks.

Provides an agentic execution loop where the LLM can call tools
(search anime, get metadata, parse titles, etc.) to gather information
before making a decision.

Used by both LLMMatcher (should I download this?) and LLMRecognizer
(what anime is this?) for cases that need more than a simple prompt.
"""

import json
import logging
from typing import Callable, Optional

from devlog import log_on_error

from core.interfaces.llm import BaseLLMClient

logger = logging.getLogger(__name__)

# Max tool-calling rounds to prevent infinite loops
MAX_ITERATIONS = 5


# --- Tool definitions (OpenAI function-calling format) ---

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_anime",
            "description": "Search for an anime by title on a tracking service. Returns a list of matching anime with id, title, episodes, score, and status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The anime title to search for",
                    },
                    "service": {
                        "type": "string",
                        "enum": ["anilist", "mal", "kitsu"],
                        "description": "Which service to search on. Defaults to anilist.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_anime_details",
            "description": "Get detailed metadata for a specific anime by its service ID. Returns title, episodes, score, status, format, genres, studios, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_id": {
                        "type": "string",
                        "description": "The anime ID on the service",
                    },
                    "service": {
                        "type": "string",
                        "enum": ["anilist", "mal", "kitsu"],
                        "description": "Which service to query. Defaults to anilist.",
                    },
                },
                "required": ["media_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_filename",
            "description": "Parse an anime filename to extract structured metadata like title, episode number, resolution, release group.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename to parse",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get filesystem-level metadata for a file: size, extension, path, existence, timestamps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_media_info",
            "description": "Probe a media file for detailed technical metadata: video codec (HEVC/AVC/AV1), resolution, bitrate, bit depth, HDR, audio tracks (codec, channels, language), subtitle tracks, duration, container format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the media file",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_media_files",
            "description": "List all media files (mkv, mp4, etc.) in a directory with their sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path to scan",
                    },
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to include (default: mkv, mp4, avi, etc.)",
                    },
                },
                "required": ["directory"],
            },
        },
    },
]


def _build_tool_handlers() -> dict[str, Callable]:
    """Build the mapping of tool name → handler function."""

    def search_anime(query: str, service: str = "anilist") -> str:
        try:
            from core.tracker import get_service_tracker
            tracker = get_service_tracker(service)
            results = tracker.search_media(query)
            return json.dumps(results[:5], default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_anime_details(media_id: str, service: str = "anilist") -> str:
        try:
            from core.tracker import get_service_tracker
            tracker = get_service_tracker(service)
            result = tracker.get_media(media_id)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def parse_filename(filename: str) -> str:
        try:
            from core.features import is_available
            if is_available("recognition"):
                from core.recognition import get_recognizer
                recognizer = get_recognizer("aniparse")
                result = recognizer.parse(filename)
                return json.dumps(dict(result), default=str)
            return json.dumps({"error": "recognition feature not installed"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_file_info(path: str) -> str:
        try:
            from core.media.filesystem import get_file_info as _get_file_info
            return json.dumps(_get_file_info(path), default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_media_info(path: str) -> str:
        try:
            from core.media.probe import get_media_info as _get_media_info
            return json.dumps(_get_media_info(path), default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_media_files(directory: str, extensions: list[str] = None) -> str:
        try:
            from core.media.filesystem import list_media_files as _list_media_files
            results = _list_media_files(directory, extensions)
            return json.dumps(results, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    return {
        "search_anime": search_anime,
        "get_anime_details": get_anime_details,
        "parse_filename": parse_filename,
        "get_file_info": get_file_info,
        "get_media_info": get_media_info,
        "list_media_files": list_media_files,
    }


class LLMAgent:
    """
    Agentic LLM executor with tool-calling loop.

    Sends a prompt to the LLM with available tools. If the LLM calls a tool,
    executes it, feeds the result back, and loops until the LLM produces a
    final text response (or hits MAX_ITERATIONS).

    Usage:
        agent = LLMAgent(llm_client)
        result = agent.run(
            system="You evaluate download rules...",
            prompt="Should I download '[SubsPlease] Frieren - 05 (1080p)'?",
        )
        # result = {"content": "yes", "tool_calls_made": [...]}
    """

    def __init__(self, llm_client: BaseLLMClient,
                 tools: list[dict] = None,
                 tool_handlers: dict[str, Callable] = None):
        self._llm = llm_client
        self._tools = tools or TOOL_DEFINITIONS
        self._handlers = tool_handlers or _build_tool_handlers()

    @log_on_error(logging.ERROR, "LLM agent execution failed: {error!r}")
    def run(self, prompt: str, system: Optional[str] = None,
            **kwargs) -> dict:
        """
        Execute the agent loop.

        Returns:
            {
                "content": str,       # final LLM text response
                "tool_calls_made": [  # log of all tool calls
                    {"tool": "search_anime", "args": {...}, "result": "..."},
                    ...
                ]
            }
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        tool_calls_made = []

        for iteration in range(MAX_ITERATIONS):
            response = self._llm.complete_with_tools(messages, self._tools, **kwargs)

            # If no tool calls, we have the final answer
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                return {
                    "content": response.get("content", ""),
                    "tool_calls_made": tool_calls_made,
                }

            # Add assistant message with tool calls to history
            messages.append(response)

            # Execute each tool call
            for tool_call in tool_calls:
                func = tool_call["function"]
                tool_name = func["name"]
                try:
                    tool_args = json.loads(func["arguments"])
                except (json.JSONDecodeError, KeyError):
                    tool_args = {}

                handler = self._handlers.get(tool_name)
                if handler:
                    tool_result = handler(**tool_args)
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                tool_calls_made.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                })

                # Feed tool result back to LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": tool_result,
                })

        # Hit max iterations
        logger.warning(f"LLM agent hit max iterations ({MAX_ITERATIONS})")
        return {
            "content": "",
            "tool_calls_made": tool_calls_made,
        }
