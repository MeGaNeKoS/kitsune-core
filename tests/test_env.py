import os
import pytest
from core.env import get, _load_dotenv


def test_get_from_environ():
    os.environ["KITSUNE_TEST_VAR"] = "hello"
    try:
        assert get("KITSUNE_TEST_VAR") == "hello"
    finally:
        del os.environ["KITSUNE_TEST_VAR"]


def test_get_default():
    assert get("NONEXISTENT_VAR_XYZ", "fallback") == "fallback"


def test_get_empty_default():
    assert get("NONEXISTENT_VAR_XYZ") == ""


def test_load_dotenv_from_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_DOTENV_KEY=test_value\n")

    # Reset loader state
    import core.env as env_module
    env_module._loaded = False

    original_file = os.path.abspath(__file__)
    # Temporarily change module path to find the tmp .env
    old_file = env_module.__file__
    env_module.__file__ = str(tmp_path / "core" / "env.py")
    os.makedirs(os.path.dirname(env_module.__file__), exist_ok=True)

    try:
        env_module._load_dotenv()
        assert os.environ.get("TEST_DOTENV_KEY") == "test_value"
    finally:
        env_module.__file__ = old_file
        env_module._loaded = False
        os.environ.pop("TEST_DOTENV_KEY", None)
