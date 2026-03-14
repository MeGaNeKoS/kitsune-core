import concurrent.futures
import logging
import threading
import time
import traceback
from enum import Enum
from typing import Union, TypedDict

from devlog import log_on_start, log_on_error

from core.client import get_client
from core.collection.queue import NamedQueue, QueueManager
from core.database.sqlite import DatabaseConnection
from core.error import NotFoundError, ThreadTermination
from core.interfaces.torrent.client import Client
from core.interfaces.torrent.torrent import TorrentEvents
from core.interfaces.torrent.torrent.torrent import TorrentInfo


class DownloadConfig(TypedDict, total=False):
    check_interval_second: Union[int, float]
    exception_traceback: bool
    queue: str
    concurrent_download: int
    max_fail: int
    event: dict
    client: dict


class DownloadDefault(Enum):
    REMOVAL_TIME_SECOND = 60
    MAX_FAIL = 3
    CHECK_INTERVAL_SECOND = 10
    EXCEPTION_TRACEBACK = "traceback.log"
    QUEUE = "default"
    CONCURRENT_DOWNLOAD = 3
    EVENT = {
        TorrentEvents.QUEUED: [],
        TorrentEvents.ADDED: [],
        TorrentEvents.DOWNLOADING: [],
        TorrentEvents.COMPLETED: []
    }


