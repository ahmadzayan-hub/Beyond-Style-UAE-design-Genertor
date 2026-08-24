"""Anonymous session ownership checks for request-scoped resources.

The secret token travels in the X-Session-Token header. Only its sha256
is stored. A missing/wrong token yields 404 (not 403) so resource
existence is not leaked across sessions.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..db import models as m
from ..security.sessions import token_matches

SESSION_HEADER = "X-Session-Token"


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, "Not found.")


def require_owned_request(session: Session, design_id: str, request: Request) -> m.DesignRequest:
    req = session.get(m.DesignRequest, _parse_uuid(design_id))
    if req is None:
        raise HTTPException(404, "Design not found.")
    token = request.headers.get(SESSION_HEADER)
    if not token_matches(token, req.session_token_hash):
        raise HTTPException(404, "Design not found.")
    return req


def require_owned_version(session: Session, version_id: str, request: Request) -> m.DesignVersion:
    version = session.get(m.DesignVersion, _parse_uuid(version_id))
    if version is None:
        raise HTTPException(404, "Version not found.")
    design = session.get(m.Design, version.design_id)
    req = session.get(m.DesignRequest, design.request_id)
    token = request.headers.get(SESSION_HEADER)
    if not token_matches(token, req.session_token_hash):
        raise HTTPException(404, "Version not found.")
    return version
