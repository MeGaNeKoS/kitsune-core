import enum


class MediaType(enum.Enum):
    ANIME = "ANIME"
    MANGA = "MANGA"


class MediaStatus(enum.Enum):
    """User's watch/read status for a media entry."""
    WATCHING = "WATCHING"
    COMPLETED = "COMPLETED"
    PLANNED = "PLANNED"
    DROPPED = "DROPPED"
    PAUSED = "PAUSED"
    REPEATING = "REPEATING"
