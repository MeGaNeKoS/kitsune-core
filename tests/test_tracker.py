from core.tracker import get_local_tracker
from core.interfaces.database.types.media import MediaType, MediaStatus


def test_add_entry(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren", MediaType.ANIME, status=MediaStatus.WATCHING, progress=3)
    assert entry["title"] == "Frieren"
    assert entry["progress"] == 3
    assert entry["status"] == "WATCHING"


def test_update_progress(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren", total_episodes=28)
    updated = tracker.update_progress(entry["id"], 10)
    assert updated["progress"] == 10


def test_auto_complete_on_total(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren", total_episodes=12, status=MediaStatus.WATCHING)
    completed = tracker.update_progress(entry["id"], 12)
    assert completed["status"] == "COMPLETED"


def test_auto_start_watching(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren", status=MediaStatus.PLANNED)
    updated = tracker.update_progress(entry["id"], 1)
    assert updated["status"] == "WATCHING"


def test_search(session):
    tracker = get_local_tracker(session)
    tracker.add_entry("Frieren: Beyond Journey's End")
    tracker.add_entry("Dandadan")
    results = tracker.search("frier")
    assert len(results) == 1
    assert results[0]["title"] == "Frieren: Beyond Journey's End"


def test_link_service(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren")
    tracker.link_service(entry["id"], "AniList", "154587")
    tracker.link_service(entry["id"], "MyAnimeList", "52991")
    mappings = tracker.get_service_mapping(entry["id"])
    assert len(mappings) == 2
    services = {m["service_name"] for m in mappings}
    assert services == {"AniList", "MyAnimeList"}


def test_unlink_service(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren")
    tracker.link_service(entry["id"], "AniList", "154587")
    assert tracker.unlink_service(entry["id"], "AniList")
    assert tracker.get_service_mapping(entry["id"]) == []


def test_delete_entry(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren")
    assert tracker.delete_entry(entry["id"])
    assert not tracker.delete_entry(entry["id"])  # already deleted


def test_list_with_filter(session):
    tracker = get_local_tracker(session)
    tracker.add_entry("Frieren", status=MediaStatus.WATCHING)
    tracker.add_entry("Dandadan", status=MediaStatus.COMPLETED)
    tracker.add_entry("One Piece", status=MediaStatus.WATCHING)

    watching = tracker.list_entries(status=MediaStatus.WATCHING)
    assert len(watching) == 2

    completed = tracker.list_entries(status=MediaStatus.COMPLETED)
    assert len(completed) == 1


def test_update_entry(session):
    tracker = get_local_tracker(session)
    entry = tracker.add_entry("Frieren")
    updated = tracker.update_entry(entry["id"], score=9.5, notes="Amazing")
    assert updated["score"] == 9.5
    assert updated["notes"] == "Amazing"
