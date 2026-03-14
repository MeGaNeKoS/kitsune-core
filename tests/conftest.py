import pytest

import core.interfaces.database.models.Media.local_media  # noqa
import core.interfaces.database.models.Media.service_mapping  # noqa

from core.database.sqlite import DatabaseConnection


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    conn = DatabaseConnection("sqlite:///:memory:")
    conn.create_tables()
    return conn


@pytest.fixture
def session(db):
    s = db.get_session()
    yield s
    s.close()
