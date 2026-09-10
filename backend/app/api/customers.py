"""Customer identity API: passwordless login by contact + one-time code,
customer token, claim requests, list & resume my designs."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.base import get_session
from ..security.ratelimit import get_limiter
from ..services import customer_service as cs
from .auth import CUSTOMER_HEADER, require_owned_request

router = APIRouter(prefix="/api/customers", tags=["customers"])
me_router = APIRouter(prefix="/api/me", tags=["customers"])
# Separate windows: starting a login (sends a code) is the expensive/abusable
# call; verifying is bounded per code anyway (5 attempts) but capped per IP too.
LOGIN_LIMITER = get_limiter("login_start", int(os.environ.get("LOGIN_RATE_MAX", "10")), float(os.environ.get("LOGIN_RATE_WINDOW_S", "600")))
VERIFY_LIMITER = get_limiter("login_verify", int(os.environ.get("LOGIN_VERIFY_RATE_MAX", "30")), float(os.environ.get("LOGIN_RATE_WINDOW_S", "600")))


class StartLogin(BaseModel):
    contact: str = Field(min_length=3, max_length=120)


class VerifyLogin(BaseModel):
    contact: str = Field(min_length=3, max_length=120)
    code: str = Field(min_length=4, max_length=12)
    display_name: str | None = Field(default=None, max_length=120)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "anon"


def require_customer(session: Session, request: Request):
    c = cs.customer_from_token(session, request.headers.get(CUSTOMER_HEADER))
    if c is None:
        raise HTTPException(401, {"code": "CUSTOMER_LOGIN_REQUIRED", "detail": "Log in with your contact to see your designs."})
    return c


@router.post("/login/start")
def login_start(req: StartLogin, request: Request, session: Session = Depends(get_session)):
    if not LOGIN_LIMITER.allow(_client_key(request)):
        raise HTTPException(429, "Too many login attempts. Please wait.")
    try:
        return cs.start_login(session, req.contact)
    except cs.LoginRejected as exc:
        raise HTTPException(422, {"code": exc.code, "detail": str(exc)})


@router.post("/login/verify")
def login_verify(req: VerifyLogin, request: Request, session: Session = Depends(get_session)):
    if not VERIFY_LIMITER.allow(_client_key(request)):
        raise HTTPException(429, "Too many login attempts. Please wait.")
    try:
        token, customer = cs.verify_code(session, req.contact, req.code)
    except cs.LoginRejected as exc:
        status = 429 if exc.code == "TOO_MANY_ATTEMPTS" else 422
        raise HTTPException(status, {"code": exc.code, "detail": str(exc)})
    if req.display_name and not customer.display_name:
        customer.display_name = req.display_name.strip()[:120]
    return {"customer_token": token, "customer_id": str(customer.id), "contact_masked": customer.contact_masked,
            "display_name": customer.display_name, "expires_in_days": 30}


@router.post("/logout")
def logout(request: Request, session: Session = Depends(get_session)):
    return {"revoked": cs.logout(session, request.headers.get(CUSTOMER_HEADER))}


@me_router.get("")
def me(request: Request, session: Session = Depends(get_session)):
    c = require_customer(session, request)
    return {"customer_id": str(c.id), "contact_kind": c.contact_kind, "contact_masked": c.contact_masked,
            "display_name": c.display_name, "verified_at": c.verified_at.isoformat() if c.verified_at else None}


@me_router.get("/designs")
def my_designs(request: Request, session: Session = Depends(get_session)):
    c = require_customer(session, request)
    return {"designs": cs.list_requests(session, c)}


@me_router.post("/designs/{design_id}/session", status_code=201)
def resume_design(design_id: str, request: Request, session: Session = Depends(get_session)):
    """Continue a claimed design on this device: rotates the per-request
    token (older devices lose it) and returns the new one."""
    c = require_customer(session, request)
    req = require_owned_request(session, design_id, request)   # customer token satisfies ownership
    try:
        token = cs.reissue_session_token(session, req, c)
    except PermissionError as exc:
        raise HTTPException(404, str(exc))
    return {"design_id": design_id, "session_token": token, "state": req.status, "text": req.source_text_normalized}


@router.post("/claim/{design_id}", status_code=201)
def claim(design_id: str, request: Request, session: Session = Depends(get_session)):
    """Bind the request I hold the per-request token for to my customer
    identity (both headers required)."""
    c = require_customer(session, request)
    req = require_owned_request(session, design_id, request)
    try:
        cs.claim_request(session, req, c)
    except PermissionError as exc:
        raise HTTPException(409, str(exc))
    return {"design_id": design_id, "customer_id": str(c.id), "claimed": True}
