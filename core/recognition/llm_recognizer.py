"""
LLM-based anime title recognizer with tool calling.

For simple filenames, the LLM parses directly.
For ambiguous titles, it can call tools to search anime databases
and verify the match.
"""

import json
import logging

from devlog import log_on_error

from core.features import require

require("llm")

from core.interfaces.recognition import BaseRecognizer, RecognitionResult
from core.interfaces.llm import BaseLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an anime metadata parser.\n"
    "You have tools to search anime databases and parse filenames.\n"
    "Use the parse_filename tool first if the input looks like a filename.\n"
    "Use search_anime to verify or find the correct anime if unsure.\n"
    "After gathering info, return a JSON object with these fields:\n"
    '{"anime_title": "...", "episode_number": int|null, '
    '"season_number": int|null, "release_group": "..."|null, '
    '"video_resolution": "..."|null}\n'
    "Return ONLY the JSON object, no other text."
)


class LLMRecognizer(BaseRecognizer):
    _name = "llm"

    def __init__(self, llm_client: BaseLLMClient = None, **kwargs):
        if llm_client is None:
            from core.llm import get_llm_client
            llm_client = get_llm_client(**kwargs)
        self._llm = llm_client

    @log_on_error(logging.ERROR, "LLM recognition failed: {error!r}")
    def parse(self, title: str) -> RecognitionResult:
        from core.llm.agent import LLMAgent

        agent = LLMAgent(self._llm)
        result = agent.run(
            prompt=f"Parse this anime title/filename: {title}",
            system=_SYSTEM,
        )

        content = result["content"].strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"LLM returned non-JSON: {content}")
            parsed = {"anime_title": title}

        return RecognitionResult(
            anime_title=parsed.get("anime_title", ""),
            episode_number=parsed.get("episode_number"),
            season_number=parsed.get("season_number"),
            release_group=parsed.get("release_group"),
            video_resolution=parsed.get("video_resolution"),
            source=self._name,
            raw=parsed,
        )

    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        return [self.parse(t) for t in titles]
