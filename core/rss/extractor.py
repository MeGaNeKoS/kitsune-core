"""
RSS feed link extractor.

Extracts magnet links, torrent URLs, and info hashes from RSS feed entries.
Supports declarative ExtractionRules for known sources, with regex
auto-detection as fallback for unknown sources.
"""

import html
import logging
import re
from urllib.parse import urlparse

from devlog import log_on_error

from core.features import require

require("downloader")
import feedparser

from core.interfaces.rss.extractor import BaseExtractor, ExtractionRule, FeedEntry

logger = logging.getLogger(__name__)

# Regex patterns for auto-detection
_MAGNET_RE = re.compile(r"(magnet:\?xt=urn:btih:([a-zA-Z0-9]{32,64})(?:&[^\"']+)?)")
_TORRENT_RE = re.compile(r"(https?://[^\"']+?\.torrent)")
_HASH_RE = re.compile(r"(?<!/)\b([a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b(?!/)")


def _resolve_field(data: dict, path: str):
    """
    Resolve a dot-separated field path against a dict.

    Examples:
        _resolve_field(entry, "link")           → entry["link"]
        _resolve_field(entry, "links.0.href")   → entry["links"][0]["href"]
        _resolve_field(entry, "nyaa:infoHash")  → entry["nyaa:infoHash"]
    """
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return current


class Extractor(BaseExtractor):

    def __init__(self, rules: list[ExtractionRule] = None):
        self._rules: dict[str, ExtractionRule] = {}
        if rules:
            for rule in rules:
                self._rules[rule.source] = rule

    def add_rule(self, rule: ExtractionRule):
        self._rules[rule.source] = rule

    def remove_rule(self, source: str):
        self._rules.pop(source, None)

    @log_on_error(logging.ERROR, "Failed to extract from entry: {error!r}")
    def extract(self, entry: dict, source: str) -> FeedEntry:
        title = entry.get("title", "")
        feed_entry = FeedEntry(title=title, raw=entry)

        rule = self._rules.get(source)
        if rule:
            feed_entry = self._extract_with_rule(entry, rule, feed_entry)

        # Fallback: auto-detect from entire entry string
        if not feed_entry.magnet_links and not feed_entry.torrent_links and not feed_entry.info_hashes:
            feed_entry = self._auto_detect(entry, feed_entry)

        return feed_entry

    @log_on_error(logging.ERROR, "Failed to parse feed: {error!r}")
    def extract_feed(self, url: str, seen: list[str] = None) -> list[FeedEntry]:
        seen = seen or []
        feed = feedparser.parse(url)
        source = urlparse(url).hostname or ""

        results = []
        for entry in feed.get("entries", []):
            title = entry.get("title", "")
            if not title or title in seen:
                continue
            results.append(self.extract(entry, source))

        return results

    @staticmethod
    def _extract_with_rule(entry: dict, rule: ExtractionRule, feed_entry: FeedEntry) -> FeedEntry:
        """Extract links using a declared rule."""
        if rule.magnet:
            value = _resolve_field(entry, rule.magnet)
            if value and isinstance(value, str) and "magnet:" in value:
                feed_entry.magnet_links.append(value)

        if rule.torrent:
            value = _resolve_field(entry, rule.torrent)
            if value and isinstance(value, str) and (".torrent" in value or "http" in value):
                feed_entry.torrent_links.append(value)

        if rule.info_hash:
            value = _resolve_field(entry, rule.info_hash)
            if value and isinstance(value, str):
                feed_entry.info_hashes.append(value)

        return feed_entry

    @staticmethod
    def _auto_detect(entry: dict, feed_entry: FeedEntry) -> FeedEntry:
        """Fallback: scan the entire entry for magnet/torrent/hash patterns."""
        entry_str = str(entry)

        # Magnet links
        for match in _MAGNET_RE.finditer(entry_str):
            link = html.unescape(match.group(1))
            if link not in feed_entry.magnet_links:
                feed_entry.magnet_links.append(link)

        # Torrent links
        for match in _TORRENT_RE.finditer(entry_str):
            link = html.unescape(match.group(1))
            if link not in feed_entry.torrent_links:
                feed_entry.torrent_links.append(link)

        # Also check enclosures (standard RSS way to attach files)
        for link in entry.get("links", []):
            if link.get("type") == "application/x-bittorrent":
                href = link.get("href", "")
                if href and href not in feed_entry.torrent_links:
                    feed_entry.torrent_links.append(href)

        # Info hashes (only if no magnets found, to avoid false positives)
        if not feed_entry.magnet_links:
            for match in _HASH_RE.finditer(entry_str):
                hash_str = match.group(1)
                if hash_str not in feed_entry.info_hashes:
                    feed_entry.info_hashes.append(hash_str)

        return feed_entry
