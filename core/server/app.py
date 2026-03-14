"""
API server for kitsune-core.

Exposes core functionality (tracker, recognition, downloader, LLM)
to remote clients like browser extensions and desktop apps.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.features import is_available

app = FastAPI(title="kitsune-core", version="0.1.0")


# --- Models ---

class RecognitionRequest(BaseModel):
    title: str
    use_llm: bool = False


class RecognitionResponse(BaseModel):
    parsed: dict
    source: str  # "aniparse" or "llm"


class TrackingUpdateRequest(BaseModel):
    media_id: int
    progress: int  # episode number
    service: str = "anilist"


class TrackingUpdateResponse(BaseModel):
    success: bool
    media_id: int
    progress: int


class DetectionResponse(BaseModel):
    players: list[dict]


# --- Endpoints ---

@app.get("/health")
def health():
    """Health check with available features."""
    return {
        "status": "ok",
        "features": {
            name: is_available(name)
            for name in ["tracker", "recognition", "downloader", "detection", "llm"]
        },
    }


@app.post("/recognize", response_model=RecognitionResponse)
def recognize(req: RecognitionRequest):
    """Parse an anime title using aniparse or LLM."""
    if req.use_llm:
        if not is_available("llm"):
            raise HTTPException(400, "Feature 'llm' not installed")
        # TODO: implement LLM-based recognition
        raise HTTPException(501, "LLM recognition not yet implemented")

    if not is_available("recognition"):
        raise HTTPException(400, "Feature 'recognition' not installed")

    from core.helper.recognition import parse
    result = parse(req.title, track=False)
    return RecognitionResponse(parsed=result, source="aniparse")


@app.post("/tracking/update", response_model=TrackingUpdateResponse)
def update_tracking(req: TrackingUpdateRequest):
    """Update watch progress on a tracking service."""
    if not is_available("tracker"):
        raise HTTPException(400, "Feature 'tracker' not installed")

    # TODO: implement via anisearch
    raise HTTPException(501, "Tracking update not yet implemented")


@app.get("/detection/players", response_model=DetectionResponse)
def detect_players():
    """Detect running media players."""
    if not is_available("detection"):
        raise HTTPException(400, "Feature 'detection' not installed")

    from core.detection.process import find_running_players
    return DetectionResponse(players=find_running_players())
