import logging

from devlog import log_on_start, log_on_error
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from core.interfaces.database.base import Base


class DatabaseConnection:
    @log_on_start(logging.INFO, "Initializing database connection...")
    @log_on_error(logging.ERROR, "Database connection failed: {error!r}")
    def __init__(self, db_url='sqlite:///:memory:', engine_options=None, session_options=None, scoped_session_options=None):
        engine_url = self.make_thread_safe_url(db_url)

        # Initialize options as empty dictionaries if None
        engine_options = engine_options or {}
        session_options = session_options or {}
        scoped_session_options = scoped_session_options or {}

        engine_options.setdefault('echo', False)

        connect_args = engine_options.setdefault('connect_args', {})
        connect_args.setdefault('check_same_thread', False)

        self._engine = create_engine(engine_url, **engine_options)
        session_factory = sessionmaker(bind=self._engine, **session_options)
        self._SessionLocal = scoped_session(session_factory, **scoped_session_options)

    @staticmethod
    def make_thread_safe_url(url):
        if url == 'sqlite:///:memory:' or url == 'sqlite://':
            return 'sqlite:///:memory:?mode=memory&cache=shared'
        return url

    def create_tables(self):
        # Create tables in the database for all models defined in Base
        Base.metadata.create_all(bind=self._engine)

    def get_session(self):
        # Get a new session for interacting with the database
        return self._SessionLocal()
