from core.interfaces.upgrade.base import (
    QualityProfile, QualityTier, CodecTier, AudioTier,
)
from core.upgrade import UpgradePolicy, UpgradeManager


def _default_profile():
    return QualityProfile(
        resolution_preferred=QualityTier.FHD,
        codec_preferred=CodecTier.HEVC,
        audio_preferred=AudioTier.DUAL,
        preferred_groups=["SubsPlease"],
        upgrade_threshold=5,
    )


class TestUpgradePolicy:

    def test_higher_resolution_scores_higher(self):
        policy = UpgradePolicy(_default_profile())
        s720 = policy.score(QualityTier.HD, CodecTier.AVC, AudioTier.MONO, "")
        s1080 = policy.score(QualityTier.FHD, CodecTier.AVC, AudioTier.MONO, "")
        assert s1080 > s720

    def test_hevc_scores_higher_than_avc(self):
        policy = UpgradePolicy(_default_profile())
        s_avc = policy.score(QualityTier.FHD, CodecTier.AVC, AudioTier.MONO, "")
        s_hevc = policy.score(QualityTier.FHD, CodecTier.HEVC, AudioTier.MONO, "")
        assert s_hevc > s_avc

    def test_preferred_group_bonus(self):
        policy = UpgradePolicy(_default_profile())
        s_no_group = policy.score(QualityTier.FHD, CodecTier.HEVC, AudioTier.DUAL, "Random")
        s_preferred = policy.score(QualityTier.FHD, CodecTier.HEVC, AudioTier.DUAL, "SubsPlease")
        assert s_preferred > s_no_group

    def test_parse_quality_from_title(self):
        policy = UpgradePolicy(_default_profile())
        q = policy.parse_quality("[SubsPlease] Frieren - 05 (1080p) x265 Dual Audio.mkv")
        assert q["resolution"] == QualityTier.FHD
        assert q["codec"] == CodecTier.HEVC
        assert q["audio"] == AudioTier.DUAL
        assert q["release_group"] == "SubsPlease"

    def test_parse_quality_480p(self):
        policy = UpgradePolicy(_default_profile())
        q = policy.parse_quality("[BadSubs] Frieren - 01 (480p).mkv")
        assert q["resolution"] == QualityTier.SD


class TestUpgradeManager:

    def test_new_episode_always_downloads(self):
        manager = UpgradeManager(_default_profile())
        assert manager.check_upgrade("Frieren", 5, "Frieren - 05 (720p).mkv")

    def test_same_quality_no_upgrade(self):
        manager = UpgradeManager(_default_profile())
        manager.register("Frieren", 5, "/d/f05.mkv", "[SubsPlease] Frieren - 05 (720p).mkv")
        assert not manager.check_upgrade("Frieren", 5, "[SubsPlease] Frieren - 05 (720p).mkv")

    def test_better_quality_triggers_upgrade(self):
        manager = UpgradeManager(_default_profile())
        manager.register("Frieren", 5, "/d/f05.mkv", "[SubsPlease] Frieren - 05 (720p).mkv")
        assert manager.check_upgrade("Frieren", 5, "[SubsPlease] Frieren - 05 (1080p) HEVC.mkv")

    def test_list_upgradeable(self):
        manager = UpgradeManager(_default_profile())
        manager.register("Frieren", 1, "/d/f01.mkv", "[BadSubs] Frieren - 01 (480p).mkv")
        manager.register("Frieren", 2, "/d/f02.mkv", "[SubsPlease] Frieren - 02 (1080p) HEVC Dual Audio.mkv")
        upgradeable = manager.list_upgradeable()
        assert len(upgradeable) == 1
        assert upgradeable[0].episode == 1
