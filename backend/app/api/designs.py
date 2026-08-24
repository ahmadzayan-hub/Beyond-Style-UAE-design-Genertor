"""Minimal API exercising the P0 backend Golden Path.

Flow: create design (draft) → confirm exact text → generate candidates
(≥30 internal, diverse top 10 returned) → fetch candidate SVG / DXF.

Storage is in-memory for this slice (PostgreSQL persistence is a later
slice); state transitions and the immutability of confirmed source text
are enforced here.
"""
from __future__ import annotations

import unicodedata
import uuid

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..config import DEFAULT_RULES
from ..engines.generator import diversity_score, generate_candidates
from ..exporters.dxf_exporter import ProductionExportBlocked, export_dxf
from ..exporters.svg_exporter import export_svg
from ..fonts.registry import get_registry
from ..schemas.jewellery_design import (
    DesignState,
    ImmutableSourceText,
    JewelleryDesign,
)

router = APIRouter(prefix="/api/designs", tags=["designs"])
fonts_router = APIRouter(prefix="/api/fonts", tags=["fonts"])

# In-memory store for the P0 slice only.
_DESIGNS: dict[str, JewelleryDesign] = {}


class CreateDesignRequest(BaseModel):
    text: str = Field(min_length=1, max_length=120)
    product_type: str = "pendant"


class ConfirmTextRequest(BaseModel):
    confirmed_text: str


@router.post("", status_code=201)
def create_design(req: CreateDesignRequest):
    design = JewelleryDesign(
        design_id=uuid.uuid4().hex[:12],
        source_text=ImmutableSourceText.create(req.text),
        rules=DEFAULT_RULES,
        product_type=req.product_type,
    )
    _DESIGNS[design.design_id] = design
    return {
        "design_id": design.design_id,
        "state": design.state,
        "normalized_text": design.source_text.normalized_text,
        "source_text_sha256": design.source_text.sha256,
        "requires_confirmation": True,
    }


@router.post("/{design_id}/confirm")
def confirm_text(design_id: str, req: ConfirmTextRequest):
    design = _get(design_id)
    if design.state != DesignState.DRAFT:
        raise HTTPException(409, "Text already confirmed.")
    if unicodedata.normalize("NFC", req.confirmed_text) != design.source_text.normalized_text:
        raise HTTPException(
            422,
            "Confirmed text does not exactly match the original text. "
            "Source text is immutable; create a new design to change it.",
        )
    confirmed = ImmutableSourceText.create(design.source_text.raw_text, confirmed=True)
    design = design.model_copy(update={"source_text": confirmed, "state": DesignState.TEXT_CONFIRMED})
    _DESIGNS[design_id] = design
    return {"design_id": design_id, "state": design.state, "confirmed": True}


@router.post("/{design_id}/candidates")
def generate(design_id: str):
    design = _get(design_id)
    if design.state == DesignState.DRAFT:
        raise HTTPException(409, "Exact source text must be confirmed before generation.")
    all_candidates, top = generate_candidates(design_id, design.source_text, design.rules)
    design = design.model_copy(
        update={
            "candidates": all_candidates,
            "top_candidate_ids": [c.candidate_id for c in top],
            "state": DesignState.CANDIDATES_GENERATED,
        }
    )
    _DESIGNS[design_id] = design
    return {
        "design_id": design_id,
        "internal_candidate_count": len(all_candidates),
        "valid_candidate_count": sum(
            1 for c in all_candidates if c.validation and c.validation.passed
        ),
        "diversity_min_pairwise": diversity_score(top),
        "top": [
            {
                "candidate_id": c.candidate_id,
                "rank": c.diversity_rank,
                "recipe_id": c.recipe.recipe_id,
                "name": c.recipe.name,
                "font_id": c.recipe.font_id,
                "composition": c.recipe.composition,
                "score": c.score,
                "width_mm": c.features.width_mm if c.features else None,
                "height_mm": c.features.height_mm if c.features else None,
                "source_text_sha256": c.source_text_sha256,
            }
            for c in top
        ],
    }


@router.get("/{design_id}")
def get_design(design_id: str):
    design = _get(design_id)
    return {
        "design_id": design.design_id,
        "schema_version": design.schema_version,
        "state": design.state,
        "product_type": design.product_type,
        "source_text": {
            "normalized_text": design.source_text.normalized_text,
            "sha256": design.source_text.sha256,
            "confirmed": design.source_text.confirmed,
        },
        "rules_profile": design.rules.profile_name,
        "internal_candidate_count": len(design.candidates),
        "top_candidate_ids": design.top_candidate_ids,
    }


@router.get("/{design_id}/candidates/{candidate_id}/validation")
def get_validation(design_id: str, candidate_id: str):
    _, candidate = _get_candidate(design_id, candidate_id)
    return candidate.validation


@router.get("/{design_id}/candidates/{candidate_id}/svg")
def get_svg(design_id: str, candidate_id: str):
    design, candidate = _get_candidate(design_id, candidate_id)
    svg = export_svg(candidate, design.source_text)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{design_id}/candidates/{candidate_id}/dxf")
def get_dxf(design_id: str, candidate_id: str):
    design, candidate = _get_candidate(design_id, candidate_id)
    try:
        dxf = export_dxf(candidate, design.source_text)
    except ProductionExportBlocked as exc:
        raise HTTPException(423, str(exc))
    return Response(
        content=dxf,
        media_type="application/dxf",
        headers={
            "Content-Disposition": f'attachment; filename="{design_id}-{candidate_id}.dxf"'
        },
    )


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


def _get(design_id: str) -> JewelleryDesign:
    if design_id not in _DESIGNS:
        raise HTTPException(404, "Design not found.")
    return _DESIGNS[design_id]


def _get_candidate(design_id: str, candidate_id: str):
    design = _get(design_id)
    for c in design.candidates:
        if c.candidate_id == candidate_id:
            return design, c
    raise HTTPException(404, "Candidate not found.")
