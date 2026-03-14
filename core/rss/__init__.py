"""
RSS feed monitor.

Pipeline:
    RSS Feed → Extractor (find download links)
             → Matcher (should I download this?)
             → Recognizer (parse the anime title)
             → Queue (ready for downloader)
"""

import logging
import time
from enum import Enum
from typing import TypedDict, Union, Optional

from core.interfaces.rss.extractor import BaseExtractor, FeedEntry
from core.interfaces.rss.matcher import BaseMatcher
from core.interfaces.torrent.torrent import TorrentEvents
from core.interfaces.torrent.torrent.torrent import TorrentInfo
from core.collection.queue import NamedQueue, QueueManager
from core.helper.file import FileCacheManager


class RSSDefault(Enum):
    CHECK_INTERVAL_SECOND = 600
    QUEUE = "default"


class RSSConfig(TypedDict, total=False):
    check_interval_second: Union[int, float]
    queue: str
    watch_list: dict[str, str]  # {log_file_path: feed_url}


class RSS:
    """
    Monitors RSS feeds and enqueues matching entries for download.

    Pipeline per entry:
        1. Extractor finds download links (magnet, torrent, info_hash)
        2. Matcher decides if this entry should be downloaded
        3. Recognizer parses the anime title from the entry
        4. Entry is enqueued for the downloader

    Usage:
        from core.rss import RSS
        from core.rss.extractor import Extractor
        from core.rss.matcher import RuleMatcher
        from core.interfaces.rss import ExtractionRule, MatchRule

        extractor = Extractor([
            ExtractionRule(source="nyaa.si", magnet="link"),
        ])

        matcher = RuleMatcher([
            MatchRule(title_pattern=r"Frieren", resolution=["1080p"]),
        ])

        rss = RSS(
            extractor=extractor,
            matcher=matcher,
            queue_manager=queue_manager,
            config={"watch_list": {"frieren.log": "https://nyaa.si/?page=rss&q=frieren"}},
        )

        rss.step()  # checks feeds if interval has elapsed
    """

    _logger = logging.getLogger(__name__)

    def __init__(self,
                 extractor: BaseExtractor,
                 matcher: BaseMatcher,
                 queue_manager: QueueManager[TorrentInfo],
                 config: RSSConfig,
                 recognizer=None):
        self._extractor = extractor
        self._matcher = matcher
        self._recognizer = recognizer

        # Config
        self._check_interval_second = config.get(
            'check_interval_second', RSSDefault.CHECK_INTERVAL_SECOND.value
        )
        queue_name = str(config.get('queue', RSSDefault.QUEUE.value))
        self._queue = queue_manager.create_queue(queue_name)
        self._queue.add_dependent(self)

        # Watch list: {FileCacheManager: feed_url}
        watch_list = config.get('watch_list', {})
        self.watch_list: dict[FileCacheManager, str] = {
            FileCacheManager(log_path): url
            for log_path, url in watch_list.items()
        }

        self._next_check = 0.0

    @property
    def check_interval_second(self) -> float:
        return self._check_interval_second

    @check_interval_second.setter
    def check_interval_second(self, value: float):
        self._check_interval_second = value

    @property
    def queue(self) -> NamedQueue:
        return self._queue

    @queue.setter
    def queue(self, value: NamedQueue):
        self._queue.remove_dependent(self)
        self._queue = value
        self._queue.add_dependent(self)

    @property
    def next_check(self) -> float:
        return self._next_check

    def to_dict(self) -> RSSConfig:
        return RSSConfig(
            check_interval_second=self.check_interval_second,
            queue=self.queue.name,
            watch_list={cache.get_file_path(): url for cache, url in self.watch_list.items()},
        )

    def step(self):
        """Check feeds if the interval has elapsed."""
        if time.time() >= self._next_check:
            self._logger.debug("Checking RSS feeds.")
            self.check_feeds()
            self._next_check = time.time() + self.check_interval_second

    def check_feeds(self):
        """Check all watched feeds."""
        for cache, url in self.watch_list.items():
            self._logger.debug(f"Checking {url}")
            try:
                seen = cache.read_file()
            except FileNotFoundError:
                seen = []

            entries = self._extractor.extract_feed(url, seen)
            for entry in entries:
                self._process_entry(entry, cache)

    def _process_entry(self, entry: FeedEntry, cache: FileCacheManager):
        """Run an entry through the matcher → recognizer → queue pipeline."""
        # Step 1: Should we download this?
        if not self._matcher.matches(entry):
            self._logger.debug(f"Skipped (matcher rejected): {entry.title}")
            return

        # Step 2: Recognize the anime title
        parsed = {}
        if self._recognizer:
            try:
                parsed = dict(self._recognizer.parse(entry.title))
            except Exception as e:
                self._logger.warning(f"Recognition failed for '{entry.title}': {e}")

        # Step 3: Build URLs list
        urls = entry.magnet_links + entry.torrent_links

        if not urls and not entry.info_hashes:
            self._logger.warning(f"No download links found for: {entry.title}")
            return

        # Step 4: Enqueue
        self._enqueue(parsed, urls, entry, cache)

    def _enqueue(self, parsed: dict, urls: list[str],
                 entry: FeedEntry, cache: FileCacheManager):
        """Create a TorrentInfo and add to queue."""
        torrent = TorrentInfo(
            anime=parsed,
            url=urls,
            log_file=[cache.get_file_path()],
            title=entry.title,
        )
        torrent.set_event(TorrentEvents.QUEUED)
        self._queue.enqueue(torrent)
        self._logger.info(f"Enqueued: {entry.title}")
