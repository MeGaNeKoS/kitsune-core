"""
Media-level file probing using pymediainfo.
Extracts actual codec, bitrate, resolution, audio tracks, subtitle tracks, etc.

Requires: pip install kitsune-core[media]
"""

import logging
from typing import Optional

from core.features import is_available

logger = logging.getLogger(__name__)


def get_media_info(path: str) -> dict:
    """
    Probe a media file for detailed technical metadata.

    Returns:
        {
            "path": str,
            "duration_seconds": float,
            "duration_display": str,       # "24:05"
            "overall_bitrate_kbps": int,
            "container": str,              # "Matroska"
            "video": {
                "codec": str,              # "HEVC", "AVC", "AV1"
                "width": int,
                "height": int,
                "resolution": str,         # "1920x1080"
                "display_resolution": str,  # "1080p"
                "framerate": float,
                "bitrate_kbps": int,
                "bit_depth": int,           # 8, 10
                "hdr": bool,
            },
            "audio": [
                {
                    "codec": str,          # "AAC", "FLAC", "Opus"
                    "channels": int,
                    "language": str,
                    "bitrate_kbps": int,
                    "title": str,          # track title if set
                }
            ],
            "subtitles": [
                {
                    "codec": str,          # "ASS", "SRT", "PGS"
                    "language": str,
                    "title": str,
                    "forced": bool,
                }
            ],
        }

    Returns minimal dict with error if pymediainfo is not installed or file not found.
    """
    if not is_available("media"):
        return {"path": path, "error": "Feature 'media' not installed. pip install kitsune-core[media]"}

    import os
    if not os.path.isfile(path):
        return {"path": path, "error": f"File not found: {path}"}

    from pymediainfo import MediaInfo

    try:
        info = MediaInfo.parse(path)
    except Exception as e:
        return {"path": path, "error": str(e)}

    result = {"path": path}

    # General track
    for track in info.tracks:
        if track.track_type == "General":
            duration_ms = track.duration or 0
            result["duration_seconds"] = round(duration_ms / 1000, 2)
            minutes = int(duration_ms / 1000 / 60)
            seconds = int(duration_ms / 1000 % 60)
            result["duration_display"] = f"{minutes}:{seconds:02d}"
            result["overall_bitrate_kbps"] = int((track.overall_bit_rate or 0) / 1000)
            result["container"] = track.format or ""

    # Video tracks
    for track in info.tracks:
        if track.track_type == "Video":
            width = track.width or 0
            height = track.height or 0
            result["video"] = {
                "codec": track.format or "",
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}" if width and height else "",
                "display_resolution": _display_resolution(height),
                "framerate": float(track.frame_rate or 0),
                "bitrate_kbps": int((track.bit_rate or 0) / 1000),
                "bit_depth": int(track.bit_depth or 8),
                "hdr": _is_hdr(track),
            }
            break  # first video track only

    # Audio tracks
    result["audio"] = []
    for track in info.tracks:
        if track.track_type == "Audio":
            result["audio"].append({
                "codec": track.format or "",
                "channels": track.channel_s or 0,
                "language": track.language or "",
                "bitrate_kbps": int((track.bit_rate or 0) / 1000),
                "title": track.title or "",
            })

    # Subtitle tracks
    result["subtitles"] = []
    for track in info.tracks:
        if track.track_type == "Text":
            result["subtitles"].append({
                "codec": track.format or "",
                "language": track.language or "",
                "title": track.title or "",
                "forced": bool(track.forced and track.forced.lower() == "yes"),
            })

    return result


def _display_resolution(height: int) -> str:
    """Map pixel height to common display resolution label."""
    if height >= 2160:
        return "4K"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    elif height >= 480:
        return "480p"
    else:
        return f"{height}p" if height else ""


def _is_hdr(track) -> bool:
    """Detect HDR from video track metadata."""
    hdr_indicators = [
        track.hdr_format,
        track.hdr_format_compatibility,
    ]
    for val in hdr_indicators:
        if val:
            return True

    # Check transfer characteristics
    transfer = getattr(track, "transfer_characteristics", "") or ""
    if "PQ" in transfer or "HLG" in transfer or "SMPTE 2084" in transfer:
        return True

    # 10-bit + BT.2020 is typically HDR
    if (track.bit_depth and int(track.bit_depth) >= 10 and
            "BT.2020" in (getattr(track, "color_primaries", "") or "")):
        return True

    return False
