from abc import ABC, abstractmethod
from typing import TypedDict

from core.interfaces.tracker.local import BaseLocalTracker
from core.interfaces.tracker.service import BaseServiceTracker


class SyncResult(TypedDict):
    added: int
    updated: int
    deleted: int
    conflicts: int
    errors: list[str]


class BaseSyncManager(ABC):
    """
    Abstract interface for synchronizing between local tracker and service trackers.
    """

    @abstractmethod
    def sync_from_service(self, local: BaseLocalTracker,
                          service: BaseServiceTracker,
                          user_id: str) -> SyncResult:
        """Pull data from service and merge into local tracker."""
        ...

    @abstractmethod
    def sync_to_service(self, local: BaseLocalTracker,
                        service: BaseServiceTracker,
                        user_id: str) -> SyncResult:
        """Push local changes to the service."""
        ...

    @abstractmethod
    def resolve_conflict(self, local_entry: dict,
                         remote_entry: dict) -> dict:
        """
        Resolve a conflict between local and remote entries.
        Returns the winning entry.
        """
        ...
