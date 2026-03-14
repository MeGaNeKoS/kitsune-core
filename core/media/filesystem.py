"""
Filesystem-level file information.
No extra dependencies — uses only the Python standard library.
"""

import os
from typing import Optional


def get_file_info(path: str) -> dict:
    """
    Get filesystem-level metadata for a file.

    Returns:
        {
            "path": str,              # absolute path
            "exists": bool,
            "filename": str,          # basename
            "extension": str,         # e.g. "mkv"
            "size_bytes": int,
            "size_mb": float,         # rounded to 2 decimals
            "directory": str,         # parent directory
            "created": float,         # unix timestamp
            "modified": float,        # unix timestamp
        }
    """
    abs_path = os.path.abspath(path)
    exists = os.path.isfile(abs_path)

    result = {
        "path": abs_path,
        "exists": exists,
        "filename": os.path.basename(abs_path),
        "extension": os.path.splitext(abs_path)[1].lstrip(".").lower(),
        "directory": os.path.dirname(abs_path),
    }

    if exists:
        stat = os.stat(abs_path)
        result["size_bytes"] = stat.st_size
        result["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
        result["created"] = stat.st_ctime
        result["modified"] = stat.st_mtime
    else:
        result["size_bytes"] = 0
        result["size_mb"] = 0.0
        result["created"] = 0.0
        result["modified"] = 0.0

    return result


def list_media_files(directory: str,
                     extensions: Optional[list[str]] = None) -> list[dict]:
    """
    List media files in a directory.

    Args:
        directory: Path to scan
        extensions: File extensions to include. Defaults to common video formats.

    Returns:
        List of file info dicts (same format as get_file_info).
    """
    if extensions is None:
        extensions = ["mkv", "mp4", "avi", "webm", "flv", "wmv", "mov", "m4v"]

    extensions = {ext.lower().lstrip(".") for ext in extensions}
    results = []

    if not os.path.isdir(directory):
        return results

    for entry in os.scandir(directory):
        if entry.is_file():
            ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
            if ext in extensions:
                results.append(get_file_info(entry.path))

    return sorted(results, key=lambda f: f["filename"])
