"""
Quality scoring and upgrade decision logic.
"""

import re
import logging
from typing import Optional

from core.interfaces.upgrade.base import (
    BaseUpgradePolicy, QualityProfile, QualityTier, CodecTier, AudioTier,
    DownloadedFile,
)

logger = logging.getLogger(__name__)


# Patterns for extracting quality from filenames
_RESOLUTION_PATTERNS = {
    QualityTier.UHD: re.compile(r"(?:2160p|4[Kk]|UHD)", re.IGNORECASE),
    QualityTier.QHD: re.compile(r"1440p", re.IGNORECASE),
    QualityTier.FHD: re.compile(r"1080p", re.IGNORECASE),
    QualityTier.HD: re.compile(r"720p", re.IGNORECASE),
    QualityTier.SD: re.compile(r"(?:480p|576p|SD)", re.IGNORECASE),
}

_CODEC_PATTERNS = {
    CodecTier.AV1: re.compile(r"\bAV1\b", re.IGNORECASE),
    CodecTier.HEVC: re.compile(r"(?:HEVC|[Hh]\.?265|[Xx]265)", re.IGNORECASE),
    CodecTier.AVC: re.compile(r"(?:AVC|[Hh]\.?264|[Xx]264)", re.IGNORECASE),
}

_AUDIO_PATTERNS = {
    AudioTier.LOSSLESS: re.compile(r"(?:FLAC|TrueHD|DTS-HD)", re.IGNORECASE),
    AudioTier.MULTI: re.compile(r"(?:multi[\s\-]?audio|tri[\s\-]?audio)", re.IGNORECASE),
    AudioTier.DUAL: re.compile(r"(?:dual[\s\-]?audio|2audio|eng?\+jap?)", re.IGNORECASE),
}

_GROUP_PATTERN = re.compile(r"^\[([^\]]+)\]")


class UpgradePolicy(BaseUpgradePolicy):
    """
    Weighted quality scoring policy.

    Each quality attribute contributes: tier_value * weight.
    A release group match adds a flat bonus.

    Usage:
        profile = QualityProfile(
            resolution_preferred=QualityTier.FHD,
            codec_preferred=CodecTier.HEVC,
            preferred_groups=["SubsPlease"],
            upgrade_threshold=5,
        )
        policy = UpgradePolicy(profile)

        score_720p = policy.score(QualityTier.HD, CodecTier.AVC, AudioTier.MONO, "BadSubs")
        score_1080p = policy.score(QualityTier.FHD, CodecTier.HEVC, AudioTier.DUAL, "SubsPlease")
        # score_1080p >> score_720p → upgrade
    """

    def __init__(self, profile: QualityProfile):
        self._profile = profile

    @property
    def profile(self) -> QualityProfile:
        return self._profile

    def score(self, resolution: QualityTier, codec: CodecTier,
              audio: AudioTier, release_group: str) -> int:
        p = self._profile
        total = 0

        # Resolution: tier * weight, capped at preferred
        res_tier = min(resolution, p.resolution_preferred)
        total += res_tier * p.resolution_weight

        # Codec: tier * weight, capped at preferred
        codec_tier = min(codec, p.codec_preferred)
        total += codec_tier * p.codec_weight

        # Audio: tier * weight, capped at preferred
        audio_tier = min(audio, p.audio_preferred)
        total += audio_tier * p.audio_weight

        # Group bonus
        if release_group and p.preferred_groups:
            if release_group.lower() in [g.lower() for g in p.preferred_groups]:
                total += p.group_weight * 5  # flat bonus for preferred group

        return total

    def should_upgrade(self, current: DownloadedFile, candidate_score: int) -> bool:
        # Reject if current is already at or above preferred on all axes
        improvement = candidate_score - current.quality_score
        if improvement < self._profile.upgrade_threshold:
            return False
        return True

    def parse_quality(self, title: str, media_info: Optional[dict] = None) -> dict:
        """
        Extract quality from title string. If media_info (from pymediainfo probe)
        is provided, use actual values instead of filename guesses.
        """
        resolution = QualityTier.UNKNOWN
        codec = CodecTier.UNKNOWN
        audio = AudioTier.UNKNOWN
        release_group = ""

        # From filename
        for tier, pattern in _RESOLUTION_PATTERNS.items():
            if pattern.search(title):
                resolution = tier
                break

        for tier, pattern in _CODEC_PATTERNS.items():
            if pattern.search(title):
                codec = tier
                break

        for tier, pattern in _AUDIO_PATTERNS.items():
            if pattern.search(title):
                audio = tier
                break

        group_match = _GROUP_PATTERN.search(title)
        if group_match:
            release_group = group_match.group(1)

        # Override with actual media info if available
        if media_info:
            video = media_info.get("video", {})
            if video:
                height = video.get("height", 0)
                if height >= 2160:
                    resolution = QualityTier.UHD
                elif height >= 1440:
                    resolution = QualityTier.QHD
                elif height >= 1080:
                    resolution = QualityTier.FHD
                elif height >= 720:
                    resolution = QualityTier.HD
                elif height > 0:
                    resolution = QualityTier.SD

                codec_name = video.get("codec", "").upper()
                if "AV1" in codec_name:
                    codec = CodecTier.AV1
                elif "HEVC" in codec_name or "H265" in codec_name or "265" in codec_name:
                    codec = CodecTier.HEVC
                elif "AVC" in codec_name or "H264" in codec_name or "264" in codec_name:
                    codec = CodecTier.AVC

            audio_tracks = media_info.get("audio", [])
            if len(audio_tracks) >= 3:
                audio = AudioTier.MULTI
            elif len(audio_tracks) >= 2:
                audio = AudioTier.DUAL
            elif audio_tracks:
                codec_name = audio_tracks[0].get("codec", "").upper()
                if codec_name in ("FLAC", "TRUEHD", "DTS-HD"):
                    audio = AudioTier.LOSSLESS
                else:
                    audio = AudioTier.MONO

        return {
            "resolution": resolution,
            "codec": codec,
            "audio": audio,
            "release_group": release_group,
        }
