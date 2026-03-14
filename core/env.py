"""
Environment variable loader.
Reads from .env file and os.environ.
"""

import os

_loaded = False


def _load_dotenv():
    """Load .env file from project root if it exists."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    # Walk up from this file to find .env
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):  # max 5 levels up
        env_path = os.path.join(current, ".env")
        if os.path.isfile(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)
            return
        current = os.path.dirname(current)


def get(key: str, default: str = "") -> str:
    """Get an environment variable, loading .env first if needed."""
    _load_dotenv()
    return os.environ.get(key, default)
