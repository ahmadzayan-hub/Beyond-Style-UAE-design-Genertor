"""Reference intake + brief + privacy endpoints (session-token protected)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..db.base import get_session
from ..security.sessions import UPLOAD_LIMITER
from ..security.uploads import MAX_UPLOAD_BYTES, UploadRejected, get_storage
from ..services import intake_service as intake
from .auth import require_owned_request

router = APIRouter(prefix="/api/designs", tags=["intake"])


class BriefRequest(BaseModel):
    customer_message: str | None = None
    product_type: str | None = None
    material_preference: str | None = None
    style_intent: str | None = None
    language: str | None = None
    quantity: int = Field(default=1, ge=1, le=500)
    deadline: str | None = None
    delivery_emirate: str | None = None


def _brief_response(brief: m.CustomerBrief) -> dict:
    return {
        "brief_id": str(brief.id),
        "request_type": brief.request_type,
        "confirmed_text": brief.confirmed_text,
        "language": brief.language,
        "product_type": brief.product_type,
        "material_preference": brief.material_preference,
        "style_intent": brief.style_intent,
        "reference_ids": brief.reference_ids or [],
        "quantity": brief.quantity,
        "deadline": brief.deadline,
        "delivery_emirate": brief.delivery_emirate,
        "missing_fields": brief.missing_fields or [],
        "confidence": brief.confidence,
        "status": brief.status,
        "generation_hints": brief.generation_hints,
    }


@router.post("/{design_id}/references", status_code=201)
async def upload_reference(
    design_id: str,
    request: Request,
    file: UploadFile = File(...),
    provenance: str = Form("UNKNOWN"),
    customer_message: str | None = Form(None),
    session: Session = Depends(get_session),
):
    req = require_owned_request(session, design_id, request)
    limit_key = req.session_token_hash or (request.client.host if request.client else "anon")
    if not UPLOAD_LIMITER.allow(limit_key):
        raise HTTPException(429, "Too many uploads. Please wait a moment and try again.")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the maximum allowed size.")
    try:
        asset = intake.add_reference(
            session,
            req.id,
            data=data,
            filename=file.filename or "upload",
            declared_type=file.content_type,
            provenance=provenance,
            customer_message=customer_message,
        )
    except UploadRejected as exc:
        raise HTTPException(422, str(exc))
    return {
        "reference_id": str(asset.id),
        "media_type": asset.media_type,
        "sha256": asset.sha256,
        "provenance": asset.provenance,
        "ip_risk": asset.ip_risk,
        "privacy_status": asset.privacy_status,
        "scan_status": asset.scan_status,
        "analysis": asset.analysis,
        "copy_notice": (
            "لا يمكن نسخ تصميم محمي؛ سننشئ تصميماً أصلياً مستوحى من الشكل العام."
            if asset.ip_risk == "POTENTIAL_COPY_RISK"
            else None
        ),
    }


@router.get("/{design_id}/references/{reference_id}/content")
def reference_content(
    design_id: str, reference_id: str, request: Request, session: Session = Depends(get_session)
):
    """Private media access — owner session only; no public URLs exist."""
    req = require_owned_request(session, design_id, request)
    try:
        ref_uuid = uuid.UUID(reference_id)
    except ValueError:
        raise HTTPException(404, "Reference not found.")
    asset = session.get(m.ReferenceAsset, ref_uuid)
    if asset is None or asset.design_request_id != req.id or asset.deleted:
        raise HTTPException(404, "Reference not found.")
    data = get_storage().get(asset.storage_key)
    return Response(content=data, media_type=asset.media_type,
                    headers={"Cache-Control": "private, no-store"})


@router.put("/{design_id}/brief")
def update_brief(
    design_id: str, body: BriefRequest, request: Request, session: Session = Depends(get_session)
):
    req = require_owned_request(session, design_id, request)
    brief = intake.upsert_brief(
        session,
        req.id,
        customer_message=body.customer_message,
        product_type=body.product_type,
        material_preference=body.material_preference,
        style_intent=body.style_intent,
        language=body.language,
        quantity=body.quantity,
        deadline=body.deadline,
        delivery_emirate=body.delivery_emirate,
    )
    return _brief_response(brief)


@router.get("/{design_id}/brief")
def get_brief(design_id: str, request: Request, session: Session = Depends(get_session)):
    req = require_owned_request(session, design_id, request)
    brief = session.execute(
        select(m.CustomerBrief).where(m.CustomerBrief.design_request_id == req.id)
    ).scalar_one_or_none()
    if brief is None:
        raise HTTPException(404, "No brief yet.")
    return _brief_response(brief)


@router.delete("/{design_id}/references")
def delete_references(design_id: str, request: Request, session: Session = Depends(get_session)):
    """Privacy: purge this session's uploaded reference files."""
    req = require_owned_request(session, design_id, request)
    count = intake.delete_references(session, req.id)
    return {"deleted": count}
