"""
Kitsu service tracker.
Uses Kitsu API (https://kitsu.io/api/edge/) with JSON:API format.
"""

import json
import logging
from typing import Optional

import urllib3
from devlog import log_on_start, log_on_error

from core.interfaces.tracker.service import BaseServiceTracker

logger = logging.getLogger(__name__)

_session = urllib3.PoolManager()
_BASE_URL = "https://kitsu.io/api/edge"
_AUTH_URL = "https://kitsu.io/api/oauth/token"


class KitsuTracker(BaseServiceTracker):
    _name = "kitsu"

    def __init__(self, access_token: str = "", **kwargs):
        self._access_token = access_token
        self._user_id = None

    def _headers(self, content_type: bool = False) -> dict:
        headers = {"Accept": "application/vnd.api+json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        if content_type:
            headers["Content-Type"] = "application/vnd.api+json"
        return headers

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{_BASE_URL}{path}"
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        response = _session.request("GET", url, headers=self._headers())
        if response.status != 200:
            raise RuntimeError(f"Kitsu API error {response.status}: {response.data.decode()}")
        return json.loads(response.data.decode())

    def _patch(self, path: str, payload: dict) -> dict:
        url = f"{_BASE_URL}{path}"
        response = _session.request(
            "PATCH", url,
            headers=self._headers(content_type=True),
            body=json.dumps(payload),
        )
        if response.status not in (200, 201):
            raise RuntimeError(f"Kitsu API error {response.status}: {response.data.decode()}")
        return json.loads(response.data.decode())

    def _delete_request(self, path: str) -> bool:
        url = f"{_BASE_URL}{path}"
        response = _session.request("DELETE", url, headers=self._headers())
        return response.status in (200, 204)

    @log_on_start(logging.INFO, "Authenticating with Kitsu...")
    @log_on_error(logging.ERROR, "Kitsu authentication failed: {error!r}",
                  sanitize_params={"password", "access_token"})
    def authenticate(self, **kwargs) -> bool:
        if "access_token" in kwargs:
            self._access_token = kwargs["access_token"]
        elif "username" in kwargs and "password" in kwargs:
            from urllib.parse import urlencode
            body = urlencode({
                "grant_type": "password",
                "username": kwargs["username"],
                "password": kwargs["password"],
            })
            response = _session.request(
                "POST", _AUTH_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body=body,
            )
            if response.status != 200:
                return False
            data = json.loads(response.data.decode())
            self._access_token = data.get("access_token", "")

        # Verify and get user ID
        try:
            data = self._get("/users", {"filter[self]": "true"})
            users = data.get("data", [])
            if users:
                self._user_id = users[0]["id"]
                return True
        except RuntimeError:
            pass
        return False

    @log_on_error(logging.ERROR, "Failed to fetch Kitsu user list: {error!r}")
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        params = {
            "filter[user_id]": user_id or self._user_id,
            "filter[kind]": "anime",
            "page[limit]": 20,
            "include": "anime",
        }
        if status:
            status_map = {
                "WATCHING": "current", "COMPLETED": "completed",
                "PLANNED": "planned", "DROPPED": "dropped",
                "PAUSED": "on_hold",
            }
            params["filter[status]"] = status_map.get(status, status)

        data = self._get("/library-entries", params)

        # Build anime lookup from included data
        included = {item["id"]: item for item in data.get("included", [])
                    if item.get("type") == "anime"}

        results = []
        for entry in data.get("data", []):
            attrs = entry.get("attributes", {})
            anime_ref = entry.get("relationships", {}).get("anime", {}).get("data", {})
            anime_data = included.get(anime_ref.get("id"), {})
            anime_attrs = anime_data.get("attributes", {})

            results.append({
                "id": anime_ref.get("id"),
                "entry_id": entry["id"],
                "title": anime_attrs.get("canonicalTitle", ""),
                "progress": attrs.get("progress", 0),
                "status": attrs.get("status"),
                "score": attrs.get("ratingTwenty"),
            })
        return results

    @log_on_error(logging.ERROR, "Failed to fetch Kitsu media: {error!r}")
    def get_media(self, media_id: str) -> dict:
        data = self._get(f"/anime/{media_id}")
        return data.get("data", {}).get("attributes", {})

    @log_on_error(logging.ERROR, "Failed to search Kitsu: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        data = self._get("/anime", {"filter[text]": query, "page[limit]": 10})
        results = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            results.append({
                "id": item["id"],
                "title": attrs.get("canonicalTitle"),
                "episodes": attrs.get("episodeCount"),
                "status": attrs.get("status"),
            })
        return results

    @log_on_error(logging.ERROR, "Failed to update Kitsu entry: {error!r}",
                  sanitize_params={"access_token"})
    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        # media_id here is the library-entry ID
        payload = {
            "data": {
                "id": media_id,
                "type": "library-entries",
                "attributes": {
                    "progress": progress,
                },
            }
        }
        if status:
            status_map = {
                "WATCHING": "current", "COMPLETED": "completed",
                "PLANNED": "planned", "DROPPED": "dropped",
                "PAUSED": "on_hold",
            }
            payload["data"]["attributes"]["status"] = status_map.get(status, status)
        if score is not None:
            payload["data"]["attributes"]["ratingTwenty"] = int(score * 2)

        self._patch(f"/library-entries/{media_id}", payload)
        return True

    @log_on_error(logging.ERROR, "Failed to delete Kitsu entry: {error!r}")
    def delete_entry(self, media_id: str) -> bool:
        return self._delete_request(f"/library-entries/{media_id}")
