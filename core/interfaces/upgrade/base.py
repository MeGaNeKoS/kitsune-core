"""
Quality upgrade system interface.

Downloads what's available now, replaces when something better appears.

Flow:
    1. RSS finds "[SubsPlease] Frieren - 05 (720p)" → download
    2. Later, "[SubsPlease] Frieren - 05 (1080p) HEVC" appears
    3. Upgrade policy says 1080p HEVC > 720p → replace
    4. Old file deleted, new one downloaded

The upgrade policy compares quality scores to decide if a new release
is worth replacing the current one.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class QualityTier(IntEnum):
    """Quality tiers ordered from lowest to highest."""
    UNKNOWN = 0
    SD = 1       # 480p and below
    HD = 2       # 720p
    FHD = 3      # 1080p
    QHD = 4      # 1440p
    UHD = 5      # 4K / 2160p


class CodecTier(IntEnum):
    UNKNOWN = 0
    AVC = 1      # H.264
    HEVC = 2     # H.265
    AV1 = 3


class AudioTier(IntEnum):
    UNKNOWN = 0
    MONO = 1     # single audio
    DUAL = 2     # dual audio
    MULTI = 3    # multi audio
    LOSSLESS = 4 # FLAC / lossless


@dataclass
class QualityProfile:
    """
    Defines what quality attributes matter and their priority.

    Higher weight = more important in upgrade decisions.
    Set a minimum to reject anything below that tier.
    Set a preferred to stop upgrading once reached.

    Example — prioritize resolution, prefer HEVC, want dual audio:
        QualityProfile(
            resolution_weight=10,
            resolution_min=QualityTier.HD,
            resolution_preferred=QualityTier.FHD,
            codec_weight=5,
            codec_preferred=CodecTier.HEVC,
            audio_weight=3,
            audio_preferred=AudioTier.DUAL,
            preferred_groups=["SubsPlease", "Erai-raws"],
            group_weight=2,
        )
    """
    # Resolution
    resolution_weight: int = 10
    resolution_min: QualityTier = QualityTier.UNKNOWN
    resolution_preferred: QualityTier = QualityTier.FHD

    # Codec
    codec_weight: int = 5
    codec_preferred: CodecTier = CodecTier.HEVC

    # Audio
    audio_weight: int = 3
    audio_preferred: AudioTier = AudioTier.DUAL

    # Release group
    preferred_groups: list[str] = field(default_factory=list)
    group_weight: int = 2

    # Minimum score improvement required to trigger an upgrade
    upgrade_threshold: int = 5


@dataclass
class DownloadedFile:
    """Represents a file we currently have on disk."""
    path: str
    title: str                        # anime title
    episode: Optional[int] = None
    resolution: QualityTier = QualityTier.UNKNOWN
    codec: CodecTier = CodecTier.UNKNOWN
    audio: AudioTier = AudioTier.UNKNOWN
    release_group: str = ""
    quality_score: int = 0            # computed score


class BaseUpgradePolicy(ABC):
    """
    Decides whether a new release should replace an existing download.
    """

    @abstractmethod
    def score(self, resolution: QualityTier, codec: CodecTier,
              audio: AudioTier, release_group: str) -> int:
        """Compute a quality score for a release."""
        ...

    @abstractmethod
    def should_upgrade(self, current: DownloadedFile,
                       candidate_score: int) -> bool:
        """Return True if the candidate is enough of an improvement."""
        ...

    @abstractmethod
    def parse_quality(self, title: str, media_info: Optional[dict] = None) -> dict:
        """
        Extract quality attributes from a title and optional media probe.

        Returns:
            {"resolution": QualityTier, "codec": CodecTier,
             "audio": AudioTier, "release_group": str}
        """
        ...
