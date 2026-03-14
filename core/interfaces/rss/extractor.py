from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractionRule:
    """
    Declares where to find download links in an RSS feed entry.

    Each RSS source structures its entries differently. This rule tells the
    extractor which fields contain the magnet link, torrent URL, or info hash.

    Use dot notation for nested fields: "links.0.href"
    Leave empty to skip that link type.

    Example for nyaa.si:
        ExtractionRule(
            source="nyaa.si",
            magnet="link",         # <link> element contains the magnet
            info_hash="nyaa:infoHash",  # custom namespace field
        )

    Example for subsplease:
        ExtractionRule(
            source="subsplease.org",
            torrent="links.0.href",  # first link's href is the .torrent URL
        )

    If no rule matches a feed's source, the extractor falls back to
    regex auto-detection (scans the entire entry for magnet/torrent patterns).
    """
    source: str             # hostname to match, e.g. "nyaa.si"
    magnet: str = ""        # field path to magnet link
    torrent: str = ""       # field path to .torrent URL
    info_hash: str = ""     # field path to info hash


@dataclass
class FeedEntry:
    """A parsed RSS feed entry with extracted download links."""
    title: str
    magnet_links: list[str] = field(default_factory=list)
    info_hashes: list[str] = field(default_factory=list)
    torrent_links: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class BaseExtractor(ABC):
    """
    Extracts download links (magnet, torrent, info_hash) from RSS feed entries.
    """

    @abstractmethod
    def extract(self, entry: dict, source: str) -> FeedEntry:
        """Extract download links from a single RSS entry."""
        ...

    @abstractmethod
    def extract_feed(self, url: str, seen: list[str] = None) -> list[FeedEntry]:
        """Parse an RSS feed URL and extract all entries, skipping already-seen titles."""
        ...
