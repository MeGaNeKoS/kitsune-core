import logging

from devlog import log_on_error

from core.features import require

require("recognition")
import aniparse

from core.interfaces.recognition import BaseRecognizer, RecognitionResult

logger = logging.getLogger(__name__)


class AniparseRecognizer(BaseRecognizer):
    _name = "aniparse"

    @log_on_error(logging.ERROR, "aniparse failed to parse title: {error!r}")
    def parse(self, title: str) -> RecognitionResult:
        parsed, _ = aniparse.parse(title, False)
        return RecognitionResult(
            anime_title=parsed.get("anime_title", ""),
            episode_number=parsed.get("episode_number"),
            season_number=parsed.get("anime_season"),
            release_group=parsed.get("release_group"),
            video_resolution=parsed.get("video_resolution"),
            source=self._name,
            raw=parsed,
        )

    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        return [self.parse(t) for t in titles]
