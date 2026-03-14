import json
import subprocess
import sys

import pytest

PYTHON = sys.executable


def _run_cli(*args, db="sqlite:///:memory:"):
    cmd = [PYTHON, "-m", "core.cli", "--db", db] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result


def test_features():
    r = _run_cli("features")
    assert r.returncode == 0
    assert "recognition" in r.stdout


def test_recognize():
    r = _run_cli("recognize", "[SubsPlease] Frieren - 05 (1080p).mkv")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["anime_title"] == "Frieren"
    assert data["episode_number"] == 5


def test_track_add_and_list():
    import tempfile, os
    db = f"sqlite:///{os.path.join(tempfile.gettempdir(), 'kitsune_cli_test.db')}"

    r = _run_cli("track", "add", "Frieren", "--status", "WATCHING", "--progress", "5", db=db)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["title"] == "Frieren"
    assert data["progress"] == 5

    r = _run_cli("track", "list", db=db)
    assert r.returncode == 0
    entries = json.loads(r.stdout)
    assert len(entries) >= 1


def test_rss_match():
    r = _run_cli("rss", "match", "[SubsPlease] Frieren (1080p)", "--pattern", "Frieren", "--resolution", "1080p")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["matches"] is True


def test_rss_match_reject():
    r = _run_cli("rss", "match", "[BadSubs] Frieren (720p)", "--pattern", "Frieren", "--resolution", "1080p")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["matches"] is False


def test_detect():
    r = _run_cli("detect")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "players" in data


def test_help():
    r = _run_cli("--help")
    assert r.returncode == 0
    assert "kitsune" in r.stdout.lower()
