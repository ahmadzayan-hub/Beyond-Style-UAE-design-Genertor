"""Beyond Style UAE — backend API (P0 Golden Path slice)."""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .api.ai import ref_router as ai_ref_router, router as ai_router
from .api.designs import fonts_router, router as designs_router, versions_router
from .api.intake import router as intake_router
from .api.visual import orchestration_router, router as visual_router
from .config import SCHEMA_VERSION
from .db.base import get_session
from .observability import CorrelationIdMiddleware, get_request_id
from .readiness import readiness_report

app = FastAPI(
    title="Beyond Style UAE — AI Jewellery Designer API",
    version=SCHEMA_VERSION,
)

# --- CORS: exact configured origins only. Never "*" together with
# credentials (session tokens travel as a header, not a cookie, but
# credentials=False keeps this rule true regardless). ---
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not _allowed_origins:
    # Honest local-dev default only — production MUST set ALLOWED_ORIGINS.
    _allowed_origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(designs_router)
app.include_router(intake_router)
app.include_router(versions_router)
app.include_router(fonts_router)
app.include_router(ai_router)
app.include_router(ai_ref_router)
app.include_router(visual_router)
app.include_router(orchestration_router)


# --- Structured errors: every 4xx/5xx response carries a machine-
# readable error_code + the request's correlation id. Internal
# exception text is NEVER exposed for 5xx — only a generic message. ---

_STATUS_TO_ERROR_CODE = {
    400: "GENERATION_FAILED",
    404: "SESSION_EXPIRED",
    409: "GENERATION_FAILED",
    413: "REFERENCE_NOT_READY",
    422: "ARABIC_VALIDATION_FAILED",
    423: "GENERATION_FAILED",
    429: "RATE_LIMITED",
}


@app.exception_handler(HTTPException)
async def structured_http_exception_handler(request: Request, exc: HTTPException):
    """`detail` always stays exactly what the route raised (string or a
    pre-existing structured dict, e.g. the visual-preview endpoint's
    own {code, reason, fallback, ...}) — unchanged from FastAPI's
    default contract, so existing callers of `response.json()["detail"]`
    keep working. `error_code`/`request_id` are added as new SIBLING
    top-level keys, never merged into `detail`."""
    request_id = get_request_id(request)
    error_code = _STATUS_TO_ERROR_CODE.get(exc.status_code, "GENERATION_FAILED")
    if isinstance(exc.detail, dict) and isinstance(exc.detail.get("code"), str):
        error_code = exc.detail["code"]
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": error_code,
            "request_id": request_id,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id(request)
    # Never leak internal stack traces / exception text to the customer —
    # the real cause is in the structured server log, keyed by request_id.
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred.",
            "error_code": "BACKEND_UNAVAILABLE",
            "request_id": request_id,
        },
    )


@app.get("/health")
def health():
    """Process-alive only — no dependency checks. See /ready for those."""
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@app.get("/ready")
def ready(session: Session = Depends(get_session)):
    report = readiness_report(session)
    status_code = 200 if report["status"] == "ready" else 503
    return JSONResponse(status_code=status_code, content=report)


# GET /api/ai/status is served by api/ai.py's router (extended this
# slice to also cover Claude/GPT-Image-2/Hermes, not just the local
# Qwen/FLUX stack) — see app.include_router(ai_router) above.
