from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class DetectedMedia(TypedDict, total=False):
    player: str
    pid: int
    title: Optional[str]  # extracted window/media title
    file_path: Optional[str]
    position: Optional[int]  # playback position in milliseconds
    duration: Optional[int]  # total duration in milliseconds
    state: Optional[str]  # "playing", "paused", "stopped"


class BaseDetector(ABC):
    """
    Abstract interface for detecting running media players
    and extracting currently playing media information.
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
    def detect(self) -> list[DetectedMedia]:
        """Detect all running media players and their current media."""
        ...

    @abstractmethod
    def is_player_running(self, player_name: str) -> bool:
        """Check if a specific media player is running."""
        ...
