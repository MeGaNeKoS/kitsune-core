"""
Process-based media player detection using psutil.
"""

import logging
from typing import Optional

from core.features import require

require("detection")
import psutil

from core.interfaces.detection import BaseDetector, DetectedMedia

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

_KNOWN_NAMES = {name.lower(): player
                for player, names in KNOWN_PLAYERS.items()
                for name in names}


class ProcessDetector(BaseDetector):
    _name = "process"

    def __init__(self, extra_players: Optional[dict] = None, **kwargs):
        """
        Args:
            extra_players: Additional player mappings, e.g.
                {"iina": ["iina", "IINA"]}
        """
        self._players = dict(KNOWN_PLAYERS)
        if extra_players:
            self._players.update(extra_players)
        self._known_names = {name.lower(): player
                             for player, names in self._players.items()
                             for name in names}

    def detect(self) -> list[DetectedMedia]:
        results = []
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                name = proc.info["name"]
                if not name:
                    continue
                player = self._known_names.get(name.lower())
                if player:
                    results.append(DetectedMedia(
                        player=player,
                        pid=proc.info["pid"],
                    ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return results

    def is_player_running(self, player_name: str) -> bool:
        target_names = self._players.get(player_name, [])
        if not target_names:
            return False
        target_lower = {n.lower() for n in target_names}
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"]
                if name and name.lower() in target_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
