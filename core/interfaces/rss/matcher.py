from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from core.interfaces.rss.extractor import FeedEntry


@dataclass
class MatchRule:
    """
    Rule-based matcher. Decides if an RSS entry should be downloaded.

    All non-empty fields must match for the rule to pass.
    Leave a field empty/None to skip that check.

    Example — download 1080p releases from SubsPlease:
        MatchRule(
            title_pattern=r"Frieren",
            resolution=["1080p"],
            release_group=["SubsPlease"],
        )

    Example — download episodes 1-12, exclude batch releases:
        MatchRule(
            title_pattern=r"Frieren",
            exclude_pattern=r"batch|complete",
            episode_range=(1, 12),
        )
    """
    title_pattern: str = ""                   # regex to match title (case-insensitive)
    exclude_pattern: str = ""                 # regex to reject title
    resolution: list[str] = field(default_factory=list)      # e.g. ["1080p", "720p"]
    release_group: list[str] = field(default_factory=list)   # e.g. ["SubsPlease"]
    episode_range: Optional[tuple[int, int]] = None          # (start, end) inclusive


@dataclass
class LLMMatchRule:
    """
    Natural language rule evaluated by an LLM.

    The LLM receives the entry title + this prompt and returns yes/no.

    Example:
        LLMMatchRule(
            prompt="Download only if this is a 1080p release from a trusted "
                   "group (SubsPlease, Erai-raws, EMBER). Skip batch releases."
        )
    """
    prompt: str


class BaseMatcher(ABC):
    """
    Decides whether an RSS feed entry should be downloaded.
    """

    @abstractmethod
    def matches(self, entry: FeedEntry) -> bool:
        """Return True if this entry should be downloaded."""
        ...
