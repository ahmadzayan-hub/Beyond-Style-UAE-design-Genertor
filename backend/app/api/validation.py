"""Public customer validation — anonymous, rate-limited, no staff token.

Customers score a manufacturable, diverse pack of proofs from their phone.
Responses are anonymous (a client-generated respondent token groups one
person's answers; it is stored hashed) and go into the append-only
customer_validation_responses table that the curation analysis reads —
never mixed with expert reviews. Engineering metadata is stripped: a
customer reacts to the piece, not to its manufacturing report.
"""
from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.base import get_session
from ..security.sessions import RateLimiter

router = APIRouter(prefix="/api/validation", tags=["validation"])

VOTE_LIMITER = RateLimiter(
    int(os.environ.get("VOTE_RATE_MAX", "60")), float(os.environ.get("VOTE_RATE_WINDOW_S", "600"))
)


def _pack(session: Session) -> dict:
    from ..services.customer_validation import select_customer_pack
    from ..services.review_items import generate_review_pack

    pack = select_customer_pack(session, generate_review_pack(max_per_product=4))
    return {
        "pack_id": pack["pack_id"],
        "size": pack["size"],
        "items": [
            {"item_id": i["item_id"], "product": i["product"], "customer_style": i["customer_style"],
             "source_text": i["source_text"], "width_mm": i["width_mm"], "height_mm": i["height_mm"],
             "proof_path_d": i["proof_path_d"], "proof_view": i["proof_view"]}
            for i in pack["items"]
        ],
    }


@router.get("/pack")
def public_pack(session: Session = Depends(get_session)):
    return _pack(session)


class VoteIn(BaseModel):
    pack_id: str
    item_id: str
    respondent_token: str = Field(min_length=8, max_length=128)
    would_buy: str
    premium_feel: int = Field(ge=1, le=5)
    readability: int = Field(ge=1, le=5)
    uniqueness: int = Field(ge=1, le=5)
    preferred_product: str | None = None
    price_band: str | None = None
    comment: str | None = Field(default=None, max_length=500)
    website: str | None = None  # honeypot — bots fill it, humans never see it


@router.post("/response", status_code=201)
def public_response(body: VoteIn, request: Request, session: Session = Depends(get_session)):
    from ..services.customer_validation import ResponseRejected, record_customer_response

    if body.website:
        raise HTTPException(422, "Rejected.")
    key = hashlib.sha256(body.respondent_token.encode()).hexdigest()[:32]
    client_key = (request.client.host if request.client else "anon")
    if not VOTE_LIMITER.allow(client_key) or not VOTE_LIMITER.allow(key):
        raise HTTPException(429, "Too many responses. Please try again later.")
    pack = _pack(session)
    if body.pack_id != pack["pack_id"] or body.item_id not in {i["item_id"] for i in pack["items"]}:
        raise HTTPException(422, "This item is not part of the current pack.")
    try:
        row = record_customer_response(
            session, item_id=body.item_id, pack_id=body.pack_id, respondent_token=key,
            would_buy=body.would_buy, premium_feel=body.premium_feel, readability=body.readability,
            uniqueness=body.uniqueness, preferred_product=body.preferred_product,
            price_band=body.price_band, comment=body.comment,
        )
    except ResponseRejected as exc:
        raise HTTPException(422, str(exc))
    return {"response_id": str(row.id), "item_id": body.item_id}
