import platform
import pytest

from core.features import is_available


@pytest.mark.skipif(not is_available("detection"), reason="psutil not installed")
def test_process_detector():
    from core.detection import get_detector
    detector = get_detector("process")
    players = detector.detect()
    assert isinstance(players, list)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_window_title_detector():
    from core.detection import get_detector
    detector = get_detector("window_title")
    players = detector.detect()
    assert isinstance(players, list)


@pytest.mark.skipif(not is_available("detection"), reason="psutil not installed")
def test_process_detector_custom_players():
    from core.detection.process import ProcessDetector
    detector = ProcessDetector(extra_players={"custom_player": ["custom.exe"]})
    assert "custom_player" in detector._players


def test_detector_factory_error():
    with pytest.raises(ValueError, match="not found"):
        from core.detection import get_detector
        get_detector("nonexistent")
