"""
IDEA: To give user ability on how to parse the rss feed from given url

This could be accomplished by letting the user write their own rule on which field should we look for the link,
and how we can proceed afterward. One of the idea is to use regex,
{
    "service_name": {
        "field_name": {  # either magnet, torrent, or info_hash
            "fields": [
                {
                    "field": "field_name",
                    "pattern": "regex_pattern_to_match_value",
                    "filter": {
                        "optional_filter_key": "optional_filter_value"
                    },
                    "sub_fields": [
                        {
                            "field": "sub_field_name",
                            "filter": {
                                "optional_filter_key": "optional_filter_value"
                            },
                            "sub_fields": [
                                {
                                    "field": "sub_sub_field_name",
                                    "filter": {
                                        "optional_filter_key": "optional_filter_value"
                                    },
                                    "...": "..."
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }
}
"""

import copy
import html
import logging
import re
from urllib.parse import urlparse

from core.features import require

require("downloader")
import feedparser
from feedparser import FeedParserDict


class RSSRuleParser:
    magnet_pattern = re.compile(r"(magnet:\?xt=urn:btih:([a-zA-Z0-9]{32,64})(?:&[^\"']+)?)")
    torrent_pattern = re.compile(r"(https?:\/\/[^\"']+?\.torrent)")
    info_hash_pattern = re.compile(r"(?<!/)\b([a-zA-Z0-9]{32,64})\b(?!/)")
    link_type_pattern = r"application/x-bittorrent"

    # As singleton for no reason.
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.configurations = {}

    def reload_config(self):
        self._compile_patterns(self.configurations)

    def load_configurations(self, config_object: dict):
        self._compile_patterns(config_object)
        self.configurations = config_object

    @classmethod
    def _compile_patterns(cls, config: dict):
        for service_name, service_config in config.items():
            for field_name, field_config in service_config.items():
                fields = field_config.get("fields", [])
                for field in fields:
                    pattern = field.get("pattern")
                    if pattern:
                        field["pattern"] = re.compile(pattern)
                    else:
                        cls.logger.warning(f"Pattern not found for {service_name}.{field_name}\n{field}")

    def to_dict(self):
        copied_configurations = copy.deepcopy(self.configurations)

        # Convert compiled regex objects back to strings in the copied configurations
        for service_name, service_config in copied_configurations.items():
            for field_name, field_config in service_config.items():
                fields = field_config.get("fields", [])
                for field in fields:
                    pattern = field.get("pattern")
                    if pattern and isinstance(pattern, re.Pattern):
                        field["pattern"] = pattern.pattern

        return copied_configurations

    @classmethod
    def from_dict(cls, config_object: dict):
        instance = cls()
        instance.load_configurations(config_object)
        return instance

    def parse_field(self, data, service_name, field_name):
        service_config = self.configurations.get(service_name, {})
        field_config = service_config.get(field_name, {})

        return self._process_fields(data, field_config.get("fields", []), field_config.get("pattern"))

    @classmethod
    def _process_fields(cls, data, fields_config, pattern=None):
        results = []

        for field_config in fields_config:
            field_name = field_config["field"]

            if field_name not in data:
                continue

            value = data[field_name]
            filter_conditions = field_config.get("filter", {})

            if isinstance(value, list):
                for item in value:
                    if not filter_conditions or all(item.get(k) == v for k, v in filter_conditions.items()):
                        results.extend(cls._process_fields(item, field_config.get("sub_fields", []), pattern))
            elif isinstance(value, dict):
                if not filter_conditions or all(value.get(k) == v for k, v in filter_conditions.items()):
                    results.extend(cls._process_fields(value, field_config.get("sub_fields", []), pattern))
            elif isinstance(value, str) and pattern is not None:
                match = re.search(pattern, value)
                if match:
                    results.append(match.group(0))

        return results

    def parse_feed(self, url, log_file: list) -> dict:
        feed: FeedParserDict = feedparser.parse(url)

        result = {}

        for torrent in feed['entries']:
            title = torrent.get("title")
            if not title or title in log_file:
                continue

            torrent_str = str(torrent)

            magnet_links = self.parse_field(torrent, urlparse(url).hostname, 'magnet')
            if not magnet_links:
                magnet_links = self.magnet_pattern.findall(torrent_str)
                # Validate magnet links
                valid_magnet_links = []
                for magnet_link, hash_str in magnet_links:
                    hash_length = len(hash_str)
                    if hash_length not in (32, 40, 64):
                        self.logger.error(f'Invalid magnet link hash length: {hash_length}')
                    else:
                        valid_magnet_links.append(magnet_link)
                magnet_links = valid_magnet_links

            info_hashes = self.parse_field(torrent, urlparse(url).hostname, 'info_hash')
            if not info_hashes:
                info_hashes = self.info_hash_pattern.findall(torrent_str)
                # Validate info_hash
                valid_info_hashes = []
                for hash_str in info_hashes:
                    hash_length = len(hash_str)
                    if hash_length in (32, 40, 64):
                        valid_info_hashes.append(hash_str)
                    else:
                        self.logger.error(f'Invalid magnet link hash length: {hash_length}')
                info_hashes = valid_info_hashes

            torrent_links = self.parse_field(torrent, urlparse(url).hostname, 'torrent')
            if not torrent_links:
                torrent_links = self.torrent_pattern.findall(torrent_str)
                # Detect link types in torrent.enclosures and extract torrent links
                enclosures = torrent.get("links", [])
                for enclosure in enclosures:
                    if enclosure.get("type") == self.link_type_pattern:
                        torrent_link = enclosure.get("href")
                        if torrent_link:
                            torrent_links.append(torrent_link)

            if not magnet_links and not torrent_links and not info_hashes:
                self.logger.error(f'Failed to get magnet link or torrent link from {torrent}')
            else:
                magnet_links = list({link.lower(): html.unescape(link) for link in magnet_links}.values())
                info_hashes = list({hash_str.lower(): html.unescape(hash_str) for hash_str in info_hashes}.values())
                torrent_links = [html.unescape(link) for link in set(torrent_links)]

                result[title] = [magnet_links, info_hashes, torrent_links]

        return result
