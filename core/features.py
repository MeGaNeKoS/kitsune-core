"""
Feature flags for optional dependencies.

Usage:
    from core.features import require, is_available

    # Check availability
    if is_available("tracker"):
        ...

    # Guard a function (raises on missing feature)
    require("downloader")
"""

from importlib.util import find_spec

_FEATURE_MODULES = {
    "tracker": "anisearch",
    "recognition": "aniparse",
    "downloader": "qbittorrentapi",
    "detection": "psutil",
    "llm": "httpx",
    "server": "fastapi",
}


def is_available(feature: str) -> bool:
    """Check if an optional feature's dependencies are installed."""
    module = _FEATURE_MODULES.get(feature)
    if module is None:
        raise ValueError(f"Unknown feature: {feature!r}")
    return find_spec(module) is not None


def require(feature: str) -> None:
    """Raise ImportError with install instructions if feature is missing."""
    if not is_available(feature):
        module = _FEATURE_MODULES[feature]
        raise ImportError(
            f"Feature '{feature}' requires '{module}' which is not installed. "
            f"Install it with: pip install kitsune-core[{feature}]"
        )
