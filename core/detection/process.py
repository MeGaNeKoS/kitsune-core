"""
Media player process detection.

Detects running media players and extracts the currently playing media title
from window titles or process metadata.
"""

import logging
import os
import platform
from typing import Optional

import psutil

logger = logging.getLogger(__name__)

# Known media players and their process names
KNOWN_PLAYERS = {
    "mpv": ["mpv", "mpv.exe"],
    "vlc": ["vlc", "vlc.exe"],
    "mpc-hc": ["mpc-hc", "mpc-hc.exe", "mpc-hc64.exe"],
    "mpc-be": ["mpc-be", "mpc-be.exe", "mpc-be64.exe"],
    "potplayer": ["PotPlayerMini", "PotPlayerMini.exe", "PotPlayerMini64.exe"],
    "kodi": ["kodi", "kodi.exe"],
}


def find_running_players() -> list[dict]:
    """Find all running media player processes."""
    results = []
    known_names = {name.lower() for names in KNOWN_PLAYERS.values() for name in names}

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = proc.info["name"]
            if name and name.lower() in known_names:
                results.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "player": _identify_player(name),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return results


def is_process_running(process_name: str) -> bool:
    """Check if a specific process is running."""
    target = os.path.basename(process_name).lower()
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _identify_player(process_name: str) -> Optional[str]:
    """Map a process name to a known player identifier."""
    lower = process_name.lower()
    for player, names in KNOWN_PLAYERS.items():
        if lower in [n.lower() for n in names]:
            return player
    return None
