# Downloader

The downloader module handles RSS feed monitoring and torrent client management for automated anime downloading.

## Architecture

```
RSS Feed ──► Extractor (find download links)
           ──► Matcher (should I download this?)
           ──► Recognizer (parse anime title)
           ──► Queue ──► Download Orchestrator ──► Torrent Client
                                │
                           ┌────┴─────┐
                           │BaseClient│
                           └────┬─────┘
                                │
                           QBittorrent
                        (future: Transmission, Deluge)
```

## RSS Pipeline

The RSS system is split into independent, testable components.

### Step 1: Extractor — "Where are the download links?"

**Interface:** `core/interfaces/rss/extractor.py` → `BaseExtractor`
**Implementation:** `core/rss/extractor.py` → `Extractor`

Extracts magnet links, torrent URLs, and info hashes from RSS feed entries.

**ExtractionRule** — declarative config per RSS source:

```python
from core.interfaces.rss import ExtractionRule

# Tell the extractor where nyaa.si puts its magnet links
rule = ExtractionRule(
    source="nyaa.si",
    magnet="link",              # RSS <link> contains the magnet
    info_hash="nyaa:infoHash",  # custom namespace field
)
```

Use dot notation for nested fields: `"links.0.href"`

If no rule matches, the extractor falls back to **regex auto-detection** — it scans the entire entry for magnet/torrent patterns. Most RSS feeds work fine with just the fallback.

**FeedEntry** — clean return type:

```python
@dataclass
class FeedEntry:
    title: str                          # entry title
    magnet_links: list[str] = []        # found magnet links
    info_hashes: list[str] = []         # found info hashes
    torrent_links: list[str] = []       # found .torrent URLs
    raw: dict = {}                      # original RSS entry
```

### Step 2: Matcher — "Should I download this?"

**Interface:** `core/interfaces/rss/matcher.py` → `BaseMatcher`
**Implementations:**
- `core/rss/matcher.py` → `RuleMatcher` (regex-based)
- `core/rss/matcher.py` → `LLMMatcher` (LLM-based)

#### RuleMatcher

All non-empty fields must match. Leave a field empty to skip that check.

```python
from core.interfaces.rss import MatchRule
from core.rss.matcher import RuleMatcher

matcher = RuleMatcher([
    # Download Frieren in 1080p from SubsPlease only
    MatchRule(
        title_pattern=r"Frieren",
        resolution=["1080p"],
        release_group=["SubsPlease"],
    ),
    # Download Dandadan episodes 1-12, skip batches
    MatchRule(
        title_pattern=r"Dandadan",
        exclude_pattern=r"batch|complete",
        episode_range=(1, 12),
    ),
])
```

**MatchRule fields:**

| Field | Type | Description |
|-------|------|-------------|
| `title_pattern` | str | Regex to match title (case-insensitive) |
| `exclude_pattern` | str | Regex to reject title |
| `resolution` | list[str] | e.g. `["1080p", "720p"]` |
| `release_group` | list[str] | e.g. `["SubsPlease", "Erai-raws"]` |
| `episode_range` | tuple[int, int] | `(start, end)` inclusive |

Multiple rules = OR logic (any rule matching is enough).

#### LLMMatcher

Natural language rules evaluated by an LLM endpoint:

```python
from core.interfaces.rss import LLMMatchRule
from core.rss.matcher import LLMMatcher
from core.llm import get_llm_client

matcher = LLMMatcher(
    rule=LLMMatchRule(
        prompt="Download only 1080p releases from trusted groups "
               "(SubsPlease, Erai-raws). Skip batch releases and re-encodes."
    ),
    llm_client=get_llm_client(),
)
```

### Step 3: Recognizer — "What anime is this?"

Uses the [Recognition module](Recognition.md) to parse the anime title from the filename. Optional — if not provided, raw title metadata is passed to the queue.

### Step 4: Queue

Matched entries are wrapped in `TorrentInfo` and enqueued for the download orchestrator.

## RSS Orchestrator

**File:** `core/rss/__init__.py` → `RSS`

Ties the pipeline together and runs on an interval:

```python
from core.rss import RSS
from core.rss.extractor import Extractor
from core.rss.matcher import RuleMatcher
from core.interfaces.rss import ExtractionRule, MatchRule
from core.recognition import get_recognizer
from core.collection.queue import QueueManager

rss = RSS(
    extractor=Extractor([
        ExtractionRule(source="nyaa.si", magnet="link"),
    ]),
    matcher=RuleMatcher([
        MatchRule(title_pattern=r"Frieren", resolution=["1080p"]),
    ]),
    queue_manager=QueueManager(),
    config={
        "check_interval_second": 600,
        "watch_list": {
            "frieren.log": "https://nyaa.si/?page=rss&q=frieren+1080p",
        },
    },
    recognizer=get_recognizer("aniparse"),
)

# Call periodically
rss.step()  # checks feeds if interval has elapsed
```

## Download Orchestrator

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

## Torrent Client

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
