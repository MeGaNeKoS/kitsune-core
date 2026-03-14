import pytest

from core.features import is_available, require


def test_known_features():
    for feature in ["tracker", "recognition", "downloader", "detection", "media", "llm", "server"]:
        # Should not raise
        is_available(feature)


def test_unknown_feature():
    with pytest.raises(ValueError, match="Unknown feature"):
        is_available("nonexistent")


def test_require_installed():
    # At least one should be installed in test env
    if is_available("recognition"):
        require("recognition")  # should not raise


def test_require_missing():
    # Monkey-patch to test missing feature
    from core import features
    original = features._FEATURE_MODULES.copy()
    features._FEATURE_MODULES["_test_missing"] = "nonexistent_module_xyz"
    try:
        with pytest.raises(ImportError, match="pip install"):
            require("_test_missing")
    finally:
        features._FEATURE_MODULES.clear()
        features._FEATURE_MODULES.update(original)
