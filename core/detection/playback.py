"""Playback position detection for media players.

Queries media player APIs to get current playback position, duration, and state.
Currently supports MPC-HC via its web interface.

Setup guides:
  MPC-HC: Options > Player > Web Interface > "Listen on port" (default 13579)
  mpv:    --input-ipc-server=\\.\pipe\mpvsocket (Windows)
  VLC:    Preferences > Main interfaces > Web, set password
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_mpc_playback(port: int = 13579) -> Optional[dict]:
    """Query MPC-HC's web interface for playback info.

    Returns dict with position, duration (ms), state, file, or None if unavailable.
    Requires: MPC-HC > Options > Player > Web Interface > Listen on port.
    """
    try:
        import httpx
        response = httpx.get(f"http://localhost:{port}/variables.html", timeout=2.0)
        if response.status_code != 200:
            return None

        html = response.text
        import re

        def extract(tag_id: str) -> str:
            m = re.search(rf'<p id="{tag_id}">([^<]*)</p>', html)
            return m.group(1) if m else ""

        position = extract("position")
        duration = extract("duration")
        state_str = extract("statestring")
        file_name = extract("file")

        state_map = {"Playing": "playing", "Paused": "paused", "Stopped": "stopped"}

        return {
            "position": int(position) if position else 0,
            "duration": int(duration) if duration else 0,
            "state": state_map.get(state_str, state_str.lower()),
            "file": file_name,
            "position_str": extract("positionstring"),
            "duration_str": extract("durationstring"),
        }
    except Exception as e:
        logger.debug(f"MPC-HC playback query failed: {e}")
        return None


def get_playback_info(player: str, **kwargs) -> Optional[dict]:
    """Get playback info for a detected player. Returns None if unsupported/unavailable."""
    player_lower = player.lower()

    if "mpc" in player_lower:
        port = kwargs.get("mpc_port", 13579)
        return get_mpc_playback(port)

    # Future: add mpv, VLC support here
    return None
