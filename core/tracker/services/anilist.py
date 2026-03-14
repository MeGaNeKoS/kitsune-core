"""
AniList service tracker — thin adapter wrapping core.service.anilist.
"""

import logging
from typing import Optional

from devlog import log_on_start, log_on_error

from core.features import require

require("tracker")

from core.interfaces.tracker.service import BaseServiceTracker
from core.service.anilist import AnilistAuthClient, AnilistClient

logger = logging.getLogger(__name__)


class AnilistTracker(BaseServiceTracker):
    _name = "anilist"

    def __init__(self, session=None, **kwargs):
        self._session = session
        self._access_token = kwargs.get("access_token")

    @log_on_start(logging.INFO, "Authenticating with AniList...")
    @log_on_error(logging.ERROR, "AniList authentication failed: {error!r}",
                  sanitize_params={"client_secret", "code"})
    def authenticate(self, **kwargs) -> bool:
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")

        if client_id:
            AnilistAuthClient.set_client_id(client_id)
        if client_secret:
            AnilistAuthClient.set_client_secret(client_secret)

        if "access_token" in kwargs:
            self._access_token = kwargs["access_token"]
            return True

        if "code" in kwargs:
            token_data = AnilistAuthClient.fetch_token(kwargs["code"])
            self._access_token = token_data.get("access_token")
            return self._access_token is not None

        # Interactive auth
        auth_url = AnilistAuthClient.generate_auth_url(auth_code=bool(client_secret))
        thread, token_container = AnilistClient.authenticate_user(auth_url)
        thread.join()
        if token_container.token:
            self._access_token = token_container.token.get("access_token")
            return self._access_token is not None
        return False

    @log_on_error(logging.ERROR, "Failed to fetch AniList user list: {error!r}",
                  sanitize_params={"access_token"})
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        if not self._session:
            raise RuntimeError("Database session required for get_user_list")

        creds = AnilistClient.fetch_user_media_list(
            session=self._session,
            access_token=self._access_token,
            user_id=int(user_id),
        )
        return creds if isinstance(creds, list) else []

    @log_on_error(logging.ERROR, "Failed to fetch AniList media: {error!r}")
    def get_media(self, media_id: str) -> dict:
        results = AnilistClient.fetch_media_entry(media_ids=[int(media_id)])
        if results:
            return results[0] if isinstance(results, list) else results
        return {}

    @log_on_error(logging.ERROR, "Failed to search AniList: {error!r}")
    def search_media(self, query: str) -> list[dict]:
        results = AnilistClient.fetch_media_entry(search=query)
        return results if isinstance(results, list) else []

    @log_on_error(logging.ERROR, "Failed to update AniList entry: {error!r}",
                  sanitize_params={"access_token"})
    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        variables = {
            "mediaId": int(media_id),
            "progress": progress,
        }
        if status:
            variables["status"] = status
        if score is not None:
            variables["score"] = score

        query = """
        mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $score: Float) {
            SaveMediaListEntry(mediaId: $mediaId, status: $status, progress: $progress, score: $score) {
                id
                progress
                status
            }
        }
        """
        result = AnilistClient._send_graphql_request(self._access_token, query, variables)
        return "errors" not in result

    @log_on_error(logging.ERROR, "Failed to delete AniList entry: {error!r}",
                  sanitize_params={"access_token"})
    def delete_entry(self, media_id: str) -> bool:
        return AnilistClient._delete_entry(self._access_token, int(media_id))
