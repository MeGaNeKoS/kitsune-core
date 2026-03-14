"""
AniList service tracker — uses the anisearch library.
"""

import logging
from typing import Optional

from devlog import log_on_start, log_on_error

from core.features import require

require("tracker")
import Anisearch
from Anisearch import Media, StudioEdge
from Anisearch.models.shared import PageResult

from core.interfaces.tracker.service import BaseServiceTracker

logger = logging.getLogger(__name__)


def _studio_fields(builder):
    return builder.name().is_animation_studio()


class AnilistTracker(BaseServiceTracker):
    _name = "anilist"

    def __init__(self, access_token: str = "", **kwargs):
        self._client = Anisearch.Anilist()
        if access_token:
            self._client.set_token(access_token)

    @log_on_start(logging.INFO, "Authenticating with AniList...")
    @log_on_error(logging.ERROR, "AniList authentication failed: {error!r}",
                  sanitize_params={"access_token"})
    def authenticate(self, **kwargs) -> bool:
        if "access_token" in kwargs:
            self._client.set_token(kwargs["access_token"])
            try:
                self._client.raw_query("query { Viewer { id } }")
                return True
            except Exception:
                return False
        return False

    @log_on_error(logging.ERROR, "Failed to fetch AniList user list: {error!r}")
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        query = """
        query ($userId: Int, $page: Int) {
            Page(page: $page, perPage: 50) {
                mediaList(userId: $userId, type: ANIME) {
                    mediaId
                    progress
                    status
                    score
                    media { id title { romaji english } episodes }
                }
            }
        }
        """
        try:
            response = self._client.raw_query(query, {"userId": int(user_id), "page": 1})
            entries = response.get("data", {}).get("Page", {}).get("mediaList", [])
            results = []
            for entry in entries:
                media = entry.get("media", {})
                title = media.get("title", {})
                results.append({
                    "id": entry.get("mediaId"),
                    "title": title.get("english") or title.get("romaji") or "",
                    "progress": entry.get("progress", 0),
                    "status": entry.get("status"),
                    "score": entry.get("score"),
                    "episodes": media.get("episodes"),
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch user list: {e}")
            return []

    @log_on_error(logging.ERROR, "Failed to fetch AniList media: {error!r}")
    def get_media(self, media_id: str) -> dict:
        result = (self._client.media(id=int(media_id))
                  .id().title().episodes().status()
                  .average_score().mean_score()
                  .season().season_year()
                  .genres().format()
                  .description().cover_image()
                  .studios(fields=_studio_fields)
                  .execute())
        return _media_to_dict(result)

    @log_on_error(logging.ERROR, "Failed to search AniList: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        result = (self._client.media(search=query)
                  .page(per_page=10)
                  .id().title().episodes().status()
                  .average_score().format()
                  .execute())
        if isinstance(result, PageResult):
            return [_media_to_dict(m) for m in result.items]
        if isinstance(result, Media):
            return [_media_to_dict(result)]
        return []

    @log_on_error(logging.ERROR, "Failed to update AniList entry: {error!r}",
                  sanitize_params={"access_token"})
    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        kwargs = {"media_id": int(media_id), "progress": progress}
        if status:
            kwargs["status"] = status
        if score is not None:
            kwargs["score"] = score
        try:
            self._client.save_media_list_entry(**kwargs)
            return True
        except Exception as e:
            logger.error(f"Failed to update entry: {e}")
            return False

    @log_on_error(logging.ERROR, "Failed to delete AniList entry: {error!r}")
    def delete_entry(self, media_id: str) -> bool:
        try:
            self._client.delete_media_list_entry(id=int(media_id))
            return True
        except Exception as e:
            logger.error(f"Failed to delete entry: {e}")
            return False


def _media_to_dict(media: Media) -> dict:
    """Convert anisearch Media dataclass to a plain dict."""
    title = media.title
    title_dict = {}
    title_display = ""
    if title:
        title_dict = {
            "romaji": title.romaji,
            "english": title.english,
            "native": title.native,
        }
        title_display = title.english or title.romaji or ""

    result = {
        "id": media.id,
        "title": title_dict,
        "title_display": title_display,
        "episodes": media.episodes,
        "status": media.status,
        "average_score": media.average_score,
        "mean_score": media.mean_score,
        "format": media.format,
        "season": media.season,
        "season_year": media.season_year,
        "genres": media.genres,
        "description": media.description,
    }

    if media.cover_image:
        result["cover_image"] = {
            "large": media.cover_image.large,
            "medium": media.cover_image.medium,
        }

    if media.studios:
        result["studios"] = [
            {"name": edge.node.name, "is_main": edge.is_main,
             "is_animation_studio": edge.node.is_animation_studio}
            for edge in media.studios
            if isinstance(edge, StudioEdge) and edge.node
        ]

    return result
