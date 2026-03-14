import os
from pathlib import Path

import pytest

from core.daemon import _load_config


def test_load_default_config():
    config = _load_config(None)
    assert config["daemon"]["db"] == "sqlite:///kitsune.db"
    assert config["server"]["port"] == 8000
    assert config["rss"]["check_interval"] == 600


def test_load_from_toml():
    config = _load_config("kitsune.example.toml")
    assert config["server"]["host"] == "0.0.0.0"
    assert len(config["rss"]["feeds"]) >= 1
    assert config["rss"]["feeds"][0]["url"] != ""
    assert len(config["rss"]["rules"]) >= 1


def test_load_missing_file():
    config = _load_config("nonexistent.toml")
    # Falls back to defaults
    assert config["daemon"]["db"] == "sqlite:///kitsune.db"


def test_config_merges_sections():
    config = _load_config("kitsune.example.toml")
    # Should have both default keys and file keys
    assert "db" in config["daemon"]
    assert "feeds" in config["rss"]
    assert "rules" in config["rss"]