class Download:
    _logger = logging.getLogger(__name__)

    def __init__(self, instance_name,
                 queue_manager: QueueManager[TorrentInfo],
                 config: DownloadConfig,
                 database: DatabaseConnection):
        self._instance_name = instance_name
        self._database = database
        # Unpack config
        self._check_interval_second = config.get("check_interval_second",
                                                 DownloadDefault.CHECK_INTERVAL_SECOND.value) * 1000
        self.exception_traceback = config.get("exception_traceback",
                                              DownloadDefault.EXCEPTION_TRACEBACK.value)
        queue_name = str(config.get("queue", DownloadDefault.QUEUE.value))
        self._queue = queue_manager.create_queue(queue_name)
        self._queue.add_dependent(self)
        self._concurrent_download = config.get("concurrent_download",
                                               DownloadDefault.CONCURRENT_DOWNLOAD.value)
        self.max_fail = config.get("max_fail", DownloadDefault.MAX_FAIL.value)
        # self.event: dict[TorrentEvents, list[DownloadEvent]] = config.get("event", {})
        self._client_config = config.get("client", {})

        # Set up instance variables
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self._concurrent_download)
        # Any torrents that just got added and haven't got metadata yet
        self._get_metadata_queue: list[TorrentInfo] = []
        # All torrents that are currently downloading
        self._download_queue: list[TorrentInfo] = []
        self.last_call = 0

        self._event = threading.Event()
        # Set up Client
        self.client: Union[Client, None] = None
        self._active = False

        self.initiate_client()

    def __getstate__(self):
        state = self.__dict__.copy()
        state['client'] = None  # Ensure a client is None when pickled
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        try:
            self.initiate_client()
        except ThreadTermination:
            self._active = False
        if self.client:
            for torrent in self._download_queue:
                torrent.client = self.client

    @property
    def active(self) -> bool:
        return self._active

    @log_on_start(logging.INFO, "Initializing torrent client...")
    @log_on_error(logging.ERROR, "Client initialization failed: {error!r}")
    def initiate_client(self):
        try:
            self.client = get_client(self._client_config)
            self._active = True
        except Exception as e:
            self._active = False
            raise ThreadTermination(f"Failed to connect to the client. Please check your configuration.\n{e}")

    @log_on_start(logging.INFO, "Reconnecting to torrent client...")
    @log_on_error(logging.ERROR, "Reconnection failed: {error!r}")
    def reconnect(self) -> None:
        if not self.client:
            self.initiate_client()
            return

        self._logger.info(f"Reconnecting to {self.client.get_name()}")
        try:
            self.client.connect()
            self._active = True
        except Exception:
            self._active = False
            self._logger.error(f"Failed to connect to the client. Please check your configuration.",
                               exc_info=True,
                               stack_info=True)

    @property
    def queue(self):
        return self._queue

    @queue.setter
    def queue(self, value: NamedQueue):
        self._queue.remove_dependent(self)
        self._queue = value
        self._queue.add_dependent(self)

    @property
    def concurrent_download(self):
        return self._concurrent_download

    @concurrent_download.setter
    def concurrent_download(self, value: int):
        self._concurrent_download = value
        self.executor._max_workers = value

    @property
    def check_interval_second(self):
        return self._check_interval_second / 1000

    @check_interval_second.setter
    def check_interval_second(self, value):
        self._check_interval_second = value * 1000

    def to_dict(self):
        """
        Convert the instance variables of the class to a dictionary.
        :return: A dictionary representation of the class.
        """
        config = DownloadConfig(check_interval_second=self.check_interval_second,
                                exception_traceback=self.exception_traceback,
                                queue=self.queue.name,
                                concurrent_download=self.concurrent_download,
                                max_fail=self.max_fail,
                                event=self.event,
                                client=self.client.to_dict() if self.client else None)
        return config

    def add_torrent(self) -> bool:
        try:
            item = self.queue.dequeue()
        except IndexError:
            return False

        if not item:
            return False

        if self.client.add_torrent(item):
            self._download_queue.append(item)
            self._get_metadata_queue.append(item)
            self.executor.submit(self.update_torrent, item)
            return True
        else:
            item.increment_fail()
            if item.fail >= self.max_fail:
                self._logger.error(
                    f"Failed to add torrent {item.anime} to client after {self.max_fail} tries. Skipping...",
                    exc_info=True,
                    stack_info=True)
                return False
            self.queue.enqueue(item)
            return False

    def remove_from_download_queue(self, torrent: TorrentInfo) -> None:
        try:
            self._download_queue.remove(torrent)
            torrent.set_event(TorrentEvents.REMOVED)
            self.on_removed(torrent)
        except ValueError:
            pass

    def process_new_queue_item(self):
        for item in self.queue.loop_new_items():
            self.queue.checked(item)
            self.on_queue(item)

    def on_queue(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.QUEUED)
        for callback in self.event.get(TorrentEvents.QUEUED, []):
            callback.process(torrent)

    def on_add(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.ADDED)
        for callback in self.event.get(TorrentEvents.ADDED, []):
            callback.process(torrent)

    def on_downloading(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.DOWNLOADING)
        for callback in self.event.get(TorrentEvents.DOWNLOADING, []):
            callback.process(torrent)

    def on_complete(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.COMPLETED)
        for callback in self.event.get(TorrentEvents.COMPLETED, []):
            callback.process(torrent)

    def on_removed(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.REMOVED)
        for callback in self.event.get(TorrentEvents.REMOVED, []):
            callback.process(torrent)

    def on_error(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.ERROR)
        for callback in self.event.get(TorrentEvents.ERROR, []):
            callback.process(torrent)

    def on_seeding_completed(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.SEEDING_COMPLETED)
        for callback in self.event.get(TorrentEvents.SEEDING_COMPLETED, []):
            callback.process(torrent)

    def on_completed_files_changes(self, torrent: TorrentInfo):
        torrent.unset_event(TorrentEvents.COMPLETED_FILES_CHANGES)
        for callback in self.event.get(TorrentEvents.COMPLETED_FILES_CHANGES, []):
            callback.process(torrent)

    def update_torrent(self, torrent: TorrentInfo):
        while torrent in self._download_queue:
            try:
                self.client.update_data(torrent)
            except NotFoundError:
                self.remove_from_download_queue(torrent)
                return

            if torrent.events & TorrentEvents.QUEUED:
                self.on_queue(torrent)
            if torrent.events & TorrentEvents.ADDED:
                self.on_add(torrent)
            if torrent.events & TorrentEvents.DOWNLOADING:
                self.on_downloading(torrent)
            if torrent.events & TorrentEvents.COMPLETED:
                self.on_complete(torrent)
            if torrent.events & TorrentEvents.ERROR:
                self.on_error(torrent)
            if torrent.events & TorrentEvents.SEEDING_COMPLETED:
                self.on_seeding_completed(torrent)
            if torrent.events & TorrentEvents.COMPLETED_FILES_CHANGES:
                self.on_completed_files_changes(torrent)

            self._event.wait(self.check_interval_second)

    def check_torrent_metadata(self) -> None:
        """
        Check if the torrent has metadata. If not, add it to the queue.
        :return:
        """
        try:
            torrent = self._get_metadata_queue.pop(0)
            try:
                self.client.update_data(torrent)
            except NotFoundError:
                # remove non-existent torrents
                self.remove_from_download_queue(torrent)
                return

            if not torrent.files:
                self._get_metadata_queue.append(torrent)
                return
        except IndexError:
            return

    def step(self, force=False) -> float:
        if not self.client:
            self.initiate_client()

        elapsed_time = time.time() - self.last_call
        wait_time = self.check_interval_second - elapsed_time
        if wait_time > 0 and not force:
            return wait_time

        self.last_call = time.time()
        try:
            self.client.connect()

            for _ in range(len(self.queue)):
                if len(self._download_queue) < self._concurrent_download:
                    self.add_torrent()
                else:
                    break

        except ConnectionError:
            self._logger.error(f"Failed to connect to torrent client",
                               exc_info=True,
                               stack_info=True)
        except Exception as e:
            with open(self.exception_traceback, "a+") as f:
                f.write(f"{e}\n{traceback.format_exc()}")
        # Return the next time to call this function
        return self.last_call + self.check_interval_second - time.time()
