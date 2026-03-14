from core.rss.extractor import Extractor, _resolve_field
from core.interfaces.rss import ExtractionRule, FeedEntry


class TestResolveField:

    def test_simple_key(self):
        assert _resolve_field({"link": "magnet:?xt=urn:btih:abc"}, "link") == "magnet:?xt=urn:btih:abc"

    def test_nested_key(self):
        data = {"links": [{"href": "http://example.com/file.torrent"}]}
        assert _resolve_field(data, "links.0.href") == "http://example.com/file.torrent"

    def test_missing_key(self):
        assert _resolve_field({"a": 1}, "b") is None

    def test_deep_missing(self):
        assert _resolve_field({"a": {"b": 1}}, "a.c") is None

    def test_index_out_of_range(self):
        assert _resolve_field({"a": [1]}, "a.5") is None


class TestExtractor:

    def test_auto_detect_magnet(self):
        extractor = Extractor()
        entry = {
            "title": "Test Anime - 01",
            "link": "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=test",
        }
        result = extractor.extract(entry, "example.com")
        assert result.title == "Test Anime - 01"
        assert len(result.magnet_links) >= 1

    def test_auto_detect_torrent_link(self):
        extractor = Extractor()
        entry = {
            "title": "Test Anime - 01",
            "summary": "Download from https://example.com/file.torrent now",
        }
        result = extractor.extract(entry, "example.com")
        assert len(result.torrent_links) >= 1

    def test_auto_detect_enclosure(self):
        extractor = Extractor()
        entry = {
            "title": "Test Anime - 01",
            "links": [{"type": "application/x-bittorrent", "href": "https://example.com/dl.torrent"}],
        }
        result = extractor.extract(entry, "example.com")
        assert "https://example.com/dl.torrent" in result.torrent_links

    def test_rule_based_extraction(self):
        extractor = Extractor([ExtractionRule(source="nyaa.si", magnet="link")])
        entry = {
            "title": "Frieren - 05",
            "link": "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&dn=frieren",
        }
        result = extractor.extract(entry, "nyaa.si")
        assert len(result.magnet_links) == 1

    def test_add_remove_rule(self):
        extractor = Extractor()
        rule = ExtractionRule(source="test.com", magnet="link")
        extractor.add_rule(rule)
        assert "test.com" in extractor._rules
        extractor.remove_rule("test.com")
        assert "test.com" not in extractor._rules

    def test_no_links_found(self):
        extractor = Extractor()
        entry = {"title": "Some text with no links"}
        result = extractor.extract(entry, "example.com")
        assert result.magnet_links == []
        assert result.torrent_links == []
        assert result.info_hashes == []
