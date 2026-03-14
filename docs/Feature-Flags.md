# Feature Flags

Kitsune Core uses Python optional dependencies (extras) to avoid pulling in unnecessary packages. At runtime, the `core.features` module provides guards to check availability and produce clear error messages.

## Available Features

| Feature | Extra | Key dependency | What it enables |
|---------|-------|---------------|-----------------|
| `tracker` | `pip install kitsune-core[tracker]` | anisearch | AniList API integration |
| `recognition` | `pip install kitsune-core[recognition]` | aniparse | Filename parsing |
| `downloader` | `pip install kitsune-core[downloader]` | qbittorrent-api, feedparser, psutil | RSS + torrent client |
| `detection` | `pip install kitsune-core[detection]` | psutil | Media player detection |
| `llm` | `pip install kitsune-core[llm]` | httpx | LLM endpoint integration |
| `server` | `pip install kitsune-core[server]` | fastapi, uvicorn | API server |
| `all` | `pip install kitsune-core[all]` | everything | All features |

## Runtime API

### `is_available(feature: str) -> bool`

Check if a feature's dependencies are installed without raising.

```python
from core.features import is_available

if is_available("tracker"):
    from core.tracker.services.anilist import AnilistTracker
```

### `require(feature: str) -> None`

Raise `ImportError` with install instructions if a feature is missing. Use at module level for hard dependencies.

```python
from core.features import require

require("downloader")
import qbittorrentapi  # safe — we know it's installed
```

**Error message:**
```
ImportError: Feature 'downloader' requires 'qbittorrentapi' which is not installed.
Install it with: pip install kitsune-core[downloader]
```

## Adding a New Feature

1. **Add the dependency** to `pyproject.toml` under `[project.optional-dependencies]`:
   ```toml
   my_feature = [
       "some-package>=1.0",
   ]
   ```

2. **Register the probe module** in `core/features.py`:
   ```python
   _FEATURE_MODULES = {
       ...
       "my_feature": "some_package",  # the import name to probe
   }
   ```

3. **Add to `all` extra** in `pyproject.toml`:
   ```toml
   all = [
       "kitsune-core[tracker,recognition,downloader,detection,llm,server,my_feature]",
   ]
   ```

4. **Guard your module** with `require()` at the top:
   ```python
   from core.features import require
   require("my_feature")
   import some_package
   ```

## Lazy Imports

For modules that are imported eagerly (like `core/client/__init__.py`), use `is_available()` with lazy imports to avoid triggering guards when the feature isn't needed:

```python
from core.features import is_available

def _get_clients():
    clients = {}
    if is_available("downloader"):
        from core.client.qbittorrent import QBittorrent
        clients[QBittorrent.get_name()] = QBittorrent
    return clients
```
