import logging
import time
from enum import Enum
from typing import TypedDict, Union

from core.interfaces.torrent.torrent import TorrentEvents
from core.interfaces.torrent.torrent.torrent import TorrentInfo
from core.collection.queue import NamedQueue, QueueManager
from core.helper import recognition
from core.helper.file import FileCacheManager
from core.rss.rule_parser import RSSRuleParser


class RSSDefault(Enum):
    CHECK_INTERVAL_SECOND = 600
    EXCEPTION_TRACEBACK = "traceback.log"
    QUEUE = "default"


class RSSConfig(TypedDict, total=False):
    check_interval_second: Union[int, float]
    exception_traceback: bool
    queue: str
    watch_list: dict[str, str]


class RSS:
    """
    This class for manage RSS feed instance

    This thread is meant to be run in one instance. But it's possible to run multiple instances of this service.
    """
    _logger = logging.getLogger(__name__)

    def __init__(self,
                 rss_parser: RSSRuleParser,
                 queue_manager: QueueManager[TorrentInfo],
                 config: RSSConfig):
        """
        :param rss_parser:
        :param queue_dict Is the global queue_dict for use to get the correct queue name from this instance config:
        """
        self._logger.debug("RSS instance created.")

        # Unpack config
        self._check_interval_second = (config.get('check_interval_second',
                                                  RSSDefault.CHECK_INTERVAL_SECOND.value)) * 1000
        self.exception_traceback = config.get('exception_traceback',
                                              RSSDefault.EXCEPTION_TRACEBACK.value)
        queue_name = str(config.get('queue', RSSDefault.QUEUE.value))
        self._queue = queue_manager.create_queue(queue_name)
        self._queue.add_dependent(self)
        watch_list = config.get('watch_list', {})
        self.watch_list: dict[FileCacheManager, str] = {FileCacheManager(file_name): link for file_name, link in
                                                        watch_list.items()}

        self.rss_parser: RSSRuleParser = rss_parser

        # Setup internal constant
        self._next_check = 0

    @property
    def check_interval_second(self):
        return self._check_interval_second / 1000

    @check_interval_second.setter
    def check_interval_second(self, value):
        self._check_interval_second = value * 1000

    @property
    def queue(self):
        return self._queue

    @property
    def next_check(self):
        return self._next_check

    @queue.setter
    def queue(self, value: NamedQueue):
        self._queue.remove_dependent(self)
        self._queue = value
        self._queue.add_dependent(self)

    def to_dict(self):

        return RSSConfig(
            check_interval_second=self.check_interval_second,
            exception_traceback=self.exception_traceback,
            queue=self.queue.name,
            watch_list={file.get_file_path(): link for file, link in self.watch_list.items()}
        )

    def add_to_queue(self, links: dict, log_file: list):
        for title, link in links.items():
            if title in log_file:
                continue

            anime = recognition.parse(title, True)

            self.validator(anime, link, log_file, title)

    def check_feed(self):
        for file_object, link in self.watch_list.items():
            self._logger.debug(f"Checking {file_object.get_file_path()} for {link}")

            log_file = file_object.read_file()

            links = self.rss_parser.parse_feed(link, log_file)

            self.add_to_queue(links, log_file)

    def step(self):
        if time.time() >= self._next_check:
            self._logger.debug("Checking RSS feed.")
            self.check_feed()
            self._next_check = time.time() + self.check_interval_second

    def validator(self, anime, link, file_log, title) -> None:
        new_torrent = TorrentInfo(anime, link, file_log, title)
        new_torrent.set_event(TorrentEvents.QUEUED)
        self.queue.enqueue(new_torrent)
