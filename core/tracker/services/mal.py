"""
MyAnimeList service tracker.
Uses MAL API v2 (https://api.myanimelist.net/v2).
"""

import logging
from typing import Optional

import urllib3
from devlog import log_on_start, log_on_error

from core.interfaces.tracker.service import BaseServiceTracker

logger = logging.getLogger(__name__)

_session = urllib3.PoolManager()
_BASE_URL = "https://api.myanimelist.net/v2"


class MALTracker(BaseServiceTracker):
    _name = "mal"

    def __init__(self, client_id: str = "", access_token: str = "", **kwargs):
        self._client_id = client_id
        self._access_token = access_token

    def _headers(self) -> dict:
        headers = {}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if self._client_id:
            headers["X-MAL-Client-ID"] = self._client_id
        return headers

    def _get(self, path: str, params: dict = None) -> dict:
        import json
        url = f"{_BASE_URL}{path}"
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        response = _session.request("GET", url, headers=self._headers())
        if response.status != 200:
            raise RuntimeError(f"MAL API error {response.status}: {response.data.decode()}")
        return json.loads(response.data.decode())

    def _patch(self, path: str, fields: dict) -> dict:
        import json
        from urllib.parse import urlencode
        url = f"{_BASE_URL}{path}"
        response = _session.request(
            "PATCH", url,
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded"},
            body=urlencode(fields),
        )
        if response.status not in (200, 201):
            raise RuntimeError(f"MAL API error {response.status}: {response.data.decode()}")
        return json.loads(response.data.decode())

    def _delete(self, path: str) -> bool:
        response = _session.request("DELETE", f"{_BASE_URL}{path}", headers=self._headers())
        return response.status == 200

    @log_on_error(logging.ERROR, "MAL authentication failed: {error!r}",
                  sanitize_params={"access_token", "client_id"})
    def authenticate(self, **kwargs) -> bool:
        if "access_token" in kwargs:
            self._access_token = kwargs["access_token"]
        if "client_id" in kwargs:
            self._client_id = kwargs["client_id"]
        # Verify by fetching user profile
        try:
            self._get("/users/@me", {"fields": "id"})
            return True
        except RuntimeError:
            return False

    @log_on_error(logging.ERROR, "Failed to fetch MAL user list: {error!r}")
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        params = {"limit": 100, "fields": "list_status{score,num_episodes_watched,status}"}
        if status:
            params["status"] = status
        endpoint = f"/users/{user_id}/animelist" if user_id != "@me" else "/users/@me/animelist"
        data = self._get(endpoint, params)
        results = []
        for item in data.get("data", []):
            node = item.get("node", {})
            list_status = item.get("list_status", {})
            results.append({
                "id": node.get("id"),
                "title": node.get("title"),
                "progress": list_status.get("num_episodes_watched", 0),
                "status": list_status.get("status"),
                "score": list_status.get("score"),
                "list_status": list_status,
            })
        return results

    @log_on_error(logging.ERROR, "Failed to fetch MAL media: {error!r}")
    def get_media(self, media_id: str) -> dict:
        data = self._get(f"/anime/{media_id}", {
            "fields": "id,title,main_picture,media_type,num_episodes,status,mean,synopsis,start_season,genres",
        })
        # Normalize
        pic = data.get("main_picture", {})
        if pic:
            data["coverImage"] = {"medium": pic.get("medium", ""), "large": pic.get("large", "")}
            data["cover_url"] = pic.get("medium") or pic.get("large") or ""
        data["format"] = (data.get("media_type") or "").upper()
        data["episodes"] = data.get("num_episodes")
        data["averageScore"] = int(data.get("mean", 0) * 10) if data.get("mean") else None
        season = data.get("start_season", {})
        if season:
            data["seasonYear"] = season.get("year")
            data["season"] = (season.get("season") or "").upper()
        genres = data.get("genres", [])
        if genres:
            data["genres"] = [g.get("name", "") for g in genres if isinstance(g, dict)]
        return data

    @log_on_error(logging.ERROR, "Failed to search MAL: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        data = self._get("/anime", {
            "q": query, "limit": 10,
            "fields": "id,title,main_picture,media_type,num_episodes,mean,start_season,synopsis,genres",
        })
        results = []
        for item in data.get("data", []):
            node = item.get("node", {})
            # Normalize to match AniList-like format
            entry = {
                "id": node.get("id"),
                "title": node.get("title", ""),
                "format": (node.get("media_type") or "").upper(),
                "episodes": node.get("num_episodes"),
                "averageScore": int(node.get("mean", 0) * 10) if node.get("mean") else None,
                "description": node.get("synopsis", ""),
            }
            pic = node.get("main_picture", {})
            if pic:
                entry["coverImage"] = {"medium": pic.get("medium", ""), "large": pic.get("large", "")}
                entry["cover_url"] = pic.get("medium") or pic.get("large") or ""
            season = node.get("start_season", {})
            if season:
                entry["seasonYear"] = season.get("year")
                entry["season"] = (season.get("season") or "").upper()
            genres = node.get("genres", [])
            if genres:
                entry["genres"] = [g.get("name", "") for g in genres]
            results.append(entry)
        return results

    @log_on_error(logging.ERROR, "Failed to update MAL entry: {error!r}",
                  sanitize_params={"access_token"})
    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        fields = {"num_watched_episodes": progress}
        if status:
            # Map common status names to MAL format
            status_map = {
                "WATCHING": "watching", "COMPLETED": "completed",
                "PLANNED": "plan_to_watch", "DROPPED": "dropped",
                "PAUSED": "on_hold", "REPEATING": "watching",
            }
            fields["status"] = status_map.get(status, status)
        if score is not None:
            fields["score"] = int(score)
        self._patch(f"/anime/{media_id}/my_list_status", fields)
        return True

    @log_on_error(logging.ERROR, "Failed to delete MAL entry: {error!r}")
    def delete_entry(self, media_id: str) -> bool:
        return self._delete(f"/anime/{media_id}/my_list_status")
