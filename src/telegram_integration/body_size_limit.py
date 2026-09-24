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
