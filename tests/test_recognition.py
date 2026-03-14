import pytest

from core.features import is_available


@pytest.mark.skipif(not is_available("recognition"), reason="aniparse not installed")
class TestAniparseRecognizer:

    def test_basic_parse(self):
        from core.recognition import get_recognizer
        r = get_recognizer("aniparse")
        result = r.parse("[SubsPlease] Sousou no Frieren - 18 (1080p) [ABC].mkv")
        assert result["anime_title"] == "Sousou no Frieren"
        assert result["episode_number"] == 18
        assert result["video_resolution"] == "1080p"
        assert result["release_group"] == "SubsPlease"
        assert result["source"] == "aniparse"

    def test_no_episode(self):
        from core.recognition import get_recognizer
        r = get_recognizer("aniparse")
        result = r.parse("[SubsPlease] Frieren (1080p).mkv")
        assert result["anime_title"] != ""
        assert result["source"] == "aniparse"

    def test_parse_batch(self):
        from core.recognition import get_recognizer
        r = get_recognizer("aniparse")
        results = r.parse_batch([
            "[SubsPlease] Frieren - 01 (1080p).mkv",
            "[SubsPlease] Frieren - 02 (1080p).mkv",
        ])
        assert len(results) == 2
        assert results[0]["episode_number"] == 1
        assert results[1]["episode_number"] == 2
