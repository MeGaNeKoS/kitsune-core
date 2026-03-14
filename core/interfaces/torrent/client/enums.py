from enum import Enum
from typing import NamedTuple, Any


class DownloadStrategy(Enum):
    """
    Enum representing different strategies for downloading torrents.

    Strategies:
    - NORMAL: Everything will be downloaded at the same time,
              following the torrent client's internal behavior.
    - PRIORITY_BASED: Files are downloaded based on their position in the
                      list, with the first file having the highest priority, while all
                      the other files are set to one priority level below the previous file.
                      Once a file is fully downloaded, the next file in the
                      list is promoted one level higher priority, and so on until
                      all files are downloaded.
    - ONE_AT_A_TIME: Only one file is downloaded at a time. The first file
                      in the list is set to the highest priority, while all
                      other files are set to not be downloaded. Once a file
                      is fully downloaded, the next file in the list is promoted
                      to highest priority, and so on until all files are downloaded.
    """
    NORMAL = "normal"
    PRIORITY_BASED = "priority_based"
    ONE_AT_A_TIME = "one_at_a_time"


class ClientMapping(Enum):
    """
    An enum representing the field in the json config file for the client, to ensure consistency between code and config.
    """
    NAME = "name"
    DOWNLOAD_STRATEGY = "download_strategy"
    BASE_RETRY_WAIT_SECOND = "base_retry_wait_time"
    MAX_RETRY_WAIT_SECOND = "max_retry_wait_time"
    MAX_RETRY = "max_retries"
    CONFIG = "config"
    CLIENT_AUTH = "client_auth"
    REQUEST_PER_SECOND = "request_per_second"
    PROGRAM_PATH = "program_path"


class ClientDefault(Enum):
    """
    A default value for client config.
    """
    DOWNLOAD_STRATEGY = DownloadStrategy.NORMAL.value
    BASE_RETRY_WAIT_SECOND = 0.5
    MAX_RETRY_WAIT_SECOND = 60
    MAX_RETRY = 10
    CONFIG = {}
    CLIENT_AUTH = {}
    REQUEST_PER_SECOND = 5
    PROGRAM_PATH = ""


class ClientConfig(NamedTuple):
    """
    A NamedTuple representing configuration settings for a client. It defines the structure of configuration fields,
    including their names, types, default values, and whether they are mandatory. This class is used to standardize
    and validate the configuration of clients.
    """
    field_name: str
    field_type: Any
    default_value: Any
    mandatory: bool = False
