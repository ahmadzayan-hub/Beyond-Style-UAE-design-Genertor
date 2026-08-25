"""Visual Studio + orchestration status endpoints.

Every response degrades honestly: with no image provider the client gets
PHOTOREAL_PREVIEW_UNAVAILABLE and keeps using the deterministic SVG
preview, which is what the workshop pipeline uses anyway.
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.agents import Orchestrator, ToolExecutionError, ToolNotPermitted, orchestration_status
from ..ai.image_providers import ImageProviderUnavailable, image_provider_status
from ..ai.llm import LLMUnavailable
from ..ai.product_skills import PRODUCT_SKILLS, load_skill
from ..ai.quality_layer import compute_confidence, design_lineage, run_design_jury
from ..ai.visual_brief import MATERIALS, QUALITY_MODES, SCENES, STONES
from ..db import models as m
from ..db.base import get_session
from ..security.uploads import get_storage
from ..services import visual_studio as vs
from .auth import require_owned_request, require_owned_version

router = APIRouter(prefix="/api/visual", tags=["visual-studio"])
orchestration_router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

#: Shared secret for the isolated Hermes runtime's tool-call callback
#: (services/hermes/app/tool_client.py). Unset by default, which closes
#: the endpoint unconditionally — only a deployment that explicitly runs
#: Hermes in isolated mode needs to set this.
INTERNAL_TOOL_TOKEN = os.environ.get("INTERNAL_TOOL_TOKEN", "")


@orchestration_router.get("/status")
def status():
    """Hermes runtime + Claude routing + budgets + agent registry.
    Never exposes any API key — only booleans."""
    return {**orchestration_status(), "image_provider": image_provider_status()}


@router.get("/options")
def options():
    return {
        "materials": sorted(MATERIALS),
        "finishes": ["polished", "matte", "brushed", "hammered"],
        "scenes": sorted(SCENES),
        "stones": sorted(STONES),
        "quality_modes": sorted(QUALITY_MODES),
    }


class PreviewRequest(BaseModel):
    scene: str = "clean_design"
    material: str = "silver-925"
    finish: str = "polished"
    stones: list[str] = Field(default_factory=list)
    orientation: str = "front"
    quality: str = "DRAFT"
    product_type: str | None = None
    use_reference_style: bool = False


@router.post("/versions/{version_id}/preview")
def create_preview(
    version_id: str,
    body: PreviewRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    version = require_owned_version(session, version_id, request)
    if not version.validation_passed:
        raise HTTPException(409, "Preview requires a validated design version.")
    if body.scene not in SCENES or body.material not in MATERIALS:
        raise HTTPException(422, "Unknown scene or material.")
    if any(s not in STONES for s in body.stones):
        raise HTTPException(422, "Unknown stone type.")

    design = session.get(m.Design, version.design_id)
    request_id = design.request_id
    brief = vs.build_brief(
        version,
        scene=body.scene,
        material=body.material,
        finish=body.finish,
        stones=body.stones,
        orientation=body.orientation,
        quality=body.quality if body.quality in QUALITY_MODES else "DRAFT",
        product_type=body.product_type,
    )
    reference_dna = None
    if body.use_reference_style:
        dna_row = session.execute(
            select(m.ReferenceDNARow).where(m.ReferenceDNARow.design_request_id == request_id)
        ).scalars().first()
        reference_dna = dna_row.dna if dna_row else None
    try:
        record = vs.generate_preview(
            session, version, request_id, brief, reference_style_dna=reference_dna
        )
    except ImageProviderUnavailable as exc:
        # Deterministic path continues — this is a display feature only.
        raise HTTPException(
            503,
            {
                "code": "PHOTOREAL_PREVIEW_UNAVAILABLE",
                "reason": exc.reason,
                "fallback": f"/api/versions/{version_id}/svg",
                "deterministic_design_unaffected": True,
            },
        )
    except vs.PreviewRejected as exc:
        raise HTTPException(409, {"code": exc.status, "guard": exc.guard})
    return {
        "generation_id": str(record.id),
        "guard_status": record.guard_status,
        "guard_report": record.guard_report,
        "attempts": record.attempts,
        "cost_usd": record.cost_usd,
        "visual_brief": record.visual_brief,
        "geometry_hash": record.geometry_hash,
        "source_text_sha256": record.source_text_sha256,
        "image_url": f"/api/visual/generations/{record.id}/image",
        "label": "AI-generated preview — visualization only, not manufacturing truth",
    }


@router.get("/generations/{generation_id}/image")
def generation_image(generation_id: str, request: Request, session: Session = Depends(get_session)):
    try:
        gid = uuid.UUID(generation_id)
    except ValueError:
        raise HTTPException(404, "Not found.")
    record = session.get(m.AIGeneration, gid)
    if record is None:
        raise HTTPException(404, "Not found.")
    require_owned_request(session, str(record.design_request_id), request)
    if not record.storage_key:
        raise HTTPException(404, "No image stored.")
    return Response(
        content=get_storage().get(record.storage_key),
        media_type="image/png",
        headers={"Cache-Control": "private, no-store",
                 "X-AI-Preview": "true", "X-Guard-Status": record.guard_status},
    )


@router.get("/versions/{version_id}/generations")
def list_generations(version_id: str, request: Request, session: Session = Depends(get_session)):
    version = require_owned_version(session, version_id, request)
    rows = session.execute(
        select(m.AIGeneration).where(m.AIGeneration.design_version_id == version.id)
    ).scalars().all()
    return [
        {
            "generation_id": str(r.id),
            "scene": r.visual_brief.get("scene"),
            "material": r.visual_brief.get("material"),
            "quality": r.quality,
            "guard_status": r.guard_status,
            "cost_usd": r.cost_usd,
            "image_url": f"/api/visual/generations/{r.id}/image",
        }
        for r in rows
    ]


@router.get("/product-skills")
def product_skills():
    return {name: skill.model_dump() for name, skill in PRODUCT_SKILLS.items()}


@router.get("/product-skills/{product}")
def product_skill(product: str):
    try:
        return load_skill(product).model_dump()
    except KeyError:
        raise HTTPException(404, "No skill for that product type.")


@router.get("/designs/{design_id}/lineage")
def lineage(design_id: str, request: Request, session: Session = Depends(get_session)):
    req = require_owned_request(session, design_id, request)
    design = session.execute(
        select(m.Design).where(m.Design.request_id == req.id)
    ).scalars().first()
    if design is None:
        raise HTTPException(404, "No design selected yet.")
    return design_lineage(session, design.id)


@router.get("/versions/{version_id}/confidence")
def confidence(version_id: str, request: Request, session: Session = Depends(get_session)):
    version = require_owned_version(session, version_id, request)
    latest_guard = session.execute(
        select(m.AIGeneration)
        .where(m.AIGeneration.design_version_id == version.id)
        .order_by(m.AIGeneration.created_at.desc())
    ).scalars().first()
    report = compute_confidence(
        identity_verified=version.identity_verified,
        validation_passed=version.validation_passed,
        preview_guard=latest_guard.guard_report if latest_guard else None,
    )
    return report.model_dump()


class JuryRequest(BaseModel):
    tier: str = "primary"


@router.post("/versions/{version_id}/jury")
def jury(version_id: str, body: JuryRequest, request: Request, session: Session = Depends(get_session)):
    """Structured Design Jury (ONE Claude call, four normalized scores).
    Advisory only — never overrides Arabic/manufacturing gates."""
    version = require_owned_version(session, version_id, request)
    summary = {
        "product_type": (version.recipe or {}).get("dna", {}).get("family", "pendant"),
        "composition": (version.recipe or {}).get("composition"),
        "identity_verified": version.identity_verified,
        "manufacturing_passed": version.validation_passed,
        "manufacturing_score": version.manufacturing_score,
    }
    try:
        verdict, usage = run_design_jury(summary, tier=body.tier)
    except LLMUnavailable as exc:
        return {"status": "SKIPPED_EXTERNAL_MODEL", "reason": exc.reason}
    return {"status": "OK", "verdict": verdict.model_dump(), "overall": verdict.overall, "usage": usage}


@router.get("/designs/{design_id}/spend")
def spend(design_id: str, request: Request, session: Session = Depends(get_session)):
    req = require_owned_request(session, design_id, request)
    from ..ai.agents import MAX_AI_COST_PER_SESSION_USD

    return {
        "session_spend_usd": vs.session_spend_usd(session, req.id),
        "max_ai_cost_per_session_usd": MAX_AI_COST_PER_SESSION_USD,
    }


class InternalToolCallRequest(BaseModel):
    agent_name: str
    job_id: str
    request_id: str | None = None
    input: dict = Field(default_factory=dict)


@orchestration_router.post("/internal/tools/{tool_name}")
def internal_tool_call(
    tool_name: str, body: InternalToolCallRequest, request: Request, session: Session = Depends(get_session)
):
    """MCP-style callback target for the isolated Hermes runtime
    (services/hermes/app/tool_client.py) — Hermes decides which tool to
    call; this process is the only one that ever executes it (it owns
    the DB session + deterministic engines, app/ai/tools.py). Closed by
    default: INTERNAL_TOOL_TOKEN is unset unless a deployment explicitly
    runs Hermes in isolated mode, in which case both processes must be
    given the same shared secret out of band (never checked into the
    repo — see backend/.env.example)."""
    if not INTERNAL_TOOL_TOKEN or request.headers.get("X-Internal-Tool-Token") != INTERNAL_TOOL_TOKEN:
        raise HTTPException(403, "Internal tool endpoint requires a valid X-Internal-Tool-Token.")
    kwargs = dict(body.input)
    if body.request_id and "request_id" not in kwargs:
        kwargs["request_id"] = body.request_id
    orch = Orchestrator(job_id=body.job_id)
    try:
        result = orch.call_tool(body.agent_name, tool_name, session, **kwargs)
    except (ToolNotPermitted, ToolExecutionError) as exc:
        raise HTTPException(422, str(exc))
    return {"status": "OK", "result": result}
