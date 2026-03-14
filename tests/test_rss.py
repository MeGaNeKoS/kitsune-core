from core.rss.matcher import RuleMatcher, _extract_episode_number
from core.interfaces.rss import MatchRule, FeedEntry


class TestRuleMatcher:

    def test_title_pattern_match(self):
        matcher = RuleMatcher([MatchRule(title_pattern=r"Frieren")])
        assert matcher.matches(FeedEntry(title="[SubsPlease] Frieren - 05"))
        assert not matcher.matches(FeedEntry(title="[SubsPlease] Dandadan - 05"))

    def test_resolution_filter(self):
        matcher = RuleMatcher([MatchRule(resolution=["1080p"])])
        assert matcher.matches(FeedEntry(title="Frieren - 05 (1080p)"))
        assert not matcher.matches(FeedEntry(title="Frieren - 05 (720p)"))

    def test_release_group_filter(self):
        matcher = RuleMatcher([MatchRule(release_group=["SubsPlease"])])
        assert matcher.matches(FeedEntry(title="[SubsPlease] Frieren"))
        assert not matcher.matches(FeedEntry(title="[BadSubs] Frieren"))

    def test_exclude_pattern(self):
        matcher = RuleMatcher([MatchRule(exclude_pattern=r"batch|complete")])
        assert not matcher.matches(FeedEntry(title="Frieren Batch 1-28"))
        assert matcher.matches(FeedEntry(title="Frieren - 05"))

    def test_episode_range(self):
        matcher = RuleMatcher([MatchRule(episode_range=(1, 12))])
        assert matcher.matches(FeedEntry(title="Frieren - 05"))
        assert not matcher.matches(FeedEntry(title="Frieren - 18"))

    def test_combined_filters(self):
        matcher = RuleMatcher([MatchRule(
            title_pattern=r"Frieren",
            resolution=["1080p"],
            release_group=["SubsPlease"],
        )])
        assert matcher.matches(FeedEntry(title="[SubsPlease] Frieren - 05 (1080p)"))
        assert not matcher.matches(FeedEntry(title="[SubsPlease] Frieren - 05 (720p)"))
        assert not matcher.matches(FeedEntry(title="[BadSubs] Frieren - 05 (1080p)"))

    def test_no_rules_accepts_all(self):
        matcher = RuleMatcher()
        assert matcher.matches(FeedEntry(title="anything"))

    def test_multiple_rules_or_logic(self):
        matcher = RuleMatcher([
            MatchRule(title_pattern=r"Frieren"),
            MatchRule(title_pattern=r"Dandadan"),
        ])
        assert matcher.matches(FeedEntry(title="Frieren - 05"))
        assert matcher.matches(FeedEntry(title="Dandadan - 03"))
        assert not matcher.matches(FeedEntry(title="One Piece - 1000"))


class TestEpisodeExtraction:

    def test_dash_format(self):
        assert _extract_episode_number("Frieren - 05 (1080p)") == 5

    def test_s_e_format(self):
        assert _extract_episode_number("Frieren S01E18 1080p") == 18

    def test_episode_word(self):
        assert _extract_episode_number("Episode 3 - Something") == 3

    def test_no_episode(self):
        assert _extract_episode_number("Frieren Batch Complete") is None
