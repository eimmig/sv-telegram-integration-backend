"""Rejects oversized request bodies before they reach a route handler.

Checks Content-Length up front (cheap, no buffering) - doesn't protect against a
chunked body without that header, but n8n's HTTP Request node always sets it for a
JSON payload, which is the only client this service has.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)
