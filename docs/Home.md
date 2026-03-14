# Kitsune Core

Kitsune Core is a modular anime tracking and download automation library for Python. It serves as the backend brain for any frontend — CLI, desktop app, or browser extension.

## Architecture

```
Browser Extension ──┐
Desktop App ────────┼──► kitsune-core (server) ──► AniList / MAL / AniDB / LLM / qBittorrent
CLI ────────────────┘
```

All logic lives in the core. Remote clients connect via the API server and interact with tracking, recognition, downloading, and LLM features.

## Modules

| Module | Description | Page |
|--------|-------------|------|
| [Tracker](Tracker.md) | Local media tracking + cloud service sync | AniList, MAL, AniDB, Kitsu |
| [Recognition](Recognition.md) | Anime title parsing from filenames | aniparse, LLM |
| [Downloader](Downloader.md) | RSS monitoring + torrent client management | qBittorrent |
| [Detection](Detection.md) | Media player process detection | Process-based, window title |
| [LLM](LLM.md) | LLM endpoint integration | OpenAI-compatible |
| [Server](Server.md) | API server for remote clients | FastAPI |
| [Database](Database.md) | Data models and schema | SQLAlchemy + SQLite |

## Feature Flags

Kitsune Core uses Python optional dependencies (extras) so users install only what they need:

```bash
pip install kitsune-core                # base only (devlog, sqlalchemy, urllib3)
pip install kitsune-core[tracker]       # + anisearch (AniList wrapper)
pip install kitsune-core[recognition]   # + aniparse (filename parser)
pip install kitsune-core[downloader]    # + feedparser, qbittorrent-api, psutil
pip install kitsune-core[detection]     # + psutil (media player detection)
pip install kitsune-core[llm]           # + httpx (LLM endpoint calls)
pip install kitsune-core[server]        # + fastapi, uvicorn (API server)
pip install kitsune-core[all]           # everything
```

See [Feature Flags](Feature-Flags.md) for details on runtime guards and how to add new features.

## Design Principles

1. **Abstract + Implementation** — Every module has an abstract interface (`core/interfaces/`) and swappable implementations (`core/`). Adding a new service or client means implementing one class.
2. **Local is source of truth** — The local database owns the user's data. Cloud services sync from/to local.
3. **No bloat** — Users opt into features. Unused features don't pull in dependencies.
4. **Logging safety** — python-devlog decorators with `sanitize_params` ensure credentials never leak into logs.
