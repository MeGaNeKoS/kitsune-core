"""
Simple API key authentication for the kitsune-core server.

Usage:
    from core.server.auth import configure_auth

    # Enable auth with a key
    configure_auth(api_key="your-secret-key")

    # Disable auth (default)
    configure_auth(api_key=None)

Clients pass the key via header:
    X-API-Key: your-secret-key

Or query parameter:
    /health?api_key=your-secret-key

The /health endpoint is always accessible without auth.
"""

import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_api_key: Optional[str] = None

# Endpoints that don't require auth
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def configure_auth(api_key: Optional[str] = None):
    """Set the API key. Pass None to disable auth."""
    global _api_key
    _api_key = api_key
    if api_key:
        logger.info("API key authentication enabled")
    else:
        logger.info("API key authentication disabled")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that checks for API key on every request."""

    async def dispatch(self, request: Request, call_next):
        if _api_key is None:
            # Auth disabled
            return await call_next(request)

        # Allow public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Check header
        key = request.headers.get("X-API-Key", "")

        # Check query param as fallback
        if not key:
            key = request.query_params.get("api_key", "")

        if key != _api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
