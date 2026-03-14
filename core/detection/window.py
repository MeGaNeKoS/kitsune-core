"""
Window title-based media player detection using Win32 API via ctypes.
No extra dependencies — uses only the Python standard library.
Windows-only.
"""

import ctypes
import logging
import platform
from typing import Optional

from core.interfaces.detection import BaseDetector, DetectedMedia

logger = logging.getLogger(__name__)

# Known media players and their process names (lowercase)
KNOWN_PLAYERS = {
    "mpv": ["mpv", "mpv.exe"],
    "vlc": ["vlc", "vlc.exe"],
    "mpc-hc": ["mpc-hc", "mpc-hc.exe", "mpc-hc64.exe"],
    "mpc-be": ["mpc-be", "mpc-be.exe", "mpc-be64.exe"],
    "potplayer": ["potplayermini", "potplayermini.exe", "potplayermini64.exe"],
    "kodi": ["kodi", "kodi.exe"],
}


def _get_windows_with_pids() -> list[dict]:
    """Enumerate all visible windows with their titles and PIDs using Win32 API."""
    if platform.system() != "Windows":
        logger.warning("Window title detection is only supported on Windows")
        return []

    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    GetWindowTextW = user32.GetWindowTextW
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    IsWindowVisible = user32.IsWindowVisible

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    windows = []

    def callback(hwnd, _):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buff, length + 1)

                pid = ctypes.c_ulong()
                GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                windows.append({
                    "title": buff.value,
                    "pid": pid.value,
                })
        return True

    EnumWindows(WNDENUMPROC(callback), 0)
    return windows


def _pid_to_process_name(pid: int) -> Optional[str]:
    """Get process name from PID using Win32 API."""
    if platform.system() != "Windows":
        return None

    try:
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010

        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return None

        try:
            psapi = ctypes.windll.psapi
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleBaseNameW(handle, None, buf, 260):
                return buf.value
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        pass
    return None


class WindowTitleDetector(BaseDetector):
    """
    Detects media players by scanning window titles.
    Extracts the currently playing media title from the window title.
    Windows-only, uses ctypes (no extra dependencies).
    """

    _name = "window_title"

    def __init__(self, extra_players: Optional[dict] = None, **kwargs):
        self._players = dict(KNOWN_PLAYERS)
        if extra_players:
            self._players.update(extra_players)

        self._known_names = {name.lower(): player
                             for player, names in self._players.items()
                             for name in names}

    def detect(self) -> list[DetectedMedia]:
        if platform.system() != "Windows":
            return []

        windows = _get_windows_with_pids()
        results = []

        for window in windows:
            pid = window["pid"]
            title = window["title"]

            # Match by process name
            proc_name = _pid_to_process_name(pid)
            if not proc_name:
                continue

            player = self._known_names.get(proc_name.lower())
            if player:
                # Extract media title from window title
                media_title = self._extract_media_title(title, player)
                results.append(DetectedMedia(
                    player=player,
                    pid=pid,
                    title=media_title,
                ))

        return results

    def is_player_running(self, player_name: str) -> bool:
        return any(d["player"] == player_name for d in self.detect())

    @staticmethod
    def _extract_media_title(window_title: str, player: str) -> Optional[str]:
        """
        Extract the media title from a window title.
        Most players use format: "filename - PlayerName" or "PlayerName - filename"
        """
        if not window_title:
            return None

        # Common patterns:
        # mpv: "filename.mkv - mpv"
        # VLC: "filename.mkv - VLC media player"
        # MPC-HC: "filename.mkv - Media Player Classic Home Cinema"
        # PotPlayer: "filename.mkv - PotPlayer"
        player_indicators = {
            "mpv": [" - mpv"],
            "vlc": [" - VLC media player", " - VLC"],
            "mpc-hc": [" - Media Player Classic Home Cinema", " - MPC-HC"],
            "mpc-be": [" - Media Player Classic Black Edition", " - MPC-BE"],
            "potplayer": [" - PotPlayer"],
            "kodi": [],  # Kodi uses different title format
        }

        indicators = player_indicators.get(player, [])
        for indicator in indicators:
            if indicator in window_title:
                title = window_title.split(indicator)[0].strip()
                return title if title else None

        return window_title
