from enum import IntFlag, Enum


class TorrentStates(IntFlag):
    CHECKING = 1 << 0  # Bit 0
    COMPLETED = 1 << 1  # Bit 1
    SEEDING = 1 << 2  # Bit 2
    DOWNLOADING = 1 << 3  # Bit 3
    ERROR = 1 << 4  # Bit 4
    PAUSED = 1 << 5  # Bit 5
    UNKNOWN = 1 << 6  # Bit 6


class TorrentEvents(IntFlag):
    # The torrent just added to queue list
    QUEUED = 1 << 0  # Bit 0
    # Torrent just added to a client
    ADDED = 1 << 1  # Bit 1
    # Torrent is downloading (metadata available)
    DOWNLOADING = 1 << 2  # Bit 2
    # Torrent finished downloading
    COMPLETED = 1 << 3  # Bit 3
    # Torrent is removed from the client
    REMOVED = 1 << 4  # Bit 4
    # An error occurred with the torrent
    ERROR = 1 << 5  # Bit 5
    # Torrent has reached its seeding goal
    SEEDING_COMPLETED = 1 << 6  # Bit 6
    # Torrent download progress has changed
    COMPLETED_FILES_CHANGES = 1 << 7  # Bit 7


class FileStates(Enum):
    QUEUED = 0
    DOWNLOADING = 1
    COMPLETED = 2
    SKIPPED = 3
    PAUSED = 4
