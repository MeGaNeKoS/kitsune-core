"""
AniList service tracker — uses the anisearch library.
"""

import logging
from typing import Optional

from devlog import log_on_start, log_on_error

from core.features import require

require("tracker")
import Anisearch

from core.interfaces.tracker.service import BaseServiceTracker

logger = logging.getLogger(__name__)


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
            # Verify by fetching viewer
            try:
                self._client.raw_query("query { Viewer { id } }")
                return True
            except Exception:
                return False
        return False

    @log_on_error(logging.ERROR, "Failed to fetch AniList user list: {error!r}")
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        try:
            result = (self._client.media(id_in=[])
                      .page(per_page=50)
                      .id().title().episodes().status().average_score()
                      .execute())
            # For user-specific lists, use raw query
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
                  .studios()
                  .execute())
        return _media_to_dict(result)

    @log_on_error(logging.ERROR, "Failed to search AniList: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        result = (self._client.media(search=query)
                  .page(per_page=10)
                  .id().title().episodes().status()
                  .average_score().format()
                  .execute())
        # PageResult has .items list
        if hasattr(result, 'items'):
            return [_media_to_dict(m) for m in result.items]
        # Single Media result
        if hasattr(result, 'id'):
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


def _media_to_dict(media) -> dict:
    """Convert anisearch Media object to a plain dict."""
    result = {"id": getattr(media, 'id', None)}

    title = getattr(media, 'title', None)
    if title:
        result["title"] = {
            "romaji": getattr(title, 'romaji', None),
            "english": getattr(title, 'english', None),
            "native": getattr(title, 'native', None),
        }
        result["title_display"] = (getattr(title, 'english', None)
                                   or getattr(title, 'romaji', None)
                                   or "")
    else:
        result["title"] = {}
        result["title_display"] = ""

    result["episodes"] = getattr(media, 'episodes', None)
    result["status"] = getattr(media, 'status', None)
    result["average_score"] = getattr(media, 'average_score', None)
    result["mean_score"] = getattr(media, 'mean_score', None)
    result["format"] = getattr(media, 'format', None)
    result["season"] = getattr(media, 'season', None)
    result["season_year"] = getattr(media, 'season_year', None)
    result["genres"] = getattr(media, 'genres', None)
    result["description"] = getattr(media, 'description', None)

    cover = getattr(media, 'cover_image', None)
    if cover:
        result["cover_image"] = {
            "large": getattr(cover, 'large', None),
            "medium": getattr(cover, 'medium', None),
        }

    studios = getattr(media, 'studios', None)
    if studios and hasattr(studios, 'nodes'):
        result["studios"] = [getattr(s, 'name', '') for s in studios.nodes]

    return result
