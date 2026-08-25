"""Correlation IDs + structured request logging.

Every request gets an `X-Request-ID` (client-supplied or generated),
propagated to the response header and into the JSON error body so a
customer-visible "تعذر توليد التصاميم" can be tied to a specific
backend log line without exposing internals to the browser. Logs are
structured JSON: request_id/route/status/duration_ms/error_code — never
a raw customer image, uploaded file, or secret value.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("beyondstyle.request")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(json.dumps({
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }))
        return response


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or "unknown"
