import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from core.server.app import app, configure_db
from core.server.auth import configure_auth

_db_path = os.path.join(tempfile.gettempdir(), "kitsune_pytest_auth.db")


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    if os.path.exists(_db_path):
        try:
            os.remove(_db_path)
        except OSError:
            pass
    configure_db(f"sqlite:///{_db_path}")


@pytest.fixture
def authed_client():
    configure_auth(api_key="test-key")
    yield TestClient(app, raise_server_exceptions=False)
    configure_auth(api_key=None)  # reset


@pytest.fixture
def open_client():
    configure_auth(api_key=None)
    return TestClient(app, raise_server_exceptions=False)


def test_no_auth_allows_all(open_client):
    r = open_client.get("/health")
    assert r.status_code == 200

    r = open_client.get("/tracking/entries")
    assert r.status_code == 200


def test_health_always_public(authed_client):
    r = authed_client.get("/health")
    assert r.status_code == 200


def test_reject_without_key(authed_client):
    r = authed_client.get("/tracking/entries")
    assert r.status_code == 401


def test_accept_with_header(authed_client):
    r = authed_client.get("/tracking/entries", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200


def test_accept_with_query_param(authed_client):
    r = authed_client.get("/tracking/entries?api_key=test-key")
    assert r.status_code == 200


def test_reject_wrong_key(authed_client):
    r = authed_client.get("/tracking/entries", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
