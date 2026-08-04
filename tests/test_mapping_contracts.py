"""Core mapping ownership and provider metadata contracts."""

import pytest

from core.interfaces.database.models.Media.kitsu import KitsuMedia
from core.interfaces.database.models.Media.mal import MALMedia
from core.tracker import get_local_tracker


def test_remote_service_id_has_one_local_owner(session):
    tracker = get_local_tracker(session)
    first = tracker.add_entry("First")
    second = tracker.add_entry("Second")

    tracker.link_service(first["id"], "MyAnimeList", "123")

    with pytest.raises(ValueError, match="already linked"):
        tracker.link_service(second["id"], "MyAnimeList", "123")

    assert tracker.get_service_mapping(second["id"]) == []


def test_mal_media_from_api_preserves_metadata_collections(session):
    media = MALMedia.from_api({
        "id": 123,
        "title": "Fixture",
        "genres": [{"name": "Fantasy"}],
        "studios": [{"name": "Fixture Studio"}],
        "start_season": {"season": "fall", "year": 2024},
        "num_episodes": 12,
    }, session)
    session.commit()

    assert media.genres == ["Fantasy"]
    assert media.studios == ["Fixture Studio"]
    assert media.season == "fall"
    assert media.season_year == 2024


def test_kitsu_media_from_api_preserves_titles_and_images(session):
    media = KitsuMedia.from_api({
        "id": "456",
        "attributes": {
            "canonicalTitle": "Fixture Kitsu",
            "titles": {"en": "Fixture Kitsu"},
            "posterImage": {"large": "https://example.test/poster.jpg"},
            "coverImage": {"large": "https://example.test/cover.jpg"},
            "episodeCount": 10,
            "averageRating": "82.5",
        },
    }, session)
    session.commit()

    assert media.id == 456
    assert media.titles == {"en": "Fixture Kitsu"}
    assert media.poster_image["large"].endswith("poster.jpg")
    assert media.cover_image["large"].endswith("cover.jpg")
    assert media.episode_count == 10
    assert media.average_rating == 82.5
