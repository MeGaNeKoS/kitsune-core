"""
Tests for service tracker implementations.
Tests structure and factory — live API calls are skipped unless credentials are set.
"""

import os
import pytest

from core.tracker import get_service_tracker


class TestTrackerFactory:

    def test_get_mal(self):
        tracker = get_service_tracker("mal", client_id="test")
        assert tracker.get_name() == "mal"

    def test_get_kitsu(self):
        tracker = get_service_tracker("kitsu")
        assert tracker.get_name() == "kitsu"

    def test_get_anidb(self):
        tracker = get_service_tracker("anidb")
        assert tracker.get_name() == "anidb"

    def test_get_anilist(self):
        from core.features import is_available
        if not is_available("tracker"):
            pytest.skip("tracker not installed")
        tracker = get_service_tracker("anilist")
        assert tracker.get_name() == "anilist"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_service_tracker("nonexistent")


class TestMALTracker:

    def test_init(self):
        tracker = get_service_tracker("mal", client_id="test-id", access_token="test-token")
        assert tracker._client_id == "test-id"
        assert tracker._access_token == "test-token"

    def test_headers(self):
        tracker = get_service_tracker("mal", client_id="cid", access_token="tok")
        headers = tracker._headers()
        assert headers["Authorization"] == "Bearer tok"
        assert headers["X-MAL-Client-ID"] == "cid"


class TestKitsuTracker:

    def test_init(self):
        tracker = get_service_tracker("kitsu", access_token="test-token")
        assert tracker._access_token == "test-token"

    def test_headers(self):
        tracker = get_service_tracker("kitsu", access_token="tok")
        headers = tracker._headers()
        assert headers["Authorization"] == "Bearer tok"
        assert headers["Accept"] == "application/vnd.api+json"


class TestAniDBTracker:

    def test_init(self):
        tracker = get_service_tracker("anidb", client="kitsune", clientver=1, username="user")
        assert tracker._client == "kitsune"
        assert tracker._username == "user"

    def test_authenticate_no_password(self):
        tracker = get_service_tracker("anidb", username="user")
        assert tracker.authenticate() is True  # returns True if username + client set

    def test_delete_not_supported(self):
        tracker = get_service_tracker("anidb")
        assert tracker.delete_entry("123") is False


@pytest.mark.skipif(
    not os.environ.get("ANILIST_TOKEN"),
    reason="Set ANILIST_TOKEN env var to run live AniList tests"
)
class TestAnilistLive:

    def test_search(self):
        tracker = get_service_tracker("anilist")
        results = tracker.search_media("Frieren")
        assert len(results) > 0
        assert results[0]["title_display"] != ""

    def test_get_media(self):
        tracker = get_service_tracker("anilist")
        media = tracker.get_media("154587")
        assert media["title_display"] == "Frieren: Beyond Journey\u2019s End"
        assert media["average_score"] > 0
