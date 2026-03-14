from dataclasses import dataclass, field
from typing import Any

from core.interfaces.torrent.torrent.state import FileStates


@dataclass
class TorrentFile:
    """
    Represents a file within a torrent.

    Attributes:
        name (str): The name of the file.
        _total_size (int): The total size of the file in bytes.
        _downloaded_size (int): The size of the part of the file that has been downloaded in bytes.
        download_priority (Any): The priority of downloading this file in the torrent client.
            The type and system of priority may vary between different torrent clients.
        folder_path (str): The relative path to the folder where the file will be downloaded.
            Example format: 'Torrent name/season 1'. The root path (e.g., "C:/<path>/") is stored elsewhere.
        state (FileStates): The current state of the file, e.g., downloading, completed, paused, seeding, etc.

    Note:
        The `progress` property calculates the download progress as a ratio of `downloaded_size` to `total_size`.
    """

    name: str
    download_priority: Any
    folder_path: str
    state: FileStates
    progress: float = field(init=False, default=0.0)
    _total_size: int = field(repr=True, kw_only=True)
    _downloaded_size: int = field(init=True, repr=False, default=0, kw_only=True)

    @property
    def total_size(self) -> int:
        return self._total_size

    @property
    def downloaded_size(self) -> int:
        """Get the size of the part of the file that has been downloaded."""
        return self._downloaded_size

    @downloaded_size.setter
    def downloaded_size(self, value: int):
        """Set the downloaded size and update progress."""
        self._downloaded_size = value
        self.progress = self._calculate_progress()

    def _calculate_progress(self) -> float:
        """Calculate the download progress of the file."""
        return self._downloaded_size / self.total_size if self.total_size else 0
