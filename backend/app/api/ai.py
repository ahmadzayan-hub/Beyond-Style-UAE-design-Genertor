"""AI / Reference Intelligence endpoints (session-token scoped).

All endpoints degrade honestly: with AI disabled/unavailable the
deterministic Golden Path is unaffected, DNA falls back to the labelled
deterministic analyzer, and photoreal previews return MODEL_UNAVAILABLE.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.providers import ModelUnavailable, ai_status, get_image_editor
from ..ai.preview_guard import check_preview
from ..ai.registry import MODEL_REGISTRY
from ..db import models as m
from ..db.base import get_session
from ..services import design_memory, reference_intelligence as ri
from .auth import require_owned_request, require_owned_version

router = APIRouter(prefix="/api/ai", tags=["ai"])
ref_router = APIRouter(prefix="/api/designs", tags=["reference-intelligence"])


@router.get("/status")
def status():
    """Honest per-model availability + license registry — covers the
    local Qwen/FLUX visual stack AND Claude/GPT-Image-2/Hermes. Never a
    fabricated PASS; deterministic_fallback is always available
    regardless of what any provider reports."""
    from ..ai.agents import orchestration_status
    from ..ai.image_providers import image_provider_status

    orch = orchestration_status()
    image = image_provider_status()
    return {
        **ai_status(),
        "registry": {k: v.model_dump() for k, v in MODEL_REGISTRY.items()},
        "claude": {
            "sdk_installed": orch["claude"]["sdk_installed"],
            "credentials_configured": orch["claude"]["credentials_configured"],
            "routing": orch["claude"]["routing"],
        },
        "gpt_image_2": {
            "enabled_flag": image["health"]["enabled_flag"],
            "sdk_installed": image["health"]["sdk_installed"],
            "key_configured": image["health"]["key_configured"],
            "role": image["health"]["role"],
        },
        "hermes": orch["hermes_client"],
        "deterministic_fallback": {
            "status": "always_available",
            "note": "Arabic/geometry/manufacturing engines never depend on any AI provider above",
        },
    }


@ref_router.post("/{design_id}/references/{reference_id}/analyze")
def analyze(
    design_id: str,
    reference_id: str,
    request: Request,
    require_model: bool = False,
    session: Session = Depends(get_session),
):
    req = require_owned_request(session, design_id, request)
    try:
        rid = uuid.UUID(reference_id)
    except ValueError:
        raise HTTPException(404, "Reference not found.")
    asset = session.get(m.ReferenceAsset, rid)
    if asset is None or asset.design_request_id != req.id or asset.deleted:
        raise HTTPException(404, "Reference not found.")
    if require_model:
        # Caller demands a real model — no deterministic fallback allowed.
        from ..ai.providers import get_visual_analyzer

        try:
            get_visual_analyzer()._guard()  # type: ignore[attr-defined]
        except ModelUnavailable as exc:
            raise HTTPException(503, str(exc))
    row = ri.analyze_reference(session, rid)
    similar = ri.retrieve_similar_approved(session, row)
    return {
        "reference_dna_id": str(row.id),
        "source": row.source,  # "vlm" (real model) or "deterministic_fallback"
        "analyzer_model": row.analyzer_model,
        "dna": row.dna,
        "copy_risk_status": ri.copy_risk_status(row),
        "similar_approved": [{"reference_dna_id": i, "similarity": round(s, 3)} for i, s in similar],
    }


class FeedbackRequest(BaseModel):
    event_type: str
    version_id: str | None = None
    metadata: dict = Field(default_factory=dict)


@ref_router.post("/{design_id}/feedback", status_code=201)
def feedback(
    design_id: str, body: FeedbackRequest, request: Request, session: Session = Depends(get_session)
):
    req = require_owned_request(session, design_id, request)
    try:
        design_memory.record_feedback(
            session,
            body.event_type,
            request_id=req.id,
            version_id=uuid.UUID(body.version_id) if body.version_id else None,
            actor="customer",
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"recorded": body.event_type}


@router.get("/memory/weights")
def memory_weights(session: Session = Depends(get_session)):
    """Diagnostic: learned recipe-family ranking weights + workshop
    failure constraints (derived from append-only events)."""
    return {
        "recipe_family_weights": design_memory.recipe_family_weights(session),
        "workshop_failure_constraints": design_memory.workshop_failure_constraints(session),
        "note": "derived from feedback events; base models are NOT retrained",
    }


class PreviewRequest(BaseModel):
    style: str = "clean_product"  # clean_product | black_luxury | white_ecommerce | lifestyle
    material: str = "silver-925"


PREVIEW_PROMPTS = {
    "clean_product": "professional studio photograph of this exact {material} jewellery pendant, soft light, neutral background. Keep the pendant shape exactly unchanged.",
    "black_luxury": "luxury product photograph of this exact {material} jewellery piece on black velvet, dramatic lighting. Keep the pendant shape exactly unchanged.",
    "white_ecommerce": "clean e-commerce photo of this exact {material} jewellery piece on pure white background. Keep the pendant shape exactly unchanged.",
    "lifestyle": "photograph of this exact {material} pendant worn on a necklace, elegant neckline, shallow depth of field. Keep the pendant shape exactly unchanged.",
}


@router.post("/versions/{version_id}/photoreal-preview")
def photoreal_preview(
    version_id: str, body: PreviewRequest, request: Request, session: Session = Depends(get_session)
):
    """AI preview of a validated design. The generated image is display-only
    ('AI preview' label in UI): it is identity-guarded against the canonical
    geometry and NEVER feeds SVG/DXF/manufacturing."""
    version = require_owned_version(session, version_id, request)
    if not version.validation_passed:
        raise HTTPException(409, "Preview requires a validated design version.")
    if body.style not in PREVIEW_PROMPTS:
        raise HTTPException(422, "Unknown preview style.")
    try:
        editor = get_image_editor()
        # Render canonical proof to raster (reference layer) via the stored
        # SVG path — the editor stylizes it; the guard verifies identity.
        from ..services.design_service import _version_to_candidate
        from ..exporters.svg_exporter import export_proof_svg

        candidate, source = _version_to_candidate(version)
        svg = export_proof_svg(candidate, source)
        prompt = PREVIEW_PROMPTS[body.style].format(material=body.material)
        rendered = editor.edit(svg.encode("utf-8"), prompt)
        guard = check_preview(version.geometry_wkt, rendered)
        if not guard["accepted"]:
            raise HTTPException(
                409,
                f"PREVIEW_REJECTED: silhouette divergence {guard['divergence']} exceeds "
                f"{guard['threshold']} — canonical design must not change.",
            )
        from ..security.uploads import get_storage

        key = get_storage().put(rendered, ".png")
        return {"status": "ok", "storage_key": key, "identity_guard": guard,
                "label": "AI preview only — not manufacturing truth"}
    except ModelUnavailable as exc:
        raise HTTPException(503, f"MODEL_UNAVAILABLE: {exc.reason}")
