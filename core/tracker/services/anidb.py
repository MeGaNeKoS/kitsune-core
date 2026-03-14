"""
AniDB service tracker.
Uses AniDB HTTP API (http://api.anidb.net:9001/httpapi).

Note: The HTTP API is read-only. Write operations (update/delete) are not
supported via HTTP and would require the UDP API. This implementation
provides search and metadata retrieval only.
"""

import logging
from typing import Optional
from xml.etree import ElementTree

import urllib3
from devlog import log_on_error

from core.interfaces.tracker.service import BaseServiceTracker

logger = logging.getLogger(__name__)

_session = urllib3.PoolManager()
_BASE_URL = "http://api.anidb.net:9001/httpapi"


class AniDBTracker(BaseServiceTracker):
    _name = "anidb"

    def __init__(self, client: str = "kitsune", clientver: int = 1,
                 username: str = "", password: str = "", **kwargs):
        self._client = client
        self._clientver = clientver
        self._username = username
        self._password = password

    def _base_params(self) -> dict:
        params = {
            "client": self._client,
            "clientver": str(self._clientver),
            "protover": "1",
        }
        if self._username:
            params["user"] = self._username
        if self._password:
            params["pass"] = self._password
        return params

    def _get(self, request_type: str, extra_params: dict = None) -> ElementTree.Element:
        from urllib.parse import urlencode
        params = {**self._base_params(), "request": request_type}
        if extra_params:
            params.update(extra_params)
        url = f"{_BASE_URL}?{urlencode(params)}"
        response = _session.request("GET", url)
        if response.status != 200:
            raise RuntimeError(f"AniDB API error {response.status}")
        return ElementTree.fromstring(response.data)

    @log_on_error(logging.ERROR, "AniDB authentication failed: {error!r}",
                  sanitize_params={"password"})
    def authenticate(self, **kwargs) -> bool:
        if "username" in kwargs:
            self._username = kwargs["username"]
        if "password" in kwargs:
            self._password = kwargs["password"]
        if "client" in kwargs:
            self._client = kwargs["client"]
        return bool(self._username and self._client)

    @log_on_error(logging.ERROR, "Failed to fetch AniDB user list: {error!r}")
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        # HTTP API only supports mylistsummary (counts, not full list)
        logger.warning("AniDB HTTP API provides limited mylist data. "
                       "Full list requires UDP API or XML export.")
        return []

    @log_on_error(logging.ERROR, "Failed to fetch AniDB media: {error!r}")
    def get_media(self, media_id: str) -> dict:
        root = self._get("anime", {"aid": media_id})
        if root.tag == "error":
            raise RuntimeError(f"AniDB error: {root.text}")

        # Parse XML response
        result = {"id": media_id}
        for title_elem in root.findall(".//title"):
            lang = title_elem.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            title_type = title_elem.get("type", "")
            if title_type == "main" or (title_type == "official" and lang == "en"):
                result.setdefault("title", title_elem.text)
            if title_type == "main":
                result["title_main"] = title_elem.text
            if lang == "en" and title_type == "official":
                result["title_english"] = title_elem.text

        episodes_elem = root.find("episodecount")
        if episodes_elem is not None and episodes_elem.text:
            result["episodes"] = int(episodes_elem.text)

        return result

    @log_on_error(logging.ERROR, "Failed to search AniDB: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        # AniDB HTTP API doesn't have a search endpoint.
        # The recommended approach is using the daily anime-titles dump.
        logger.warning("AniDB HTTP API does not support search. "
                       "Use anime-titles dump for local search.")
        return []

    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        logger.warning("AniDB HTTP API is read-only. "
                       "Write operations require the UDP API.")
        return False

    def delete_entry(self, media_id: str) -> bool:
        logger.warning("AniDB HTTP API is read-only. "
                       "Write operations require the UDP API.")
        return False
