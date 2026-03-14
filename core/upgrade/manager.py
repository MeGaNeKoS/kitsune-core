"""
Upgrade manager — tracks downloaded files and decides when to replace them.

Maintains a registry of what we have, compares against new releases,
and triggers re-downloads when a better version is available.
"""

import logging
import os
from typing import Optional

from devlog import log_on_start, log_on_error

from core.interfaces.upgrade.base import (
    QualityProfile, QualityTier, CodecTier, AudioTier, DownloadedFile,
)
from core.upgrade.policy import UpgradePolicy

logger = logging.getLogger(__name__)


class UpgradeManager:
    """
    Tracks downloaded files and manages quality upgrades.

    Usage:
        profile = QualityProfile(
            resolution_preferred=QualityTier.FHD,
            codec_preferred=CodecTier.HEVC,
            preferred_groups=["SubsPlease"],
            upgrade_threshold=5,
        )
        manager = UpgradeManager(profile)

        # Register a downloaded file
        manager.register("Frieren", 5, "/downloads/Frieren - 05 (720p).mkv",
                         "[SubsPlease] Frieren - 05 (720p).mkv")

        # Later, check if a new release is an upgrade
        if manager.check_upgrade("Frieren", 5,
                                 "[SubsPlease] Frieren - 05 (1080p) HEVC.mkv"):
            # trigger re-download and replace
            ...
    """

    def __init__(self, profile: QualityProfile):
        self._policy = UpgradePolicy(profile)
        # Registry: {(title, episode): DownloadedFile}
        self._registry: dict[tuple[str, Optional[int]], DownloadedFile] = {}

    @property
    def policy(self) -> UpgradePolicy:
        return self._policy

    @property
    def registry(self) -> dict:
        return dict(self._registry)

    def register(self, title: str, episode: Optional[int], path: str,
                 release_title: str, media_info: Optional[dict] = None) -> DownloadedFile:
        """
        Register a downloaded file in the upgrade registry.

        Args:
            title: Anime title (normalized)
            episode: Episode number (None for movies)
            path: Path to the downloaded file
            release_title: Original release title (for quality parsing)
            media_info: Optional pymediainfo probe result for accurate quality
        """
        quality = self._policy.parse_quality(release_title, media_info)
        score = self._policy.score(
            quality["resolution"], quality["codec"],
            quality["audio"], quality["release_group"],
        )

        entry = DownloadedFile(
            path=path,
            title=title,
            episode=episode,
            resolution=quality["resolution"],
            codec=quality["codec"],
            audio=quality["audio"],
            release_group=quality["release_group"],
            quality_score=score,
        )

        key = (title.lower(), episode)
        self._registry[key] = entry
        logger.info(
            f"Registered: {title} ep={episode} "
            f"[{quality['resolution'].name} {quality['codec'].name} "
            f"{quality['audio'].name}] score={score}"
        )
        return entry

    def check_upgrade(self, title: str, episode: Optional[int],
                      candidate_title: str,
                      media_info: Optional[dict] = None) -> bool:
        """
        Check if a new release is an upgrade over what we have.

        Args:
            title: Anime title
            episode: Episode number
            candidate_title: The new release title to evaluate
            media_info: Optional media probe of the candidate

        Returns:
            True if the candidate is worth upgrading to.
        """
        key = (title.lower(), episode)
        current = self._registry.get(key)

        if current is None:
            # We don't have this episode at all — always download
            return True

        quality = self._policy.parse_quality(candidate_title, media_info)

        # Check minimum resolution
        if quality["resolution"] < self._policy.profile.resolution_min:
            return False

        candidate_score = self._policy.score(
            quality["resolution"], quality["codec"],
            quality["audio"], quality["release_group"],
        )

        should = self._policy.should_upgrade(current, candidate_score)
        if should:
            logger.info(
                f"Upgrade available for {title} ep={episode}: "
                f"score {current.quality_score} -> {candidate_score} "
                f"({candidate_title})"
            )
        return should

    @log_on_error(logging.ERROR, "Failed to replace file: {error!r}")
    def replace(self, title: str, episode: Optional[int],
                new_path: str, new_release_title: str,
                media_info: Optional[dict] = None,
                delete_old: bool = True) -> DownloadedFile:
        """
        Replace a downloaded file with a better version.

        Args:
            title: Anime title
            episode: Episode number
            new_path: Path to the new file
            new_release_title: Release title of the new version
            media_info: Optional media probe
            delete_old: Whether to delete the old file

        Returns:
            The new DownloadedFile entry.
        """
        key = (title.lower(), episode)
        old = self._registry.get(key)

        if old and delete_old and os.path.isfile(old.path):
            logger.info(f"Deleting old file: {old.path}")
            os.remove(old.path)

        return self.register(title, episode, new_path, new_release_title, media_info)

    def get_current(self, title: str, episode: Optional[int]) -> Optional[DownloadedFile]:
        """Get the currently registered file for a title/episode."""
        return self._registry.get((title.lower(), episode))

    def list_upgradeable(self) -> list[DownloadedFile]:
        """List all files that are below their preferred quality."""
        p = self._policy.profile
        preferred_score = self._policy.score(
            p.resolution_preferred, p.codec_preferred,
            p.audio_preferred, "",
        )
        return [
            f for f in self._registry.values()
            if f.quality_score < preferred_score
        ]
