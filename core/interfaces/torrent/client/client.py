import os
import platform
import subprocess
import threading
from abc import abstractmethod
from enum import Enum
from typing import Any

import psutil

from core.interfaces.torrent.client.base import BaseClient
from core.interfaces.torrent.torrent.torrent import TorrentInfo


class Client(BaseClient):
    _name = 0

    class AuthConfig(Enum):
        pass

    class CustomConfig(Enum):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._event = threading.Event()

    def sleep(self, seconds):
        self._event.wait(seconds)

    def _is_running(self):
        program_name = os.path.basename(self.program_path)
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == program_name:  # noqa
                return True
        return False

    def _start_if_not_running(self):
        if self.program_path and not self._is_running():
            if platform.system() == "Windows":
                subprocess.Popen(self.program_path)
            elif platform.system() == "Linux" or platform.system() == "Darwin":
                subprocess.Popen(["open", self.program_path])
            else:
                self._logger.error(f'Unsupported platform: {platform.system()}')

    @abstractmethod
    def _download_tick(self, torrent: TorrentInfo) -> None:
        pass

    @abstractmethod
    def _start_download(self, torrent: TorrentInfo) -> None:
        pass

    @abstractmethod
    def connect(self) -> bool:
        raise NotImplemented

    @abstractmethod
    def add_torrent(self, torrent: TorrentInfo) -> bool:
        raise NotImplemented

    @abstractmethod
    def update_data(self, torrent: TorrentInfo) -> None:
        raise NotImplemented

    @abstractmethod
    def remove_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        raise NotImplemented

    @abstractmethod
    def set_file_priority(self, torrent_hash: str, file_id: Any, priority: Any) -> bool:
        raise NotImplemented

    @abstractmethod
    def pause_torrent(self, torrent_hash: str) -> bool:
        raise NotImplemented

    @abstractmethod
    def resume_torrent(self, torrent_hash: str) -> bool:
        raise NotImplemented
