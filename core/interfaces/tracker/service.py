from abc import ABC, abstractmethod
from typing import Optional


class BaseServiceTracker(ABC):
    """
    Abstract interface for external tracking services (AniList, MAL, AniDB, etc.).
    Each implementation wraps a specific service's API.
    """

    _name: str = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls._name is None:
            raise NotImplementedError("Subclasses must define a '_name' attribute")

    @classmethod
    def get_name(cls) -> str:
        return cls._name

    @abstractmethod
    def authenticate(self, **kwargs) -> bool:
        """Authenticate with the service. Implementation-specific kwargs."""
        ...

    @abstractmethod
    def get_user_list(self, user_id: str,
                      status: Optional[str] = None) -> list[dict]:
        """Fetch the user's media list from the service."""
        ...

    @abstractmethod
    def get_media(self, media_id: str) -> dict:
        """Fetch metadata for a specific media by service ID."""
        ...

    @abstractmethod
    def search_media(self, query: str) -> list[dict]:
        """Search for media on the service."""
        ...

    @abstractmethod
    def update_entry(self, media_id: str, progress: int,
                     status: Optional[str] = None,
                     score: Optional[float] = None) -> bool:
        """Update a user's entry on the service."""
        ...

    @abstractmethod
    def delete_entry(self, media_id: str) -> bool:
        """Delete a user's entry from the service."""
        ...
