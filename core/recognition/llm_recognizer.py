import logging

from devlog import log_on_error

from core.features import require

require("llm")

from core.interfaces.recognition import BaseRecognizer, RecognitionResult
from core.interfaces.llm import BaseLLMClient

logger = logging.getLogger(__name__)

_PARSE_PROMPT = """Parse this anime filename/title into structured JSON.
Return ONLY a JSON object with these fields:
- anime_title: string (the anime name, cleaned up)
- episode_number: integer or null
- season_number: integer or null
- release_group: string or null
- video_resolution: string or null

Title: {title}"""


class LLMRecognizer(BaseRecognizer):
    _name = "llm"

    def __init__(self, llm_client: BaseLLMClient = None, **kwargs):
        if llm_client is None:
            from core.llm import get_llm_client
            llm_client = get_llm_client(**kwargs)
        self._llm = llm_client

    @log_on_error(logging.ERROR, "LLM recognition failed: {error!r}")
    def parse(self, title: str) -> RecognitionResult:
        result = self._llm.complete_json(
            _PARSE_PROMPT.format(title=title),
            system="You are an anime metadata parser. Return only valid JSON.",
        )
        return RecognitionResult(
            anime_title=result.get("anime_title", ""),
            episode_number=result.get("episode_number"),
            season_number=result.get("season_number"),
            release_group=result.get("release_group"),
            video_resolution=result.get("video_resolution"),
            source=self._name,
            raw=result,
        )

    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        return [self.parse(t) for t in titles]
