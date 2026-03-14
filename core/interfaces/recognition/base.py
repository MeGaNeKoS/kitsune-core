from abc import ABC, abstractmethod
from typing import Optional, TypedDict


class RecognitionResult(TypedDict, total=False):
    anime_title: str
    episode_number: Optional[int]
    season_number: Optional[int]
    release_group: Optional[str]
    video_resolution: Optional[str]
    source: str  # "aniparse", "llm", etc.
    raw: dict  # full parsed output from the underlying parser


class BaseRecognizer(ABC):
    """
    Abstract interface for anime title recognition/parsing.
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
    def parse(self, title: str) -> RecognitionResult:
        """Parse a single anime title/filename into structured data."""
        ...

    @abstractmethod
    def parse_batch(self, titles: list[str]) -> list[RecognitionResult]:
        """Parse multiple titles. Default implementation calls parse() in a loop."""
        ...
