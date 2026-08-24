"""API for the persistent P0 Golden Path.

Flow: create request → confirm exact text → generate candidates →
select (Design + version 1) → designer edit (new versions) → customer
approval (immutable lock) → authorized production export. Backed by
PostgreSQL via app.services.design_service.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..db.base import get_session
from ..engines.generator import diversity_score
from ..exporters.dxf_exporter import ProductionExportBlocked
from ..exporters.svg_exporter import export_svg
from ..fonts.registry import get_registry
from ..schemas.jewellery_design import (
    DesignCandidate,
    ImmutableSourceText,
    RecipeParams,
    TextIdentityProof,
    ValidationReport,
)
from ..security.sessions import GENERATE_LIMITER, issue_token
from ..services import design_service as svc
from .auth import require_owned_request, require_owned_version

router = APIRouter(prefix="/api/designs", tags=["designs"])
versions_router = APIRouter(prefix="/api/versions", tags=["versions"])
fonts_router = APIRouter(prefix="/api/fonts", tags=["fonts"])


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, "Not found.")


class CreateDesignRequest(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    product_type: str = "pendant"


class ConfirmTextRequest(BaseModel):
    confirmed_text: str


class SelectRequest(BaseModel):
    candidate_id: str


class EditRequest(BaseModel):
    recipe_overrides: dict = Field(default_factory=dict)
    note: str | None = None
    created_by: str = "designer"


class ChangeTextRequest(BaseModel):
    new_text: str = Field(min_length=1, max_length=120)
    confirmed: bool = False
    created_by: str = "designer"


class ApproveRequest(BaseModel):
    confirmed_text: str
    source_text_sha256: str
    geometry_hash: str
    approved_by: str = "customer"
    approval_method: str = "api"


@router.post("", status_code=201)
def create_design(req: CreateDesignRequest, session: Session = Depends(get_session)):
    token, token_hash = issue_token()
    row = svc.create_request(session, req.text, req.product_type, session_token_hash=token_hash)
    return {
        "design_id": str(row.id),
        "session_token": token,
        "state": row.status,
        "normalized_text": row.source_text_normalized,
        "source_text_sha256": row.source_text_sha256,
        "requires_confirmation": True,
    }


@router.post("/{design_id}/confirm")
def confirm_text(design_id: str, req: ConfirmTextRequest, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_request(session, design_id, request)
    try:
        row = svc.confirm_request_text(session, owned.id, req.confirmed_text)
    except svc.ConflictError as exc:
        raise HTTPException(409, str(exc))
    except svc.ApprovalRejected as exc:
        raise HTTPException(422, str(exc))
    return {"design_id": design_id, "state": row.status, "confirmed": True}


@router.post("/{design_id}/candidates")
def generate(design_id: str, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_request(session, design_id, request)
    if not GENERATE_LIMITER.allow(owned.session_token_hash or design_id):
        raise HTTPException(429, "Too many generation requests. Please wait a moment.")
    try:
        result = svc.generate_and_persist_candidates(session, owned.id)
    except svc.ConflictError as exc:
        raise HTTPException(409, str(exc))
    all_c, top = result["all"], result["top"]
    return {
        "design_id": design_id,
        "internal_candidate_count": len(all_c),
        "valid_candidate_count": sum(1 for c in all_c if c.validation and c.validation.passed),
        "diversity_min_pairwise": diversity_score(top),
        "ranking_config_version": top[0].ranking_config_version if top else None,
        "top": [
            {
                "candidate_id": c.candidate_id,
                "rank": c.diversity_rank,
                "recipe_id": c.recipe.recipe_id,
                "name": c.recipe.name,
                "font_id": c.recipe.font_id,
                "composition": c.recipe.composition,
                "score": c.score,
                "score_breakdown": c.score_breakdown,
                "width_mm": c.features.width_mm if c.features else None,
                "height_mm": c.features.height_mm if c.features else None,
                "source_text_sha256": c.source_text_sha256,
            }
            for c in top
        ],
    }


@router.get("/{design_id}")
def get_design(design_id: str, request: Request, session: Session = Depends(get_session)):
    row = require_owned_request(session, design_id, request)
    return {
        "design_id": design_id,
        "schema_version": row.schema_version,
        "state": row.status,
        "product_type": row.product_type,
        "source_text": {
            "normalized_text": row.source_text_normalized,
            "sha256": row.source_text_sha256,
            "confirmed": row.confirmed,
        },
        "ranking_config_version": row.ranking_config_version,
    }


@router.get("/{design_id}/candidates")
def list_candidates(
    design_id: str,
    request: Request,
    include_invalid: bool = False,
    session: Session = Depends(get_session),
):
    require_owned_request(session, design_id, request)
    rows = session.execute(
        select(m.DesignCandidateRow).where(m.DesignCandidateRow.request_id == _uuid(design_id))
    ).scalars().all()
    return [
        {
            "candidate_id": r.candidate_key,
            "validation_passed": r.validation_passed,
            "diversity_rank": r.diversity_rank,
            "score": r.score,
        }
        for r in rows
        if include_invalid or r.validation_passed
    ]


@router.get("/{design_id}/candidates/{candidate_id}/validation")
def get_validation(design_id: str, candidate_id: str, request: Request, session: Session = Depends(get_session)):
    require_owned_request(session, design_id, request)
    row = _candidate_row(session, design_id, candidate_id)
    return row.validation


@router.get("/{design_id}/candidates/{candidate_id}/svg")
def get_candidate_svg(design_id: str, candidate_id: str, request: Request, session: Session = Depends(get_session)):
    """Preview SVG for a generated candidate (pre-selection, not production)."""
    req = require_owned_request(session, design_id, request)
    row = _candidate_row(session, design_id, candidate_id)
    candidate, source = _row_to_candidate(row, req)
    return Response(content=export_svg(candidate, source), media_type="image/svg+xml")


@router.post("/{design_id}/select", status_code=201)
def select_candidate(design_id: str, req: SelectRequest, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_request(session, design_id, request)
    try:
        design, version = svc.select_candidate(session, owned.id, req.candidate_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except svc.ConflictError as exc:
        raise HTTPException(409, str(exc))
    return {
        "design_uuid": str(design.id),
        "version_id": str(version.id),
        "version_number": version.version_number,
        "status": version.status,
        "source_text_sha256": version.source_text_sha256,
        "geometry_hash": version.geometry_hash,
    }


@router.get("/{design_id}/events")
def list_events(design_id: str, request: Request, session: Session = Depends(get_session)):
    rid = require_owned_request(session, design_id, request).id
    design_ids = list(
        session.execute(select(m.Design.id).where(m.Design.request_id == rid)).scalars()
    )
    rows = session.execute(
        select(m.DesignEvent)
        .where(
            (m.DesignEvent.request_id == rid)
            | (m.DesignEvent.design_id == rid)
            | (m.DesignEvent.design_id.in_(design_ids))
        )
        .order_by(m.DesignEvent.created_at)
    ).scalars().all()
    return [
        {
            "event_id": str(r.id),
            "event_type": r.event_type,
            "version_id": str(r.version_id) if r.version_id else None,
            "actor": r.actor,
            "actor_type": r.actor_type,
            "created_at": r.created_at.isoformat(),
            "metadata": r.event_metadata,
        }
        for r in rows
    ]


# ------------------------------------------------------------- versions


@versions_router.get("/{version_id}")
def get_version(version_id: str, request: Request, session: Session = Depends(get_session)):
    v = require_owned_version(session, version_id, request)
    return {
        "version_id": str(v.id),
        "design_uuid": str(v.design_id),
        "version_number": v.version_number,
        "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
        "status": v.status,
        "immutable_source_text": v.immutable_source_text,
        "source_text_sha256": v.source_text_sha256,
        "geometry_hash": v.geometry_hash,
        "schema_version": v.schema_version,
        "arabic_engine_version": v.arabic_engine_version,
        "font_id": v.font_id,
        "font_version": v.font_version,
        "recipe_id": v.recipe_id,
        "recipe_version": v.recipe_version,
        "manufacturing_rules_version": v.manufacturing_rules_version,
        "validation_passed": v.validation_passed,
        "identity_verified": v.identity_verified,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat(),
        "edit_metadata": v.edit_metadata,
    }


@versions_router.post("/{version_id}/edit", status_code=201)
def edit_version(version_id: str, req: EditRequest, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_version(session, version_id, request)
    try:
        version = svc.edit_version(
            session, owned.id, req.recipe_overrides, req.note, req.created_by
        )
    except KeyError:
        raise HTTPException(404, "Version not found.")
    except svc.ApprovalRejected as exc:
        raise HTTPException(422, str(exc))
    return {
        "version_id": str(version.id),
        "version_number": version.version_number,
        "status": version.status,
        "validation_passed": version.validation_passed,
        "geometry_hash": version.geometry_hash,
        "source_text_sha256": version.source_text_sha256,
    }


@versions_router.post("/{version_id}/change-text", status_code=201)
def change_text(version_id: str, req: ChangeTextRequest, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_version(session, version_id, request)
    try:
        version = svc.change_source_text(
            session, owned.id, req.new_text, req.confirmed, req.created_by
        )
    except KeyError:
        raise HTTPException(404, "Version not found.")
    except svc.ApprovalRejected as exc:
        raise HTTPException(422, str(exc))
    return {
        "version_id": str(version.id),
        "version_number": version.version_number,
        "status": version.status,
        "source_text_sha256": version.source_text_sha256,
        "approvals_invalidated": True,
    }


@versions_router.post("/{version_id}/approve", status_code=201)
def approve(version_id: str, req: ApproveRequest, request: Request, session: Session = Depends(get_session)):
    owned = require_owned_version(session, version_id, request)
    try:
        approval = svc.approve_version(
            session,
            owned.id,
            confirmed_text=req.confirmed_text,
            source_text_sha256=req.source_text_sha256,
            geometry_hash=req.geometry_hash,
            approved_by=req.approved_by,
            approval_method=req.approval_method,
        )
    except KeyError:
        raise HTTPException(404, "Version not found.")
    except svc.ConflictError as exc:
        raise HTTPException(409, str(exc))
    except svc.ApprovalRejected as exc:
        raise HTTPException(422, str(exc))
    return {
        "approval_id": str(approval.id),
        "approval_hash": approval.approval_hash,
        "approved_at": approval.approved_at.isoformat(),
        "status": approval.status,
        "version_status": "APPROVED_LOCKED",
        "confirmation_statement": approval.confirmation_statement,
    }


@versions_router.get("/{version_id}/export/{fmt}")
def export(
    version_id: str,
    fmt: str,
    request: Request,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    owned = require_owned_version(session, version_id, request)
    try:
        content, record = svc.export_version(
            session, owned.id, fmt, idempotency_key=idempotency_key
        )
    except KeyError:
        raise HTTPException(404, "Version not found.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except svc.ConflictError as exc:
        raise HTTPException(409, str(exc))
    except ProductionExportBlocked as exc:
        raise HTTPException(423, str(exc))
    if not content:
        return {
            "idempotent_replay": True,
            "export_id": str(record.id),
            "content_sha256": record.content_sha256,
        }
    media = "image/svg+xml" if fmt == "svg" else "application/dxf"
    return Response(
        content=content,
        media_type=media,
        headers={
            "X-Export-Id": str(record.id),
            "X-Content-Sha256": record.content_sha256,
        },
    )


@versions_router.get("/{version_id}/svg")
def version_preview_svg(version_id: str, request: Request, session: Session = Depends(get_session)):
    """Owner-scoped PREVIEW render of a version (any status) — used for
    proof display and repair before/after. Not a production export: no
    export record, and the production DXF path stays lock-gated."""
    v = require_owned_version(session, version_id, request)
    candidate, source = svc._version_to_candidate(v)
    return Response(content=export_svg(candidate, source), media_type="image/svg+xml")


class RepairRequest(BaseModel):
    created_by: str = "customer"


@versions_router.get("/{version_id}/repair-options")
def repair_options(version_id: str, request: Request, session: Session = Depends(get_session)):
    """Deterministic, validated repair proposals only. Empty list = nothing
    to offer (design already comfortably manufacturable)."""
    v = require_owned_version(session, version_id, request)
    recipe = RecipeParams(**v.recipe)
    options = []
    if recipe.stroke_delta_mm < 0.45:
        options.append(
            {
                "repair_id": "thicken_strokes",
                "label_ar": "تحسين قابلية التصنيع (تسميك الخطوط)",
                "label_en": "Improve manufacturability (thicken strokes)",
                "overrides": {"stroke_delta_mm": round(recipe.stroke_delta_mm + 0.1, 3)},
            }
        )
    return {"version_id": version_id, "options": options}


@versions_router.post("/{version_id}/repair", status_code=201)
def apply_repair(
    version_id: str, req: RepairRequest, request: Request, session: Session = Depends(get_session)
):
    """Apply the safe deterministic fix as a NEW version (before/after =
    parent SVG vs new SVG). Historical/approved versions are never mutated."""
    v = require_owned_version(session, version_id, request)
    recipe = RecipeParams(**v.recipe)
    overrides = {"stroke_delta_mm": round(recipe.stroke_delta_mm + 0.1, 3)}
    try:
        version = svc.edit_version(
            session, v.id, overrides, note="auto-repair: thicken strokes", created_by=req.created_by
        )
    except svc.ApprovalRejected as exc:
        raise HTTPException(422, str(exc))
    return {
        "version_id": str(version.id),
        "parent_version_id": str(v.id),
        "version_number": version.version_number,
        "status": version.status,
        "validation_passed": version.validation_passed,
        "geometry_hash": version.geometry_hash,
        "source_text_sha256": version.source_text_sha256,
        "before_svg_url": f"/api/versions/{v.id}/svg",
        "after_svg_url": f"/api/versions/{version.id}/svg",
    }


@fonts_router.get("")
def list_fonts():
    return [
        {
            "font_id": f.font_id,
            "family": f.family,
            "style_family": f.style_family,
            "license": f.license,
            "rights_status": f.rights_status,
            "commercial_production_allowed": f.commercial_production_allowed,
        }
        for f in get_registry().list()
    ]


# ------------------------------------------------------------- helpers


def _candidate_row(session: Session, design_id: str, candidate_id: str) -> m.DesignCandidateRow:
    row = session.execute(
        select(m.DesignCandidateRow).where(
            m.DesignCandidateRow.request_id == _uuid(design_id),
            m.DesignCandidateRow.candidate_key == candidate_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Candidate not found.")
    return row


def _row_to_candidate(row: m.DesignCandidateRow, req: m.DesignRequest):
    source = ImmutableSourceText.create(req.source_text_raw, confirmed=req.confirmed)
    candidate = DesignCandidate(
        candidate_id=row.candidate_key,
        design_id=str(row.request_id),
        source_text_sha256=row.source_text_sha256,
        recipe=RecipeParams(**row.recipe),
        shaped_runs=[],
        identity_proof=TextIdentityProof(
            verified=row.identity_verified,
            covered_codepoint_indices=[],
            uncovered_codepoint_indices=[],
            notdef_glyph_count=0,
        ),
        validation=ValidationReport(**row.validation) if row.validation else None,
        geometry_wkt=row.geometry_wkt,
    )
    return candidate, source
