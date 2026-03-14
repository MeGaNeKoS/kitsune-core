"""
API server for kitsune-core.

Exposes core functionality (tracker, recognition, downloader, LLM)
to remote clients like browser extensions and desktop apps.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from core.features import is_available
from core.database.sqlite import DatabaseConnection
from core.tracker import get_local_tracker
from core.interfaces.tracker.local import BaseLocalTracker

# --- App state ---

_db: Optional[DatabaseConnection] = None


def _ensure_models_imported():
    """Ensure all models are imported so Base.metadata knows about them."""
    import core.interfaces.database.models.Media.local_media  # noqa
    import core.interfaces.database.models.Media.service_mapping  # noqa


def _get_db() -> DatabaseConnection:
    global _db
    if _db is None:
        configure_db("sqlite:///kitsune.db")
    return _db


def configure_db(db_url: str = "sqlite:///kitsune.db"):
    """Allow consumers to configure the database before starting."""
    global _db
    _ensure_models_imported()
    _db = DatabaseConnection(db_url)
    _db.create_tables()


app = FastAPI(title="kitsune-core", version="0.1.0")


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
def health():
    return {
        "status": "ok",
        "features": {
            name: is_available(name)
            for name in ["tracker", "recognition", "downloader", "detection", "llm"]
        },
    }


# --- Recognition ---

@app.post("/recognize", response_model=RecognitionResponse)
def recognize(req: RecognitionRequest):
    """Parse an anime title using aniparse or LLM."""
    recognizer_name = "llm" if req.use_llm else "aniparse"

    if req.use_llm and not is_available("llm"):
        raise HTTPException(400, "Feature 'llm' not installed")
    if not req.use_llm and not is_available("recognition"):
        raise HTTPException(400, "Feature 'recognition' not installed")

    from core.recognition import get_recognizer
    recognizer = get_recognizer(recognizer_name)
    result = recognizer.parse(req.title)
    return RecognitionResponse(parsed=dict(result), source=result.get("source", recognizer_name))


# --- Local Tracking ---

@app.get("/tracking/entries")
def list_entries(status: Optional[str] = None, media_type: Optional[str] = None,
                 tracker: BaseLocalTracker = Depends(get_tracker)):
    """List all local media entries."""
    from core.interfaces.database.types.media import MediaType, MediaStatus
    s = MediaStatus(status) if status else None
    t = MediaType(media_type) if media_type else None
    return tracker.list_entries(status=s, media_type=t)


@app.get("/tracking/entries/{media_id}")
def get_entry(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Get a single media entry."""
    try:
        return tracker.get_entry(media_id)
    except ValueError:
        raise HTTPException(404, f"Entry {media_id} not found")


@app.post("/tracking/entries")
def add_entry(req: TrackingAddRequest, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Add a new local media entry."""
    from core.interfaces.database.types.media import MediaType, MediaStatus
    return tracker.add_entry(
        title=req.title,
        media_type=MediaType(req.media_type),
        status=MediaStatus(req.status),
        progress=req.progress,
        total_episodes=req.total_episodes,
        score=req.score,
    )


@app.patch("/tracking/entries/{media_id}")
def update_entry(media_id: int, req: TrackingUpdateRequest,
                 tracker: BaseLocalTracker = Depends(get_tracker)):
    """Update a media entry."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    # Convert status string to enum if present
    if "status" in updates:
        from core.interfaces.database.types.media import MediaStatus
        updates["status"] = MediaStatus(updates["status"])

    try:
        return tracker.update_entry(media_id, **updates)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/tracking/entries/{media_id}")
def delete_entry(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Delete a media entry."""
    if not tracker.delete_entry(media_id):
        raise HTTPException(404, f"Entry {media_id} not found")
    return {"deleted": True}


@app.get("/tracking/entries/{media_id}/progress")
def get_progress(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Get current progress for an entry."""
    try:
        entry = tracker.get_entry(media_id)
        return {"media_id": media_id, "progress": entry["progress"],
                "total_episodes": entry["total_episodes"], "status": entry["status"]}
    except ValueError:
        raise HTTPException(404, f"Entry {media_id} not found")


@app.put("/tracking/entries/{media_id}/progress/{episode}")
def update_progress(media_id: int, episode: int,
                    tracker: BaseLocalTracker = Depends(get_tracker)):
    """Update episode progress. Auto-completes if at total."""
    try:
        return tracker.update_progress(media_id, episode)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/tracking/search")
def search_entries(q: str, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Search local entries by title."""
    return tracker.search(q)


# --- Service Mapping ---

@app.get("/tracking/entries/{media_id}/services")
def get_service_mappings(media_id: int, tracker: BaseLocalTracker = Depends(get_tracker)):
    """Get all service links for a local entry."""
    return tracker.get_service_mapping(media_id)


@app.post("/tracking/entries/{media_id}/services")
def link_service(media_id: int, req: TrackingLinkRequest,
                 tracker: BaseLocalTracker = Depends(get_tracker)):
    """Link a local entry to an external service."""
    try:
        return tracker.link_service(media_id, req.service_name, req.service_media_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/tracking/entries/{media_id}/services/{service_name}")
def unlink_service(media_id: int, service_name: str,
                   tracker: BaseLocalTracker = Depends(get_tracker)):
    """Unlink a service from a local entry."""
    if not tracker.unlink_service(media_id, service_name):
        raise HTTPException(404, f"No {service_name} mapping for entry {media_id}")
    return {"unlinked": True}


# --- Service Sync ---

@app.post("/tracking/sync")
def sync_with_service(req: ServiceSyncRequest,
                      tracker: BaseLocalTracker = Depends(get_tracker)):
    """Sync local tracker with an external service."""
    if not is_available("tracker"):
        raise HTTPException(400, "Feature 'tracker' not installed")

    from core.tracker import get_service_tracker
    from core.tracker.sync import SyncManager

    try:
        service = get_service_tracker(req.service, access_token=req.access_token)
    except ValueError as e:
        raise HTTPException(400, str(e))

    sync = SyncManager()
    result = sync.sync_from_service(tracker, service, req.user_id)
    return result


# --- Detection ---

@app.get("/detection/players", response_model=DetectionResponse)
def detect_players():
    """Detect running media players."""
    if not is_available("detection"):
        raise HTTPException(400, "Feature 'detection' not installed")

    from core.detection import get_detector
    detector = get_detector()
    return DetectionResponse(players=detector.detect())


# --- LLM ---

@app.post("/llm/complete", response_model=LLMCompleteResponse)
def llm_complete(req: LLMCompleteRequest):
    """Forward a prompt to the configured LLM endpoint."""
    if not is_available("llm"):
        raise HTTPException(400, "Feature 'llm' not installed")

    from core.llm import get_llm_client
    client = get_llm_client()
    kwargs = {}
    if req.model:
        kwargs["model"] = req.model
    result = client.complete(req.prompt, system=req.system, **kwargs)
    return LLMCompleteResponse(**result)
