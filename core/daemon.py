"""
Kitsune Core daemon — runs all services in one process.

Combines:
- API server (FastAPI/uvicorn)
- RSS feed polling on interval
- Service sync on interval

Usage:
    kitsune daemon start
    kitsune daemon start --config kitsune.toml

Config file (kitsune.toml):
    [daemon]
    db = "sqlite:///kitsune.db"
    api_key = ""

    [server]
    host = "0.0.0.0"
    port = 8000

    [rss]
    check_interval = 600  # seconds

    [[rss.feeds]]
    url = "https://nyaa.si/?page=rss&q=frieren+1080p"
    log = "frieren.log"

    [[rss.rules]]
    title_pattern = "Frieren"
    resolution = ["1080p"]
    release_group = ["SubsPlease"]

    [sync]
    enabled = false
    interval = 3600  # seconds
    service = "anilist"
    user_id = ""

    [llm]
    provider = "openrouter"
    model = "nvidia/nemotron-3-super-120b-a12b:free"

    [upgrade]
    enabled = false
    resolution = "FHD"
    codec = "HEVC"
    threshold = 5
"""

import asyncio
import logging
import signal
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _load_config(config_path: Optional[str] = None) -> dict:
    """Load config from TOML file, falling back to defaults."""
    config = {
        "daemon": {"db": "sqlite:///kitsune.db", "api_key": ""},
        "server": {"host": "0.0.0.0", "port": 8000},
        "rss": {"check_interval": 600, "feeds": [], "rules": []},
        "sync": {"enabled": False, "interval": 3600, "service": "anilist", "user_id": ""},
        "llm": {},
        "upgrade": {"enabled": False, "resolution": "FHD", "codec": "HEVC", "threshold": 5},
    }

    if config_path and Path(config_path).exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # Python < 3.11

        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)

        # Deep merge
        for section, values in user_config.items():
            if section in config and isinstance(config[section], dict):
                config[section].update(values)
            else:
                config[section] = values

    return config


class Daemon:
    """
    Main daemon process. Runs the API server and background tasks.
    """

    def __init__(self, config: dict):
        self._config = config
        self._running = False
        self._tasks: list[threading.Thread] = []

    def start(self):
        """Start the daemon with all configured services."""
        self._running = True

        # Handle shutdown signals
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Setup database
        from core.server.app import configure_db
        db_url = self._config["daemon"]["db"]
        configure_db(db_url)
        logger.info(f"Database: {db_url}")

        # Setup auth
        api_key = self._config["daemon"].get("api_key")
        if api_key:
            from core.server.auth import configure_auth
            configure_auth(api_key=api_key)

        # Setup LLM from config
        llm_config = self._config.get("llm", {})
        if llm_config:
            import os
            if "provider" in llm_config:
                os.environ.setdefault("LLM_PROVIDER", llm_config["provider"])
            if "model" in llm_config:
                os.environ.setdefault("LLM_MODEL", llm_config["model"])
            if "api_key" in llm_config:
                os.environ.setdefault("LLM_API_KEY", llm_config["api_key"])

        # Start background tasks
        rss_config = self._config["rss"]
        if rss_config.get("feeds"):
            t = threading.Thread(target=self._rss_loop, daemon=True, name="rss-poller")
            t.start()
            self._tasks.append(t)
            logger.info(f"RSS poller: {len(rss_config['feeds'])} feed(s), "
                        f"interval={rss_config['check_interval']}s")

        sync_config = self._config["sync"]
        if sync_config.get("enabled"):
            t = threading.Thread(target=self._sync_loop, daemon=True, name="sync")
            t.start()
            self._tasks.append(t)
            logger.info(f"Sync: {sync_config['service']}, interval={sync_config['interval']}s")

        # Start server (blocking)
        server_config = self._config["server"]
        logger.info(f"Server: {server_config['host']}:{server_config['port']}")
        self._run_server(server_config)

    def _signal_handler(self, signum, frame):
        logger.info("Shutdown signal received")
        self._running = False

    def _run_server(self, server_config: dict):
        from core.features import require
        require("server")
        from core.server.app import app
        import uvicorn

        uvicorn.run(
            app,
            host=server_config.get("host", "0.0.0.0"),
            port=server_config.get("port", 8000),
            log_level="info",
        )

    def _rss_loop(self):
        """Background RSS feed polling."""
        from core.rss.extractor import Extractor
        from core.rss.matcher import RuleMatcher
        from core.interfaces.rss import ExtractionRule, MatchRule, FeedEntry

        rss_config = self._config["rss"]
        interval = rss_config.get("check_interval", 600)

        # Build matcher from config rules
        rules = []
        for rule_cfg in rss_config.get("rules", []):
            rules.append(MatchRule(
                title_pattern=rule_cfg.get("title_pattern", ""),
                exclude_pattern=rule_cfg.get("exclude_pattern", ""),
                resolution=rule_cfg.get("resolution", []),
                release_group=rule_cfg.get("release_group", []),
                episode_range=tuple(rule_cfg["episode_range"]) if rule_cfg.get("episode_range") else None,
            ))
        matcher = RuleMatcher(rules)
        extractor = Extractor()

        logger.info("RSS poller started")
        while self._running:
            for feed_cfg in rss_config.get("feeds", []):
                url = feed_cfg.get("url", "")
                if not url:
                    continue
                try:
                    entries = extractor.extract_feed(url)
                    matched = [e for e in entries if matcher.matches(e)]
                    if matched:
                        logger.info(f"RSS {url}: {len(matched)}/{len(entries)} matched")
                        for entry in matched:
                            logger.info(f"  -> {entry.title}")
                    else:
                        logger.debug(f"RSS {url}: {len(entries)} entries, 0 matched")
                except Exception as e:
                    logger.error(f"RSS error for {url}: {e}")

            # Sleep in small increments so we can respond to shutdown
            for _ in range(int(interval)):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("RSS poller stopped")

    def _sync_loop(self):
        """Background service sync."""
        sync_config = self._config["sync"]
        interval = sync_config.get("interval", 3600)
        service_name = sync_config.get("service", "anilist")
        user_id = sync_config.get("user_id", "")

        logger.info(f"Sync loop started ({service_name})")
        while self._running:
            try:
                from core.database.sqlite import DatabaseConnection
                from core.tracker import get_local_tracker, get_service_tracker
                from core.tracker.sync import SyncManager
                from core.server.app import _get_db

                db = _get_db()
                session = db.get_session()
                try:
                    local = get_local_tracker(session)
                    service = get_service_tracker(service_name,
                                                  access_token=sync_config.get("access_token", ""))
                    sync = SyncManager()
                    result = sync.sync_from_service(local, service, user_id)
                    logger.info(f"Sync result: added={result['added']} "
                                f"updated={result['updated']} conflicts={result['conflicts']}")
                finally:
                    session.close()
            except Exception as e:
                logger.error(f"Sync error: {e}")

            for _ in range(int(interval)):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Sync loop stopped")


def start_daemon(config_path: Optional[str] = None, **overrides):
    """Entry point for the daemon."""
    config = _load_config(config_path)

    # Apply CLI overrides
    for key, value in overrides.items():
        if value is None:
            continue
        if "." in key:
            section, field = key.split(".", 1)
            config.setdefault(section, {})[field] = value
        else:
            config["daemon"][key] = value

    daemon = Daemon(config)
    daemon.start()
