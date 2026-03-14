# Tracker

The tracker module handles two concerns: **local media tracking** and **cloud service synchronization**.

## Architecture

```
┌──────────────────┐     ┌───────────────────┐
│  BaseLocalTracker│     │ BaseServiceTracker│
│  (local DB)      │◄───►│ (cloud APIs)      │
└────────┬─────────┘     └───────┬───────────┘
         │                       │
         └───────┬───────────────┘
                 │
          ┌──────▼────────┐
          │BaseSyncManager│
          └───────────────┘
```

## Local Tracker

**Interface:** `core/interfaces/tracker/local.py` → `BaseLocalTracker`

The local tracker operates on the `LocalMedia` table. It is the source of truth for the user's watch state.

### Methods

| Method | Description |
|--------|-------------|
| `get_entry(media_id)` | Get a single media entry by local ID |
| `list_entries(status?, media_type?)` | List entries with optional filters |
| `add_entry(title, media_type, **kwargs)` | Create a new media entry |
| `update_progress(media_id, progress)` | Update episode/chapter progress |
| `update_status(media_id, status)` | Update watch/read status |
| `update_entry(media_id, **kwargs)` | Update arbitrary fields |
| `delete_entry(media_id)` | Delete a media entry |
| `search(query)` | Search local entries by title |
| `link_service(media_id, service_name, service_media_id)` | Link to an external service |
| `unlink_service(media_id, service_name)` | Remove a service link |
| `get_service_mapping(media_id)` | Get all service mappings for an entry |

### Status Values

Defined in `core/interfaces/database/types/media.py` → `MediaStatus`:

- `WATCHING` — Currently watching/reading
- `COMPLETED` — Finished
- `PLANNED` — Plan to watch/read
- `DROPPED` — Dropped
- `PAUSED` — On hold
- `REPEATING` — Rewatching/rereading

## Service Tracker

**Interface:** `core/interfaces/tracker/service.py` → `BaseServiceTracker`

Each cloud service (AniList, MAL, AniDB, Kitsu) implements this interface. Implementations wrap the service's API.

### Methods

| Method | Description |
|--------|-------------|
| `authenticate(**kwargs)` | Authenticate with the service (OAuth, API key, etc.) |
| `get_user_list(user_id, status?)` | Fetch the user's media list |
| `get_media(media_id)` | Fetch metadata for a specific media |
| `search_media(query)` | Search for media on the service |
| `update_entry(media_id, progress, status?, score?)` | Update a user's entry |
| `delete_entry(media_id)` | Delete a user's entry |

### Implementing a New Service

```python
from core.interfaces.tracker.service import BaseServiceTracker

class MyAnimeListTracker(BaseServiceTracker):
    _name = "mal"

    def authenticate(self, **kwargs) -> bool:
        # OAuth2 flow for MAL
        ...

    def get_user_list(self, user_id, status=None):
        # GET https://api.myanimelist.net/v2/users/{user_id}/animelist
        ...

    # ... implement remaining methods
```

### Supported Services

| Service | Status | Extra |
|---------|--------|-------|
| AniList | Planned (existing code to wrap) | `tracker` |
| MyAnimeList | Planned | `tracker` |
| Kitsu | Planned | `tracker` |
| AniDB | Planned | `tracker` |

## Sync Manager

**Interface:** `core/interfaces/tracker/sync.py` → `BaseSyncManager`

Orchestrates bidirectional synchronization between the local tracker and service trackers.

### Methods

| Method | Description |
|--------|-------------|
| `sync_from_service(local, service, user_id)` | Pull from service → merge into local |
| `sync_to_service(local, service, user_id)` | Push local changes → service |
| `resolve_conflict(local_entry, remote_entry)` | Decide which version wins |

### Sync Flow

```
1. Fetch user list from service
2. For each remote entry:
   a. Find local entry via ServiceMediaMapping
   b. If no local entry → create one, link it
   c. If local entry exists → compare, resolve conflicts
3. For each local entry linked to this service:
   a. If not in remote list → push to service (or mark deleted)
```

### SyncResult

```python
class SyncResult(TypedDict):
    added: int       # new entries created
    updated: int     # entries modified
    deleted: int     # entries removed
    conflicts: int   # conflicts encountered
    errors: list[str]
```

## Service Mapping

The `ServiceMediaMapping` table correlates local entries with external service IDs:

| local_media_id | service_name | service_media_id |
|---|---|---|
| 1 | AniList | 154587 |
| 1 | MyAnimeList | 52991 |
| 1 | AniDB | 17617 |

One local entry can link to multiple services. The `service_media_id` is a string to accommodate different ID formats across services.

See [Database](Database.md) for the full schema.
