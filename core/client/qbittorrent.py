import base64
import logging
import os
import re
import time
from enum import Enum
from typing import cast, Union

from devlog import log_on_start, log_on_error

from core.features import require

require("downloader")
import qbittorrentapi
from qbittorrentapi import TorrentInfoList, TorrentFile as QbittorrentFile
from qbittorrentapi.torrents import TorrentDictionary

from core.interfaces.torrent.client import Client, RateLimitedClient, DownloadStrategy, ClientConfig
from core.interfaces.torrent.torrent import TorrentFile, TorrentStates, FileStates, TorrentEvents
from core.interfaces.torrent.torrent.torrent import TorrentInfo
from core.error import NotFoundError

logger = logging.getLogger(__name__)


class QBittorrent(Client):
    """
    QBittorrent client class for handling interactions with the QBittorrent API.

    Custom Attributes:
        category (str, None): Default category for grouping torrents.
                                       Used to distinguish between auto-added
                                       and user-added torrents. Can be None.

        tag (str, list[str], None): Default tags for grouping torrents.
                                      QBittorrent allows multiple tags per torrent.
                                      It Can be a single string, list of strings, or None.
    """

    _name = "qbittorrent"
    # https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#get-torrent-contents
    priorities = [0, 1, 6, 7]

    class AuthConfig(Enum):
        USERNAME = ClientConfig("username", str, "admin", True)
        PASSWORD = ClientConfig("password", str, "adminadmin", True)
        HOST = ClientConfig("host", str, "localhost", True)
        PORT = ClientConfig("port", int, 8080, True)

    class CustomConfig(Enum):
        CATEGORY = ClientConfig("category", str, "", False)
        TAGS = ClientConfig("tags", list[str], "", False)

    def __init__(self, **kwargs):
        """
        Initialize the client.
        """
        super().__init__(**kwargs)

        self.client: qbittorrentapi.Client = qbittorrentapi.Client()

    # Utility methods
    def _get_info_hash_from_url(self, url):
        if url.startswith("magnet:"):
            candidate = re.findall("urn:btih:(.*?)(?:&|$)", url, flags=re.IGNORECASE)
            for info_hash in candidate:
                if len(info_hash) == 40 or len(info_hash) == 64:
                    return info_hash
                if len(info_hash) == 32:
                    return base64.b32decode(info_hash).hex()
            self._logger.info(f"Could not find info_hash in magnet link: {url}")
        return None

    @classmethod
    def _get_next_priority(cls, current_priority):
        idx = cls.priorities.index(current_priority)
        return cls.priorities[min(len(cls.priorities) - 1, idx + 1)]

    @classmethod
    def _get_previous_priority(cls, current_priority):
        idx = cls.priorities.index(current_priority)
        return cls.priorities[max(0, idx - 1)]

    def _get_timeout(self, attempt):
        timeout = self.base_retry_wait_second ** attempt + self.base_retry_wait_second
        return min(self.max_retry_wait_second, int(timeout))

    @classmethod
    def _max_priority(cls):
        return cls.priorities[-1]

    @classmethod
    def _min_priority(cls):
        return cls.priorities[0]

    def _download_tick(self, torrent: TorrentInfo) -> None:
        if torrent.has_state(TorrentStates.ERROR):
            # Can't process the download if the torrent is in error state
            torrent.set_event(TorrentEvents.ERROR)
            return
        if torrent.downloaded_files == torrent.last_downloaded_files:
            # No new files downloaded
            return

        if self.download_strategy == DownloadStrategy.NORMAL:
            # we don't need to do anything
            return

        if self.download_strategy == DownloadStrategy.PRIORITY_BASED:
            self._priority_based_tick(torrent)
        elif self.download_strategy == DownloadStrategy.ONE_AT_A_TIME:
            self._one_at_time_tick(torrent)

    def _one_at_time_tick(self, torrent: TorrentInfo) -> None:
        """
        Method to download torrent files one at a time.

        This method increases the download priority of the next file
        once the current file is completely downloaded (progress is 1 or above).
        It breaks the loop if a file is being downloaded but not yet complete (progress is less than 1).

        :param torrent: TorrentInfo object containing files to be downloaded.
        """
        priority_increase_flag = False
        for identifier, file in torrent.files.items():
            if file.state == FileStates.SKIPPED:
                continue

            if file.progress >= 1:
                priority_increase_flag = True
            elif priority_increase_flag and file.progress < 1:
                next_priority = self._get_next_priority(file.download_priority)
                try:
                    self.client.torrents_file_priority(torrent.info_hash, identifier, next_priority)
                except Exception as e:
                    self._logger.error(
                        f"Failed to set priority for {torrent.name} - {file.name} from {file.download_priority} "
                        f"to {next_priority} - {e}")
                    continue
                file.download_priority = next_priority
                break
            elif file.progress < 1:
                break

    def _priority_based_tick(self, torrent: TorrentInfo) -> None:
        """
        Method to download torrent files based on a priority scheme.

        The method increases the download priority of the next file
        that is not fully downloaded (progress is less than 1) by 1 unit
        once the current file is completely downloaded (progress is 1).
        It ensures that no two consecutive files have the same priority.

        :param torrent: TorrentInfo object containing files to be downloaded.
        """
        increase_next = False
        previous_priority = None
        for identifier, file in torrent.files.items():
            if file.state == FileStates.SKIPPED:
                continue

            if file.progress >= 1:
                increase_next = True
            elif increase_next and file.progress < 1:
                next_priority = self._get_next_priority(file.download_priority)
                if next_priority == previous_priority:
                    # in case there's an out-of-sync, we won't get two files that have the same priority
                    break

                previous_priority = file.download_priority
                try:
                    self.client.torrents_file_priority(torrent.info_hash, identifier, next_priority)
                except Exception as e:
                    self._logger.error(
                        f"Failed to set priority for {torrent.name} - {file.name} to {next_priority} - {e}")
                    continue

                previous_priority = next_priority
                if next_priority == self._get_next_priority(self._min_priority()):
                    increase_next = False
                file.download_priority = next_priority
            else:
                previous_priority = file.download_priority

    def _start_download(self, torrent: TorrentInfo):
        """
        Initializes the downloading of a torrent by setting the priority of files.
        The function sets the highest priority to the first file. For 'PRIORITY_BASED' strategy,
        it decreases the priority for each subsequent file. For 'ONE_AT_A_TIME' strategy, it sets
        the lowest priority for each subsequent file. This ensures that files are downloaded in
        order of priority or one at a time depending on the chosen strategy.

        :param torrent: The torrent whose files are to be downloaded.
        """
        if self.download_strategy == DownloadStrategy.NORMAL:
            return

        this_priority = self._max_priority()
        for identifier, file in torrent.files.items():
            if file.progress >= 1 and file:
                continue

            try:
                self.client.torrents_file_priority(torrent.info_hash, identifier, this_priority)
            except Exception as e:
                self._logger.error(
                    f"Failed to set priority for {torrent.name} - {file.name} to {this_priority} - {e}")
                continue

            file.download_priority = this_priority

            if this_priority == self._min_priority():
                file.state = FileStates.QUEUED
            else:
                file.state = FileStates.DOWNLOADING

            # Decide the priority for the next file based on the download strategy
            if self.download_strategy == DownloadStrategy.PRIORITY_BASED:
                this_priority = self._get_previous_priority(this_priority)
            elif self.download_strategy == DownloadStrategy.ONE_AT_A_TIME:
                this_priority = self._min_priority()

    def _try_loop(self, *, max_retries=None, exponential_backoff=False):
        """
        This method is a generator function that produces a series of attempts for any operation that may fail and
        needs retries. The method waits for a certain period before each new attempt. The waiting period can be a
        fixed value, or it can grow exponentially based on the number of failed attempts.

        :param max_retries: The maximum number of attempts. If not provided, the instance's max_retries attribute
                            will be used.
        :param exponential_backoff: A boolean value to determine whether to use exponential backoff for
                            the waiting period.

        :yields: The current attempt number.
        """
        max_retries = max_retries or self.max_retries
        for attempt in range(max_retries):
            yield attempt
            # In case any error happens, wait before retry
            # Sometimes the torrent is not found because of a heavy load on the client.
            if exponential_backoff:
                self._event.wait(self._get_timeout(attempt))
            else:
                self._event.wait(self._wait_time)
            if self._event.is_set():
                break

    @classmethod
    def _update_torrent(cls, torrent: TorrentInfo, entry: TorrentDictionary) -> None:
        """
        This method updates the properties of a TorrentInfo object based on a TorrentDictionary object.
        The TorrentInfo object is a representation of a torrent within the system,
        while the TorrentDictionary is the raw information received from a torrent client.
        The method includes updating torrent states, file details, progress, and client-specific attributes.

        :param torrent: TorrentInfo object to be updated.
        :param entry: TorrentDictionary object providing the new data.
        """
        torrent.info_hash = entry.hash
        torrent.name = entry.name
        torrent.save_path = entry.save_path
        torrent.total_size = entry.size
        torrent.torrent_size = entry.total_size
        torrent.progress = entry.progress

        torrent.client_attributes.update({
            cls.CustomConfig.TAGS.value: entry.tags,
            cls.CustomConfig.CATEGORY.value: entry.category
        })

        state_conditions = {
            TorrentStates.CHECKING: entry.state_enum.is_checking,
            TorrentStates.SEEDING: entry.state_enum.is_uploading,
            TorrentStates.COMPLETED: entry.state_enum.is_complete,
            TorrentStates.DOWNLOADING: entry.state_enum.is_downloading,
            TorrentStates.ERROR: entry.state_enum.is_errored,
            TorrentStates.PAUSED: entry.state_enum.is_paused,
        }
        state = TorrentStates(0)  # Initialize state as an empty set
        for state_type, condition, event in state_conditions.items():
            if condition:
                state |= state_type

        state = state if state != TorrentStates(0) else TorrentStates.UNKNOWN

        torrent.set_state(state)

        downloaded_files = 0
        for file in entry.files:  # type: QbittorrentFile
            folder_path, filename = os.path.split(file.name)
            current_file_size = file.progress * file.size

            if file.index in torrent.files:
                this_file = torrent.files[file.index]
                # update the file
                this_file.name = filename
                this_file.folder_path = folder_path
                this_file.download_priority = file.priority

                if file.priority != cls._min_priority():
                    if file.progress >= 1 and this_file.state != FileStates.COMPLETED:
                        this_file.state = FileStates.COMPLETED

                    elif file.progress > 0 and this_file.state != FileStates.DOWNLOADING:
                        this_file.state = FileStates.DOWNLOADING

                this_file.downloaded_size = current_file_size
            else:
                torrent.files[file.index] = TorrentFile(
                    name=filename,  # individual file name
                    _total_size=file.size,  # individual file size
                    download_priority=file.priority,
                    state=FileStates.DOWNLOADING,  # By default, it will download everything
                    folder_path=folder_path,  # folder path
                    _downloaded_size=current_file_size
                )
                torrent.set_event(TorrentEvents.DOWNLOADING)

            if file.progress >= 1:
                downloaded_files += 1

        if torrent.downloaded_files != downloaded_files:
            torrent.downloaded_files = downloaded_files
            torrent.set_event(TorrentEvents.COMPLETED_FILES_CHANGES)

    # Connection methods
    @log_on_start(logging.INFO, "Connecting to qBittorrent...")
    @log_on_error(logging.ERROR, "Failed to connect to qBittorrent: {error!r}",
                  sanitize_params={"password"})
    def connect(self) -> bool:
        """
        This method connects the application to the torrent client using the provided authentication details.
        If the connection isn't already established, it attempts to connect a certain number of times
        with an exponential backoff mechanism for retrying. If all attempts fail, it raises a ConnectionError.

        :raises ConnectionError: If the application fails to connect to the torrent client after all attempts.
        """
        if not self.client.is_logged_in:
            for attempt in self._try_loop(exponential_backoff=True):
                try:
                    client = qbittorrentapi.Client(**self.client_auth)
                    rate_limited_client = RateLimitedClient(client, self.request_per_second)
                    self.client = cast(qbittorrentapi.Client, rate_limited_client)  # for type hinting
                    break
                except Exception as e:
                    logger.error(f"Login failed [{attempt + 1}/{self.max_retries}]: {e}")
                    self._start_if_not_running()

        # check if the client is connected
        if not self.client.is_logged_in:
            raise ConnectionError("Could not connect to the client")
        return self.client.is_logged_in

    # Torrent methods
    @log_on_error(logging.ERROR, "Failed to add torrent: {error!r}")
    def add_torrent(self, torrent: TorrentInfo) -> bool:
        tags = self.config.get(self.CustomConfig.TAGS.value, None)
        category = self.config.get(self.CustomConfig.CATEGORY.value, None)

        if not isinstance(tags, list):
            tags = [tags]

        tags = list(filter(None, tags))

        # this used to identify the torrent since the client only return Ok.
        identifier = f"identifier-{time.time()}"

        if identifier not in tags:
            tags.append(identifier)

        if not tags:
            tags = None

        for url in torrent.urls:
            if not url:
                continue

            info_hash = self._get_info_hash_from_url(url)

            for attempt in self._try_loop():
                self.client.torrents_add(url, tags=tags, category=category)

                # Verify if the torrent was added.
                # Because QBittorrent return ok weather it added or not.
                data = self.get_torrent_info(torrent_hash=info_hash) if info_hash else self.get_torrent_info(
                    tags=identifier)
                if data:
                    torrent.client = self
                    torrent.set_event(TorrentEvents.ADDED)
                    self._update_torrent(torrent, data[0])
                    self.torrent_remove_tag(torrent.info_hash, [identifier], True)
                    return True
                self._logger.info(f"[{attempt + 1}/{self.max_retries}] Failed to add torrent: {torrent.name}")
        self._logger.info(f"Failed to add torrent: {torrent.name}")
        return False

    def get_torrent_info(self, torrent_hash: str = None, tags=None, category=None) -> Union[TorrentInfoList, None]:
        """
        Retrieves information about a specific torrent from the client.

        This method queries the client to fetch the torrent details. It will retry the operation based on the defined
        max_retries if an exception occurs during the fetch operation. It uses the provided torrent hash, tags,
        and category as search criteria to find the torrent.

        :param torrent_hash: The unique hash of the torrent.
        :param tags: A list or a single tag associated with the torrent.
        :param category: The category of the torrent.

        :return: A list of matching torrent entries (TorrentInfoList) or None if no match found or in case of an exception.
        """
        for _ in self._try_loop():
            try:
                entries = self.client.torrents_info(torrent_hashes=torrent_hash, tag=tags, category=category)
                if entries:
                    return entries
            except qbittorrentapi.APIError as e:
                self._logger.error(f"Could not get torrent information: {e}")
            except Exception as e:
                self._logger.error(f"Could not get torrent information: {e}")
                return None
        return None

    @log_on_error(logging.ERROR, "Failed to remove torrent: {error!r}")
    def remove_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """
        Removes a specific torrent from the client.

        This method attempts to delete a torrent using its unique hash. It will retry the operation based on the defined
        max_retries if the torrent is not deleted in the first attempt. Optionally, it can also delete the downloaded
        files associated with the torrent.

        :param torrent_hash: The unique hash of the torrent to be deleted.
        :param delete_files: Boolean indicating whether to delete the downloaded files associated with the torrent.

        :return: True if the torrent was deleted successfully, False otherwise.
        """
        for _ in self._try_loop():
            self.client.torrents_delete(torrent_hashes=torrent_hash, delete_files=delete_files)

            # verify if the torrent was removed
            if not self.get_torrent_info(torrent_hash):
                return True
        return False

    def set_file_priority(self, torrent_hash: str, file_id: int, priority: int) -> bool:
        """
        Sets the priority for a specific file in a torrent.

        This method attempts to set the priority for a specific file identified by its id, in a specific torrent
        identified by its hash. It will retry the operation based on the defined max_retries if the operation fails
        in the first attempt.

        :param torrent_hash: The unique hash of the torrent containing the file.
        :param file_id: The id of the file whose priority is to be set.
        :param priority: The priority to be set.

        :return: True if the operation was successful, False otherwise.
        """
        for _ in self._try_loop():
            self.client.torrents_file_priority(torrent_hash, file_id, priority)
            return True
        return False

    def update_data(self, torrent: TorrentInfo) -> None:
        """
        Updates the data for a specific torrent.

        This method fetches the latest data for a torrent from the client and updates the local representation of
        the torrent. If new data is successfully fetched, it processes the download for the torrent. This method
        will retry the operation based on the defined max_retries if the operation fails in the first attempt.

        :param torrent: The torrent object whose data is to be updated.
        """
        for _ in self._try_loop():
            data = self.get_torrent_info(torrent_hash=torrent.info_hash)
            if data:
                self._update_torrent(torrent, data[0])
                self._download_tick(torrent)
                return
        raise NotFoundError("Torrent not found")

    def pause_torrent(self, torrent_hash: str) -> bool:
        """
        Pauses a specific torrent.

        This method attempts to pause a specific torrent identified by its hash.
        It will retry the operation based on the defined max_retries if the operation fails in the first attempt.

        :param torrent_hash: The unique hash of the torrent to be paused.

        :return: True if the operation was successful, False otherwise.
        """
        for _ in self._try_loop():
            self.client.torrents_pause(torrent_hashes=torrent_hash)
            return True
        return False

    def resume_torrent(self, torrent_hash: str) -> bool:
        """
        Resume a specific torrent.

        This method attempts to resume a specific torrent identified by its hash.
        It will retry the operation based on the defined max_retries if the operation fails in the first attempt.

        :param torrent_hash: The unique hash of the torrent to be paused.

        :return: True if the operation was successful, False otherwise.
        """
        for _ in self._try_loop():
            self.client.torrents_resume(torrent_hashes=torrent_hash)
            return True
        return False

    # client-specific methods
    def torrent_add_tags(self, torrent_hash: str, tags: list) -> bool:
        """
        Adds tags to a specific torrent.

        This method attempts to add specified tags to a specific torrent identified by its hash.
        It will retry the operation based on the defined max_retries if the operation fails in the first attempt.

        :param torrent_hash: The unique hash of the torrent to add tags to.
        :param tags: A list of tags to be added to the torrent.

        :return: True if the operation was successful, False otherwise.
        """
        for _ in self._try_loop():
            self.client.torrents_add_tags(torrent_hashes=torrent_hash, tags=tags)

            data = self.get_torrent_info(torrent_hash)
            if not data:
                continue

            for tag in tags:
                if tag in data[0].tags:
                    continue
                break
            else:
                return True
        return False

    def torrent_remove_tag(self, torrent_hash: str, tags: list, delete=False) -> bool:
        """
        Removes specified tags from a torrent or deletes them completely.

        This method attempts to remove specified tags from a specific torrent identified by its hash or
        deletes them completely from the client. It will retry the operation based on the defined max_retries
        if the operation fails in the first attempt.

        :param torrent_hash: The unique hash of the torrent to remove tags from.
        :param tags: A list of tags to be removed.
        :param delete: If set to True, the tags will be completely deleted from the client.

        :return: True if the operation was successful, False otherwise.
        """
        for _ in self._try_loop():
            if delete:
                self.client.torrents_delete_tags(tags=tags)
                for tag in tags:
                    if tag in self.client.torrents_tags():
                        break
                else:
                    return True
            else:
                self.client.torrents_remove_tags(torrent_hashes=torrent_hash, tags=tags)

                data = self.get_torrent_info(torrent_hash)
                if not data:
                    continue

                remaining_tags = set(data[0].tags)
                if not any(tag in remaining_tags for tag in tags):
                    return True

        return False
