"""
API server for kitsune-core.

Exposes core functionality (tracker, recognition, downloader, LLM)
to remote clients like browser extensions and desktop apps.

All endpoints are async. Sync operations (DB, tracker) run in
a threadpool automatically via FastAPI's dependency injection.
"""

import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from core.features import is_available
from core.database.sqlite import DatabaseConnection
from core.tracker import get_local_tracker
from core.interfaces.tracker.local import BaseLocalTracker
from core.server.auth import APIKeyMiddleware, configure_auth

# --- App state ---

_db: Optional[DatabaseConnection] = None


def _ensure_models_imported():
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa


def _get_db() -> DatabaseConnection:
    global _db
    if _db is None:
        configure_db("sqlite:///kitsune.db")
    return _db


def configure_db(db_url: str = "sqlite:///kitsune.db"):
    global _db
    _ensure_models_imported()
    _db = DatabaseConnection(db_url)
    _db.create_tables()


app = FastAPI(title="kitsune-core", version="0.1.0")
app.add_middleware(APIKeyMiddleware)


def get_session():
    session = _get_db().get_session()
    try:
        yield session
    finally:
        session.close()


def get_tracker(session=Depends(get_session)) -> BaseLocalTracker:
    return get_local_tracker(session)


# --- Request/Response Models ---

class RecognitionRequest(BaseModel):
    title: str
    use_llm: bool = False


class RecognitionResponse(BaseModel):
    parsed: dict
    source: str


class TrackingAddRequest(BaseModel):
    title: str
    media_type: str = "ANIME"
    status: str = "PLANNED"
    progress: int = 0
    total_episodes: Optional[int] = None
    score: Optional[float] = None


class TrackingUpdateRequest(BaseModel):
    progress: Optional[int] = None
    status: Optional[str] = None
    score: Optional[float] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class TrackingLinkRequest(BaseModel):
    service_name: str
    service_media_id: str


class ServiceSyncRequest(BaseModel):
    service: str = "anilist"
    user_id: str = ""
    access_token: str = ""


class RSSParseRequest(BaseModel):
    url: str


class RSSMatchRequest(BaseModel):
    title: str
    title_pattern: str = ""
    exclude_pattern: str = ""
    resolution: list[str] = []
    release_group: list[str] = []
    episode_range: Optional[list[int]] = None


class LLMCompleteRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    model: Optional[str] = None


class LLMCompleteResponse(BaseModel):
    content: str
    model: str
    usage: dict


class DetectionResponse(BaseModel):
    players: list[dict]


# --- Health ---

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "features": {
            name: is_available(name)
            for name in ["tracker", "recognition", "downloader", "detection", "media", "llm"]
        },
    }


# --- Recognition ---

@app.post("/recognize", response_model=RecognitionResponse)
async def recognize(req: RecognitionRequest):
    recognizer_name = "llm" if req.use_llm else "aniparse"

    if req.use_llm and not is_available("llm"):
        raise HTTPException(400, "Feature 'llm' not installed")
    if not req.use_llm and not is_available("recognition"):
        raise HTTPException(400, "Feature 'recognition' not installed")

    def _do():
        from core.recognition import get_recognizer
        recognizer = get_recognizer(recognizer_name)
        return recognizer.parse(req.title)

    result = await asyncio.to_thread(_do)
    return RecognitionResponse(parsed=dict(result), source=result.get("source", recognizer_name))


# --- Local Tracking ---

@app.get("/tracking/entries")
async def list_entries(status: Optional[str] = None, media_type: Optional[str] = None,
                       tracker: BaseLocalTracker = Depends(get_tracker)):
    from core.interfaces.database.types.media import MediaType, MediaStatus
    s = MediaStatus(status) if status else None
    t = MediaType(media_type) if media_type else None
    return await asyncio.to_thread(tracker.list_entries, status=s, media_type=t)


