import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core.server.app import app, configure_db

_db_path = os.path.join(tempfile.gettempdir(), "kitsune_pytest_server.db")


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    if os.path.exists(_db_path):
        try:
            os.remove(_db_path)
        except OSError:
            pass
    configure_db(f"sqlite:///{_db_path}")


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_recognize(client):
    r = client.post("/recognize", json={"title": "[SubsPlease] Frieren - 05 (1080p).mkv"})
    assert r.status_code == 200
    assert r.json()["parsed"]["anime_title"] == "Frieren"


def test_tracking_crud(client):
    # Add
    r = client.post("/tracking/entries", json={"title": "Frieren", "status": "WATCHING", "progress": 3})
    assert r.status_code == 200
    mid = r.json()["id"]

    # Get
    r = client.get(f"/tracking/entries/{mid}")
    assert r.json()["title"] == "Frieren"

    # Update progress
    r = client.put(f"/tracking/entries/{mid}/progress/10")
    assert r.json()["progress"] == 10

    # Patch
    r = client.patch(f"/tracking/entries/{mid}", json={"status": "COMPLETED"})
    assert r.json()["status"] == "COMPLETED"

    # Delete
    r = client.delete(f"/tracking/entries/{mid}")
    assert r.json()["deleted"]

    # Not found
    r = client.get(f"/tracking/entries/{mid}")
    assert r.status_code == 404


def test_service_linking(client):
    r = client.post("/tracking/entries", json={"title": "Frieren"})
    mid = r.json()["id"]

    client.post(f"/tracking/entries/{mid}/services", json={"service_name": "AniList", "service_media_id": "123"})
    r = client.get(f"/tracking/entries/{mid}/services")
    assert len(r.json()) == 1

    r = client.delete(f"/tracking/entries/{mid}/services/AniList")
    assert r.json()["unlinked"]


def test_search(client):
    client.post("/tracking/entries", json={"title": "Frieren"})
    r = client.get("/tracking/search?q=frier")
    assert len(r.json()) >= 1


def test_rss_match(client):
    r = client.post("/rss/match", json={
        "title": "[SubsPlease] Frieren - 05 (1080p)",
        "title_pattern": "Frieren",
        "resolution": ["1080p"],
    })
    assert r.json()["matches"]

    r = client.post("/rss/match", json={
        "title": "[SubsPlease] Frieren - 05 (720p)",
        "title_pattern": "Frieren",
        "resolution": ["1080p"],
    })
    assert not r.json()["matches"]


def test_detection(client):
    r = client.get("/detection/players")
    assert r.status_code == 200


def test_downloader_status(client):
    r = client.get("/downloader/status")
    assert r.json()["available"]
