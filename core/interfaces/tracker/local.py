from abc import ABC, abstractmethod
from typing import Optional

from core.interfaces.database.types.media import MediaType, MediaStatus


class BaseLocalTracker(ABC):
    """
    Abstract interface for local media tracking.
    Operates on the local database as the source of truth.
    """

    @abstractmethod
    def get_entry(self, media_id: int) -> dict:
        """Get a single media entry by local ID."""
        ...

    @abstractmethod
    def list_entries(self, status: Optional[MediaStatus] = None,
                     media_type: Optional[MediaType] = None) -> list[dict]:
        """List media entries, optionally filtered by status/type."""
        ...

    @abstractmethod
    def add_entry(self, title: str, media_type: MediaType = MediaType.ANIME,
                  **kwargs) -> dict:
        """Add a new media entry to the local tracker."""
        ...

    @abstractmethod
    def update_progress(self, media_id: int, progress: int) -> dict:
        """Update episode/chapter progress for a media entry."""
        ...

    @abstractmethod
    def update_status(self, media_id: int, status: MediaStatus) -> dict:
        """Update the watch/read status of a media entry."""
        ...

    @abstractmethod
    def update_entry(self, media_id: int, **kwargs) -> dict:
        """Update arbitrary fields on a media entry."""
        ...

    @abstractmethod
    def delete_entry(self, media_id: int) -> bool:
        """Delete a media entry."""
        ...

    @abstractmethod
    def search(self, query: str) -> list[dict]:
        """Search local entries by title."""
        ...

    @abstractmethod
    def link_service(self, media_id: int, service_name: str,
                     service_media_id: str) -> dict:
        """Link a local entry to an external service ID."""
        ...

    @abstractmethod
    def unlink_service(self, media_id: int, service_name: str) -> bool:
        """Remove a service link from a local entry."""
        ...

    @abstractmethod
    def get_service_mapping(self, media_id: int) -> list[dict]:
        """Get all service mappings for a local entry."""
        ...
