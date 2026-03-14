# Database

Kitsune Core uses SQLAlchemy with SQLite as the default database. All models inherit from a shared `declarative_base()`.

## Schema Overview

```
┌───────────────┐      ┌─────────────────────┐      ┌──────────────┐
│  LocalMedia   │──1:N─│ ServiceMediaMapping  │      │ AnilistMedia │
│  (source of   │      │ (correlates local    │      │ (cached API  │
│   truth)      │      │  to service IDs)     │      │  data)       │
└───────────────┘      └─────────────────────┘      └──────────────┘
                                                          │
                                              ┌───────────┴──────────┐
                                              │                      │
                                     AnilistMediaTitle    AnilistAiringSchedule

┌──────────────┐
│ ServiceCreds │ (OAuth tokens per user per service)
│              │──1:N── AnilistUserEntry
└──────────────┘
```

## Tables

### LocalMedia

The source of truth for the user's media tracking state.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment internal ID |
| `title` | STRING | Canonical title |
| `media_type` | ENUM(MediaType) | ANIME or MANGA |
| `status` | ENUM(MediaStatus) | WATCHING, COMPLETED, PLANNED, DROPPED, PAUSED, REPEATING |
| `progress` | INTEGER | Current episode/chapter number |
| `total_episodes` | INTEGER? | Total known episodes (null if unknown) |
| `score` | FLOAT? | User's score |
| `start_date` | INTEGER? | Unix timestamp when started |
| `end_date` | INTEGER? | Unix timestamp when completed |
| `notes` | TEXT? | User notes |
| `file_path` | STRING? UNIQUE | Local file path if applicable |
| `created_at` | INTEGER | Unix timestamp, auto-set |
| `updated_at` | INTEGER | Unix timestamp, auto-updated on change |

### ServiceMediaMapping

Maps local entries to external service IDs. One local entry can link to multiple services.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `local_media_id` | INTEGER FK → LocalMedia.id | The local entry |
| `service_name` | ENUM(ServiceName) | AniList, MyAnimeList, Kitsu, AniDB |
| `service_media_id` | STRING | The ID on the external service |

**Unique constraint:** `(local_media_id, service_name)` — one mapping per service per local entry.

**Why `service_media_id` is a string:** Different services use different ID formats. AniList uses integers, AniDB uses integers in different ranges, Kitsu sometimes uses slugs.

### AnilistMedia

Cached metadata from the AniList API. Not the source of truth — this is a cache for display and offline access.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | AniList media ID |
| `idMal` | INTEGER? | Corresponding MAL ID (from AniList) |
| `type` | ENUM | ANIME, MANGA |
| `format` | ENUM | TV, MOVIE, OVA, ONA, etc. |
| `status` | ENUM | FINISHED, RELEASING, NOT_YET_RELEASED, etc. |
| `episodes` | INTEGER? | Total episodes |
| `season` | ENUM? | WINTER, SPRING, SUMMER, FALL |
| `seasonYear` | INTEGER? | Year |
| ... | ... | See `core/interfaces/database/models/Media/anilist.py` for full schema |

### AnilistMediaTitle

Multi-language titles for AniList media.

| Column | Type |
|--------|------|
| `media_id` | INTEGER FK PK → AnilistMedia.id |
| `romaji` | STRING? |
| `english` | STRING? |
| `native` | STRING? |

### AnilistAiringSchedule

Next airing episode info for currently releasing anime.

| Column | Type |
|--------|------|
| `media_id` | INTEGER FK PK → AnilistMedia.id |
| `airingAt` | INTEGER (unix timestamp) |
| `episode` | INTEGER |

### ServiceCreds

OAuth credentials per user per service.

See `core/interfaces/database/models/Service/__init__.py` for the full schema.

### AnilistUserEntry

User's anime list entries synced from AniList.

See `core/interfaces/database/models/Service/anilist.py` for the full schema.

## Enums

### MediaType
`ANIME`, `MANGA`

### MediaStatus
`WATCHING`, `COMPLETED`, `PLANNED`, `DROPPED`, `PAUSED`, `REPEATING`

### ServiceName
`ANILIST`, `MYANIMELIST`, `KITSU`, `ANIDB`

## Usage

```python
from core.database.sqlite import DatabaseConnection

# In-memory (testing)
db = DatabaseConnection()

# File-based
db = DatabaseConnection("sqlite:///kitsune.db")

# Create tables
db.create_tables()

# Get a session
session = db.get_session()
```

The `DatabaseConnection` class uses `scoped_session` for thread safety. Consumers are responsible for configuring log handlers and rotation.
