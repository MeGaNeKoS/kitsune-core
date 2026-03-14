"""
AniDB UDP API client for write operations.

The HTTP API is read-only. This UDP client provides:
- Authentication (session management)
- MyList add/update (mark episodes watched)
- Anime lookup by name

Rate limited: 1 packet every 4 seconds.
"""

import logging
import socket
import time
import threading
from typing import Optional

from devlog import log_on_start, log_on_error

logger = logging.getLogger(__name__)

_HOST = "api.anidb.net"
_PORT = 9000
_PROTO_VER = 3
_RATE_LIMIT = 4.0  # seconds between packets


class AniDBUDPClient:
    """
    Low-level AniDB UDP API client.

    Usage:
        client = AniDBUDPClient("kitsune", 1)
        client.auth("username", "password")
        client.mylist_add(aid=1, epno=5, viewed=True)
        client.logout()
    """

    def __init__(self, client_name: str = "kitsune", client_ver: int = 1,
                 timeout: float = 10.0):
        self._client_name = client_name
        self._client_ver = client_ver
        self._timeout = timeout
        self._session: Optional[str] = None
        self._sock: Optional[socket.socket] = None
        self._last_send = 0.0
        self._lock = threading.Lock()

    def _ensure_socket(self):
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(self._timeout)

    def _send(self, command: str) -> tuple[int, str]:
        """Send a command and return (code, response_body)."""
        with self._lock:
            self._ensure_socket()

            # Rate limiting
            elapsed = time.time() - self._last_send
            if elapsed < _RATE_LIMIT:
                time.sleep(_RATE_LIMIT - elapsed)

            data = command.encode("utf-8")
            self._sock.sendto(data, (_HOST, _PORT))
            self._last_send = time.time()

            try:
                response, _ = self._sock.recvfrom(1400)
            except socket.timeout:
                return 0, "TIMEOUT"

            decoded = response.decode("utf-8").strip()
            # Parse "CODE MESSAGE\nDATA"
            parts = decoded.split("\n", 1)
            header = parts[0]
            body = parts[1] if len(parts) > 1 else ""

            code = int(header[:3])
            message = header[4:]

            return code, f"{message}\n{body}" if body else message

    @log_on_start(logging.INFO, "Authenticating with AniDB UDP API...")
    @log_on_error(logging.ERROR, "AniDB UDP auth failed: {error!r}",
                  sanitize_params={"password"})
    def auth(self, username: str, password: str) -> bool:
        """Authenticate and obtain a session key."""
        cmd = (
            f"AUTH user={username}&pass={password}"
            f"&protover={_PROTO_VER}"
            f"&client={self._client_name}"
            f"&clientver={self._client_ver}"
        )
        code, msg = self._send(cmd)
        if code in (200, 201):
            # Session key is first word after the code message
            self._session = msg.split()[0]
            logger.info(f"AniDB UDP authenticated (code={code})")
            return True
        logger.error(f"AniDB UDP auth failed: {code} {msg}")
        return False

    def logout(self):
        """End the session."""
        if self._session:
            self._send(f"LOGOUT s={self._session}")
            self._session = None
        if self._sock:
            self._sock.close()
            self._sock = None

    def _authed_cmd(self, command: str) -> tuple[int, str]:
        """Send a command with session key appended."""
        if not self._session:
            raise RuntimeError("Not authenticated. Call auth() first.")
        return self._send(f"{command}&s={self._session}")

    @log_on_error(logging.ERROR, "AniDB mylist_add failed: {error!r}")
    def mylist_add(self, aid: Optional[int] = None, epno: Optional[int] = None,
                   viewed: bool = False, edit: bool = False,
                   **kwargs) -> tuple[int, str]:
        """
        Add or update a mylist entry.

        Args:
            aid: Anime ID
            epno: Episode number
            viewed: Mark as watched
            edit: If True, update existing entry
        """
        parts = ["MYLISTADD"]
        params = []
        if aid is not None:
            params.append(f"aid={aid}")
        if epno is not None:
            params.append(f"epno={epno}")
        if viewed:
            params.append("viewed=1")
            params.append(f"viewdate={int(time.time())}")
        if edit:
            params.append("edit=1")
        for k, v in kwargs.items():
            params.append(f"{k}={v}")

        cmd = f"{parts[0]} {'&'.join(params)}"
        return self._authed_cmd(cmd)

    @log_on_error(logging.ERROR, "AniDB anime lookup failed: {error!r}")
    def anime(self, aid: Optional[int] = None,
              aname: Optional[str] = None) -> tuple[int, str]:
        """Look up anime by ID or name."""
        if aid is not None:
            cmd = f"ANIME aid={aid}"
        elif aname is not None:
            cmd = f"ANIME aname={aname}"
        else:
            raise ValueError("Provide either aid or aname")
        return self._authed_cmd(cmd)

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None

    def __del__(self):
        self.logout()
