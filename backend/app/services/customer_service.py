"""Customer identity + secure retrieval of a customer's own requests.

Flow: start_login(contact) → code (hashed, 10 min, 5 attempts) delivered
through the provider adapter → verify_code → customer session token (30 d,
only its sha256 stored) → claim_request binds an anonymous request to the
customer → list_requests / reissue_session_token let the customer continue
on another device. Anonymous per-request tokens keep working unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..security import customer_auth as ca
from ..security.sessions import hash_token, issue_token, token_matches
from .design_service import _emit  # audit trail shared with the design flow


class LoginRejected(ValueError):
    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.code = code   # CONTACT_INVALID | CODE_INVALID | CODE_EXPIRED | TOO_MANY_ATTEMPTS | NO_CODE


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_login(session: Session, raw_contact: str) -> dict:
    try:
        kind, normalized = ca.normalize_contact(raw_contact)
    except ca.ContactInvalid as exc:
        raise LoginRejected(str(exc), "CONTACT_INVALID")
    h = ca.contact_hash(normalized)
    customer = session.execute(select(m.Customer).where(m.Customer.contact_hash == h)).scalar_one_or_none()
    if customer is None:
        customer = m.Customer(contact_kind=kind, contact_hash=h, contact_masked=ca.mask_contact(kind, normalized))
        session.add(customer)
        session.flush()
    # one live code per customer: expire older unused codes
    for old in session.execute(select(m.CustomerLoginCode).where(
            m.CustomerLoginCode.customer_id == customer.id, m.CustomerLoginCode.used_at.is_(None))).scalars():
        old.expires_at = min(old.expires_at, _now())
    code = ca.new_code()
    delivery = ca.deliver_code(kind, normalized, code)
    row = m.CustomerLoginCode(customer_id=customer.id, code_hash=ca.hash_code(str(customer.id), code),
                              expires_at=_now() + timedelta(minutes=ca.CODE_TTL_MINUTES),
                              delivery_status=delivery["status"])
    session.add(row)
    session.flush()
    out = {"customer_id": str(customer.id), "contact_kind": kind, "contact_masked": customer.contact_masked,
           "delivery": delivery, "expires_in_minutes": ca.CODE_TTL_MINUTES}
    if ca.dev_echo_enabled():
        out["dev_code"] = code   # local/CI only — readiness flags this setting
    return out


def verify_code(session: Session, raw_contact: str, code: str) -> tuple[str, m.Customer]:
    try:
        kind, normalized = ca.normalize_contact(raw_contact)
    except ca.ContactInvalid as exc:
        raise LoginRejected(str(exc), "CONTACT_INVALID")
    customer = session.execute(select(m.Customer).where(m.Customer.contact_hash == ca.contact_hash(normalized))).scalar_one_or_none()
    if customer is None:
        raise LoginRejected("No login code was requested for this contact.", "NO_CODE")
    row = session.execute(select(m.CustomerLoginCode).where(
        m.CustomerLoginCode.customer_id == customer.id
    ).order_by(m.CustomerLoginCode.created_at.desc())).scalars().first()
    if row is None or row.used_at is not None:   # latest code already consumed → single use
        raise LoginRejected("No login code was requested for this contact.", "NO_CODE")
    if row.expires_at <= _now():
        raise LoginRejected("The code has expired; request a new one.", "CODE_EXPIRED")
    if row.attempts >= ca.CODE_MAX_ATTEMPTS:
        raise LoginRejected("Too many attempts; request a new code.", "TOO_MANY_ATTEMPTS")
    row.attempts += 1
    if row.code_hash != ca.hash_code(str(customer.id), (code or "").strip()):
        # The failed attempt MUST persist even though the request ends in an
        # error response (the commit middleware rolls back on 4xx) — an
        # attacker must not get unlimited guesses.
        session.commit()
        raise LoginRejected("Incorrect code.", "CODE_INVALID")
    row.used_at = _now()
    customer.verified_at = customer.verified_at or _now()
    customer.last_login_at = _now()
    token, token_hash = issue_token()
    session.add(m.CustomerSession(customer_id=customer.id, token_hash=token_hash,
                                  expires_at=_now() + timedelta(days=ca.CUSTOMER_SESSION_DAYS)))
    session.flush()
    return token, customer


def customer_from_token(session: Session, token: str | None) -> m.Customer | None:
    if not token:
        return None
    row = session.execute(select(m.CustomerSession).where(m.CustomerSession.token_hash == hash_token(token))).scalar_one_or_none()
    if row is None or row.revoked_at is not None or row.expires_at <= _now():
        return None
    return session.get(m.Customer, row.customer_id)


def logout(session: Session, token: str | None) -> bool:
    row = session.execute(select(m.CustomerSession).where(m.CustomerSession.token_hash == hash_token(token or ""))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = _now()
    return True


def claim_request(session: Session, req: m.DesignRequest, customer: m.Customer) -> m.DesignRequest:
    """Bind a request the caller already owns (per-request token) to the
    logged-in customer. A request already bound to another customer is
    never re-bound."""
    if req.customer_id is not None and req.customer_id != customer.id:
        raise PermissionError("This design already belongs to another customer.")
    if req.customer_id is None:
        req.customer_id = customer.id
        _emit(session, "REQUEST_CLAIMED", request_id=req.id, actor=str(customer.id), actor_type="customer",
              metadata={"contact_kind": customer.contact_kind})
    return req


def list_requests(session: Session, customer: m.Customer) -> list[dict]:
    rows = session.execute(select(m.DesignRequest).where(m.DesignRequest.customer_id == customer.id)
                           .order_by(m.DesignRequest.created_at.desc())).scalars().all()
    out = []
    for r in rows:
        design = session.execute(select(m.Design).where(m.Design.request_id == r.id)).scalar_one_or_none()
        latest = None
        approved = False
        if design is not None:
            latest = session.execute(select(m.DesignVersion).where(m.DesignVersion.design_id == design.id)
                                     .order_by(m.DesignVersion.version_number.desc())).scalars().first()
            approved = session.execute(select(m.DesignVersion).where(
                m.DesignVersion.design_id == design.id, m.DesignVersion.status == "APPROVED_LOCKED")).scalars().first() is not None
        out.append({
            "design_id": str(r.id), "text": r.source_text_normalized, "product_type": r.product_type,
            "state": r.status, "confirmed": r.confirmed, "created_at": r.created_at.isoformat(),
            "versions": design.current_version_number if design else 0,
            "latest_version_id": str(latest.id) if latest else None,
            "latest_version_status": latest.status if latest else None,
            "approved": approved,
        })
    return out


def reissue_session_token(session: Session, req: m.DesignRequest, customer: m.Customer) -> str:
    """Continue on another device: rotate the per-request secret (the old
    token stops working) and hand the new one to the verified owner."""
    if req.customer_id != customer.id:
        raise PermissionError("Not your design.")
    token, token_hash = issue_token()
    req.session_token_hash = token_hash
    _emit(session, "SESSION_REISSUED", request_id=req.id, actor=str(customer.id), actor_type="customer")
    return token


def customer_owns_request(session: Session, req: m.DesignRequest, customer_token: str | None) -> bool:
    if req.customer_id is None or not customer_token:
        return False
    c = customer_from_token(session, customer_token)
    return c is not None and c.id == req.customer_id


__all__ = ["LoginRejected", "start_login", "verify_code", "customer_from_token", "logout", "claim_request",
           "list_requests", "reissue_session_token", "customer_owns_request", "token_matches"]
