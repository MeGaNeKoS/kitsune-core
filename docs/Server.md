# Server

The server module exposes kitsune-core's functionality via a REST API, allowing remote clients (browser extensions, desktop apps) to interact with all features.

**Extra:** `server` (installs FastAPI + uvicorn)

## Architecture

```
Browser Extension ──┐
Desktop App ────────┼──► FastAPI Server ──► Tracker / Recognition / LLM / etc.
CLI ────────────────┘        │
                         /health
                         /recognize
                         /tracking/*
                         /detection/*
                         /llm/*
                         /download/*
```

## Running the Server

```bash
# Install with server extra
pip install kitsune-core[server]

# Run with uvicorn
uvicorn core.server.app:app --host 0.0.0.0 --port 8000
```

## Endpoints

### Health

```
GET /health
```

Returns server status and available features:
```json
{
    "status": "ok",
    "features": {
        "tracker": true,
        "recognition": true,
        "downloader": false,
        "detection": true,
        "llm": true
    }
}
```

### Recognition

```
POST /recognize
```

Parse an anime title using aniparse or LLM.

**Request:**
```json
{
    "title": "[SubsPlease] Frieren - 05 (1080p).mkv",
    "use_llm": false
}
```

**Response:**
```json
{
    "parsed": {
        "anime_title": "Frieren",
        "episode_number": 5,
        "video_resolution": "1080p",
        "release_group": "SubsPlease"
    },
    "source": "aniparse"
}
```

### Tracking

```
POST /tracking/update
```

Update watch progress on a tracking service.

**Request:**
```json
{
    "media_id": 154587,
    "progress": 9,
    "service": "anilist"
}
```

### Detection

```
GET /detection/players
```

Detect running media players.

**Response:**
```json
{
    "players": [
        {
            "player": "mpv",
            "pid": 12345,
            "title": "Frieren - 05.mkv"
        }
    ]
}
```

## Feature Gating

Every endpoint checks if its required feature is installed. If not, it returns a `400` with an install instruction:

```json
{
    "detail": "Feature 'recognition' not installed"
}
```

## Browser Extension Integration

The server is designed to be the backend for a browser extension. The extension can:

1. **Detect what the user is watching** — Send the page title/URL for recognition
2. **Update tracking** — Push episode progress to AniList/MAL
3. **Use LLM** — Forward LLM requests through the server (so the extension works standalone without a full kitsune-core install, just needing an LLM endpoint)

The extension communicates over HTTP to `localhost:8000` (or a configured remote server).
