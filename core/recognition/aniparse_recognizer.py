import logging
from typing import Optional

from devlog import log_on_error

from core.features import require

require("recognition")
import aniparse

from core.interfaces.recognition import BaseRecognizer, RecognitionResult

logger = logging.getLogger(__name__)


def _extract_field(data: dict, key: str, default=None):
    """Extract first value from aniparse 2.0 list fields."""
    val = data.get(key)
    if isinstance(val, list) and val:
        return val[0] if not isinstance(val[0], dict) else val[0]
    return val if val is not None else default


class AniparseRecognizer(BaseRecognizer):
    _name = "aniparse"

    @log_on_error(logging.ERROR, "aniparse failed to parse title: {error!r}")
    def parse(self, title: str) -> RecognitionResult:
        parsed = aniparse.parse(title)
        if parsed is None:
            return RecognitionResult(
                anime_title="", source=self._name, raw={}
            )

        # Extract title and episode from series field (aniparse 2.0 format)
        anime_title = ""
        episode_number = None
        season_number = None
        series = parsed.get("series", [])
        if series:
            first_series = series[0]
            anime_title = first_series.get("title", "")
            episodes = first_series.get("episode", [])
            if episodes:
                episode_number = episodes[0].get("number")
            season_number = first_series.get("season")

        # Resolution
        video_resolution = None
        res_list = parsed.get("video_resolution", [])
        if res_list:
            res = res_list[0]
            if isinstance(res, dict):
                height = res.get("video_height", "")
                scan = res.get("scan_method", "")
                video_resolution = f"{height}{scan}" if height else None
            else:
                video_resolution = str(res)

        # Release group
        release_group = None
        groups = parsed.get("release_group", [])
        if groups:
            release_group = groups[0]

        return RecognitionResult(
            anime_title=anime_title,
            episode_number=episode_number,
            season_number=season_number,
            release_group=release_group,
            video_resolution=video_resolution,
            source=self._name,
            raw=parsed,
        )

    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        return [self.parse(t) for t in titles]
