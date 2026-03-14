from core.interfaces.detection import BaseDetector
from core.features import is_available


def get_detector(name: str = "process", **kwargs) -> BaseDetector:
    detectors = {}
    if is_available("detection"):
        from core.detection.process import ProcessDetector
        detectors[ProcessDetector.get_name()] = ProcessDetector

    detector_cls = detectors.get(name)
    if detector_cls:
        return detector_cls(**kwargs)

    available = list(detectors.keys()) or ["none — install kitsune-core[detection]"]
    raise ValueError(f"Detector {name!r} not found. Available: {', '.join(available)}")
