"""
RSS feed entry matchers.

Decides whether an RSS entry should be downloaded based on rules
(regex patterns, filters) or LLM evaluation.
"""

import logging
import re
from typing import Optional

from core.interfaces.rss.matcher import BaseMatcher, MatchRule, LLMMatchRule
from core.interfaces.rss.extractor import FeedEntry

logger = logging.getLogger(__name__)


class RuleMatcher(BaseMatcher):
    """
    Rule-based matcher using regex patterns and filters.

    Usage:
        matcher = RuleMatcher([
            MatchRule(
                title_pattern=r"Frieren",
                resolution=["1080p"],
                release_group=["SubsPlease"],
            ),
            MatchRule(
                title_pattern=r"Dandadan",
                exclude_pattern=r"batch",
            ),
        ])

        if matcher.matches(entry):
            # download this entry
    """

    def __init__(self, rules: list[MatchRule] = None):
        self._rules = rules or []

    def add_rule(self, rule: MatchRule):
        self._rules.append(rule)

    def remove_rule(self, index: int):
        if 0 <= index < len(self._rules):
            self._rules.pop(index)

    @property
    def rules(self) -> list[MatchRule]:
        return list(self._rules)

    def matches(self, entry: FeedEntry) -> bool:
        """Return True if any rule matches the entry."""
        if not self._rules:
            return True  # no rules = accept everything

        return any(self._check_rule(entry, rule) for rule in self._rules)

    @staticmethod
    def _check_rule(entry: FeedEntry, rule: MatchRule) -> bool:
        title = entry.title

        # Title must match pattern
        if rule.title_pattern:
            if not re.search(rule.title_pattern, title, re.IGNORECASE):
                return False

        # Title must NOT match exclude pattern
        if rule.exclude_pattern:
            if re.search(rule.exclude_pattern, title, re.IGNORECASE):
                return False

        # Resolution filter
        if rule.resolution:
            title_lower = title.lower()
            if not any(res.lower() in title_lower for res in rule.resolution):
                return False

        # Release group filter
        if rule.release_group:
            title_lower = title.lower()
            if not any(group.lower() in title_lower for group in rule.release_group):
                return False

        # Episode range filter
        if rule.episode_range:
            episode = _extract_episode_number(title)
            if episode is not None:
                start, end = rule.episode_range
                if not (start <= episode <= end):
                    return False

        return True


class LLMMatcher(BaseMatcher):
    """
    Agentic LLM-based matcher with tool calling.

    The LLM can call tools to look up anime metadata, parse filenames,
    and gather information before deciding whether to download.

    Simple rules (just title matching) are answered directly.
    Complex rules (check score on AniList, verify studio, etc.) trigger
    tool calls automatically.

    Usage:
        from core.llm import get_llm_client

        # Simple rule — LLM answers directly
        matcher = LLMMatcher(
            rule=LLMMatchRule(
                prompt="Download only 1080p releases from SubsPlease"
            ),
            llm_client=get_llm_client(),
        )

        # Complex rule — LLM calls tools to check
        matcher = LLMMatcher(
            rule=LLMMatchRule(
                prompt="Download only if the anime has score > 8 on AniList "
                       "and is currently airing"
            ),
            llm_client=get_llm_client(),
        )
    """

    _SYSTEM = (
        "You are a download rule evaluator for an anime tracker.\n"
        "You have tools to search anime databases and parse filenames.\n"
        "Use them when the rule requires checking external data "
        "(scores, studios, airing status, etc.).\n"
        "After gathering all needed information, answer with ONLY 'yes' or 'no'."
    )

    def __init__(self, rule: LLMMatchRule, llm_client=None, **kwargs):
        self._rule = rule
        if llm_client is None:
            from core.llm import get_llm_client
            llm_client = get_llm_client(**kwargs)
        self._llm = llm_client

    def matches(self, entry: FeedEntry) -> bool:
        from core.llm.agent import LLMAgent

        agent = LLMAgent(self._llm)
        prompt = (
            f"Rule: {self._rule.prompt}\n\n"
            f"Entry title: {entry.title}\n\n"
            f"Should this entry be downloaded? "
            f"Use tools if needed, then answer 'yes' or 'no'."
        )

        try:
            result = agent.run(prompt, system=self._SYSTEM)
            answer = result["content"].strip().lower()
            if result["tool_calls_made"]:
                logger.info(
                    f"LLM matcher used {len(result['tool_calls_made'])} tool call(s) "
                    f"for '{entry.title}'"
                )
            return answer in ("yes", "y", "true")
        except Exception as e:
            logger.error(f"LLM matcher failed, defaulting to reject: {e}")
            return False


def _extract_episode_number(title: str) -> Optional[int]:
    """Try to extract an episode number from a title string."""
    # Common patterns: "- 05", "E05", "Episode 5", "S01E05"
    patterns = [
        r"(?:^|[\s\-])(\d{1,4})(?:\s|v\d|\[|\(|\.mkv|\.mp4|$)",  # "- 05" or standalone number
        r"[Ee](?:pisode\s*)?(\d{1,4})",     # E05, Episode 5
        r"[Ss]\d{1,2}[Ee](\d{1,4})",        # S01E05
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None