@app.get("/tracking/entries/{media_id}")
async def get_entry(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    try:
        return await asyncio.to_thread(tracker.get_entry, media_id)
    except ValueError:
        raise HTTPException(404, f"Entry {media_id} not found")


@app.post("/tracking/entries")
async def add_entry(req: TrackingAddRequest, tracker: BaseLocalTracker = Depends(get_tracker)):
    from core.interfaces.database.types.media import MediaType, MediaStatus

    def _do():
        return tracker.add_entry(
            title=req.title,
            media_type=MediaType(req.media_type),
            status=MediaStatus(req.status),
            progress=req.progress,
            total_episodes=req.total_episodes,
            score=req.score,
        )

    return await asyncio.to_thread(_do)


@app.patch("/tracking/entries/{media_id}")
async def update_entry(media_id: int, req: TrackingUpdateRequest,
                       tracker: BaseLocalTracker = Depends(get_tracker)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    if "status" in updates:
        from core.interfaces.database.types.media import MediaStatus
        updates["status"] = MediaStatus(updates["status"])

    try:
        return await asyncio.to_thread(tracker.update_entry, media_id, **updates)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/tracking/entries/{media_id}")
async def delete_entry(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    result = await asyncio.to_thread(tracker.delete_entry, media_id)
    if not result:
        raise HTTPException(404, f"Entry {media_id} not found")
    return {"deleted": True}


@app.get("/tracking/entries/{media_id}/progress")
async def get_progress(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    try:
        entry = await asyncio.to_thread(tracker.get_entry, media_id)
        return {"media_id": media_id, "progress": entry["progress"],
                "total_episodes": entry["total_episodes"], "status": entry["status"]}
    except ValueError:
        raise HTTPException(404, f"Entry {media_id} not found")


@app.put("/tracking/entries/{media_id}/progress/{episode}")
async def update_progress(media_id: int, episode: int,
                          tracker: BaseLocalTracker = Depends(get_tracker)):
    try:
        return await asyncio.to_thread(tracker.update_progress, media_id, episode)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/tracking/search")
async def search_entries(q: str, tracker: BaseLocalTracker = Depends(get_tracker)):
    return await asyncio.to_thread(tracker.search, q)


# --- Service Mapping ---

@app.get("/tracking/entries/{media_id}/services")
async def get_service_mappings(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    return await asyncio.to_thread(tracker.get_service_mapping, media_id)


@app.post("/tracking/entries/{media_id}/services")
async def link_service(media_id: int, req: TrackingLinkRequest,
                       tracker: BaseLocalTracker = Depends(get_tracker)):
    try:
        return await asyncio.to_thread(
            tracker.link_service, media_id, req.service_name, req.service_media_id
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/tracking/entries/{media_id}/services/{service_name}")
async def unlink_service(media_id: int, service_name: str,
                         tracker: BaseLocalTracker = Depends(get_tracker)):
    result = await asyncio.to_thread(tracker.unlink_service, media_id, service_name)
    if not result:
        raise HTTPException(404, f"No {service_name} mapping for entry {media_id}")
    return {"unlinked": True}


# --- Service Sync ---

@app.post("/tracking/sync")
async def sync_with_service(req: ServiceSyncRequest,
                            tracker: BaseLocalTracker = Depends(get_tracker)):
    if not is_available("tracker"):
        raise HTTPException(400, "Feature 'tracker' not installed")

    def _do():
        from core.tracker import get_service_tracker
        from core.tracker.sync import SyncManager
        service = get_service_tracker(req.service, access_token=req.access_token)
        sync = SyncManager()
        return sync.sync_from_service(tracker, service, req.user_id)

    try:
        return await asyncio.to_thread(_do)
    except ValueError as e:
        raise HTTPException(400, str(e))


# --- RSS ---

@app.post("/rss/parse")
async def rss_parse(req: RSSParseRequest):
    if not is_available("downloader"):
        raise HTTPException(400, "Feature 'downloader' not installed")

    def _do():
        from core.rss.extractor import Extractor
        extractor = Extractor()
        return extractor.extract_feed(req.url)

    entries = await asyncio.to_thread(_do)
    return {
        "feed_url": req.url,
        "count": len(entries),
        "entries": [
            {"title": e.title, "magnet_links": e.magnet_links,
             "info_hashes": e.info_hashes, "torrent_links": e.torrent_links}
            for e in entries
        ],
    }


@app.post("/rss/match")
async def rss_match(req: RSSMatchRequest):
    from core.rss.matcher import RuleMatcher
    from core.interfaces.rss import MatchRule, FeedEntry

    rule = MatchRule(
        title_pattern=req.title_pattern,
        exclude_pattern=req.exclude_pattern,
        resolution=req.resolution,
        release_group=req.release_group,
        episode_range=tuple(req.episode_range) if req.episode_range else None,
    )
    matcher = RuleMatcher([rule])
    entry = FeedEntry(title=req.title)

    return {"title": req.title, "matches": matcher.matches(entry)}


# --- Downloader ---

@app.get("/downloader/status")
async def downloader_status():
    if not is_available("downloader"):
        raise HTTPException(400, "Feature 'downloader' not installed")
    return {"available": True}


# --- Detection ---

@app.get("/detection/players", response_model=DetectionResponse)
async def detect_players():
    if not is_available("detection"):
        raise HTTPException(400, "Feature 'detection' not installed")

    def _do():
        from core.detection import get_detector
        return get_detector().detect()

    players = await asyncio.to_thread(_do)
    return DetectionResponse(players=players)


# --- LLM ---

@app.post("/llm/complete", response_model=LLMCompleteResponse)
async def llm_complete(req: LLMCompleteRequest):
    if not is_available("llm"):
        raise HTTPException(400, "Feature 'llm' not installed")

    def _do():
        from core.llm import get_llm_client
        client = get_llm_client()
        kwargs = {}
        if req.model:
            kwargs["model"] = req.model
        return client.complete(req.prompt, system=req.system, **kwargs)

    result = await asyncio.to_thread(_do)
    return LLMCompleteResponse(**result)
