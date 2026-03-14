import threading
import time
from typing import Optional, Union

from core.interfaces.torrent.client import Client
from core.interfaces.torrent.torrent import TorrentStates, TorrentEvents, TorrentFile


class TorrentInfo:
    """
    Represents a torrent. This is a base class that can be extended for specific torrent clients.

    - anime: Media parsed from the torrent title.
    - url: list url of the torrent, including magnet link, torrent file/link, info hash.
    - log_file: list of path to where it need to write log on finished.
    - title: title of the torrent from the rss.
    - name: Name of the torrent in the client.
    - progress: Progress of the download.
    - state: Status of the torrent, in download, collection, paused, seed, etc.
    - files: List of TorrentFile objects representing the files in the torrent.
    - Save_path: the root Path where the torrent is being saved.
        'C:/Users/user/Downloads' for example.
    - Client: the client that is downloading the torrent.
    - Client_attributes: the attributes needed for the client in order to track the torrent.
    - rule_attributes: the attributes added by the rule (query rule)
    """

    def __init__(self,
                 anime: dict,
                 url: list[str],
                 file_log: str,
                 title: str):
        self.anime = anime
        self.urls = url
        self.log_file: list = [file_log]
        self.title = title

        # Download instance responsibilities
        self._fail = 0
        self._last_update = time.time()
        self._inactive = False

        # Download client responsibilities
        self.info_hash: Optional[str] = None
        self.name: Optional[str] = None
        self._states: TorrentStates = TorrentStates.UNKNOWN
        self.events: TorrentEvents = TorrentEvents(1)
        self.files: dict[str, TorrentFile] = {}
        self.save_path: Optional[str] = None

        self._progress: float = 0.0
        self._download_size: int = 0
        self._total_size: int = 0
        self._torrent_size: int = 0
        # This use as a quick-look-up for how many files downloaded. Not guarantee to be accurate.
        self._downloaded_files: int = 0
        self.client: Union[Client, None] = None

        # Any additional attribute set by client must be added here.
        self.client_attributes: dict = {}
        # Any additional attribute set by rule must be added here
        self.rule_attributes: dict = {}

        self._lock = threading.RLock()

    def __getstate__(self):
        state = self.__dict__.copy()
        state['client'] = None  # Ensure a client is None when pickled
        return state

    def remove_torrent(self) -> bool:
        """
        Remove torrent from a client.
        """

        if self.client:
            if self.client.remove_torrent(self.info_hash):
                return True
            return False
        return True

    def set_state(self, state: TorrentStates) -> None:
        """Sets a state in the torrent info."""
        with (self._lock):
            # If previously not error and new state is error
            if state & TorrentStates.ERROR and not self._states & TorrentStates.ERROR:
                self.set_event(TorrentEvents.ERROR)
            # If the current state is complete and paused, while previously not both of them, then set SEEDING_COMPLETED
            if (state & TorrentStates.SEEDING and state & TorrentStates.COMPLETED and
                    not (self._states & TorrentStates.SEEDING and self._states & TorrentStates.COMPLETED)):
                self.set_event(TorrentEvents.SEEDING_COMPLETED)

            self._states = state

    def has_state(self, state: TorrentStates) -> bool:
        """Checks if a state is present in the torrent info."""
        with self._lock:
            return (self._states & state) != 0

    @property
    def total_size(self) -> int:
        return self._total_size

    @total_size.setter
    def total_size(self, value: int) -> None:
        with self._lock:
            self._total_size = value

    @property
    def torrent_size(self) -> int:
        return self._torrent_size

    @torrent_size.setter
    def torrent_size(self, value: int) -> None:
        with self._lock:
            self._torrent_size = value

    @property
    def download_size(self) -> int:
        return self._download_size

    @download_size.setter
    def download_size(self, value: int) -> None:
        with self._lock:
            self._download_size = value
            progress = self._download_size / self.total_size if self.total_size else 0
            if self._progress != progress and progress >= 1:
                self.events |= TorrentEvents.COMPLETED
            self._progress = progress

    @property
    def fail(self) -> int:
        return self._fail

    @property
    def downloaded_files(self) -> int:
        return self._downloaded_files

    @downloaded_files.setter
    def downloaded_files(self, value: int) -> None:
        with self._lock:
            self._downloaded_files = value

    def increment_fail(self) -> None:
        with self._lock:
            self._fail += 1

    def update_last_update(self) -> None:
        with self._lock:
            self._last_update = time.time()

    @property
    def inactive(self) -> bool:
        return self._inactive

    def set_activity(self, state: bool) -> None:
        with self._lock:
            self._inactive = not state

    @property
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        with self._lock:
            if self._progress != value and value >= 1:
                self.events |= TorrentEvents.COMPLETED
            self._progress = value
            self._download_size = int(self._progress * self.total_size)

    def set_event(self, event: TorrentEvents) -> None:
        with self._lock:
            self.events |= event

    def unset_event(self, event: TorrentEvents) -> None:
        with self._lock:
            self.events &= ~event
