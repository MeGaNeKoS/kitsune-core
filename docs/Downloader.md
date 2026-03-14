# Downloader

The downloader module handles RSS feed monitoring and torrent client management for automated anime downloading.

## Architecture

```
RSS Feed ──► RSSRuleParser ──► Queue ──► Download Orchestrator ──► Torrent Client
                                              │
                                         ┌────┴────┐
                                         │BaseClient│
                                         └────┬────┘
                                              │
                                         QBittorrent
                                      (future: Transmission, Deluge)
```

## Components

### RSS Parser

**File:** `core/rss/rule_parser.py` → `RSSRuleParser`

Monitors RSS feeds and extracts torrent links (magnet, .torrent, info hash) using configurable per-service parsing rules.

**Configuration format:**
```json
{
    "nyaa.si": {
        "magnet": {
            "fields": [
                {
                    "field": "link",
                    "pattern": "magnet:\\?xt=urn:btih:.*",
                    "sub_fields": []
                }
            ]
        }
    }
}
```

### Download Orchestrator

**File:** `core/downloader/__init__.py` → `Download`

Manages the download lifecycle:
1. Dequeues torrents from the named queue
2. Adds them to the torrent client
3. Monitors progress via concurrent threads
4. Fires events on state changes (queued, added, downloading, completed, error)

**Configuration:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `check_interval_second` | float | 10 | Polling interval for torrent status |
| `concurrent_download` | int | 3 | Max parallel downloads |
| `max_fail` | int | 3 | Retries before skipping a torrent |
| `queue` | str | "default" | Named queue to use |
| `client` | dict | {} | Torrent client config (see below) |

### Torrent Client

**Interface:** `core/interfaces/torrent/client/base.py` → `BaseClient`

Abstract interface for torrent client implementations. Each client must define:
- `AuthConfig` enum — required auth fields (host, port, username, password)
- `CustomConfig` enum — client-specific settings (category, tags)
- `_name` — client identifier string

### Methods

| Method | Description |
|--------|-------------|
| `connect()` | Connect/authenticate with the client |
| `add_torrent(torrent)` | Add a torrent to the client |
| `update_data(torrent)` | Refresh torrent state from client |
| `remove_torrent(hash, delete_files?)` | Remove a torrent |
| `set_file_priority(hash, file_id, priority)` | Set per-file download priority |
| `pause_torrent(hash)` | Pause a torrent |
| `resume_torrent(hash)` | Resume a torrent |

### Download Strategies

| Strategy | Behavior |
|----------|----------|
| `NORMAL` | Download all files simultaneously (client default) |
| `PRIORITY_BASED` | Gradually increase priority for next files as current ones complete |
| `ONE_AT_A_TIME` | Only download one file at a time, sequentially |

## QBittorrent Implementation

**File:** `core/client/qbittorrent.py` → `QBittorrent`
**Extra:** `downloader`

Wraps the [qbittorrent-api](https://pypi.org/project/qbittorrent-api/) library.

**Auth config:**
```json
{
    "name": "qbittorrent",
    "client_auth": {
        "username": "admin",
        "password": "adminadmin",
        "host": "localhost",
        "port": 8080
    }
}
```

Features:
- Rate-limited API calls via `RateLimitedClient` wrapper
- Exponential backoff retry logic
- Tag and category management
- Auto-detect and start the qBittorrent process if not running
- Per-file priority manipulation for sequential downloading

## Implementing a New Client

```python
from core.interfaces.torrent.client import Client, ClientConfig
from enum import Enum

class Transmission(Client):
    _name = "transmission"

    class AuthConfig(Enum):
        HOST = ClientConfig("host", str, "localhost", True)
        PORT = ClientConfig("port", int, 9091, True)

    class CustomConfig(Enum):
        DOWNLOAD_DIR = ClientConfig("download_dir", str, "", False)

    def connect(self) -> bool:
        ...

    def add_torrent(self, torrent) -> bool:
        ...

    # ... implement remaining methods
```

Register it in `core/client/__init__.py` to make it available via `get_client()`.

## Event System

The downloader fires events during the torrent lifecycle:

| Event | When |
|-------|------|
| `QUEUED` | Torrent enters the download queue |
| `ADDED` | Torrent successfully added to client |
| `DOWNLOADING` | Download in progress |
| `COMPLETED` | All files downloaded |
| `COMPLETED_FILES_CHANGES` | Individual file completed |
| `ERROR` | Torrent entered error state |
| `SEEDING_COMPLETED` | Seeding finished |
| `REMOVED` | Torrent removed from queue |
