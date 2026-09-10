"""Real tool wiring for Hermes/Orchestrator agents.

Every tool is a thin, strictly-schemad wrapper around an EXISTING
deterministic service/engine function — nothing here re-implements
Arabic shaping, geometry, validation or approval logic. Agents can only
reach these through `Orchestrator.call_tool` (policy allow-list +
budget + durable audit, see app/ai/agents.py); this module never talks
to the DB session outside a service/engine call, so "agent output
cannot directly mutate DB/files" holds by construction:

  - analyze_reference / generate_design_recipes / repair_geometry /
    create_visual_preview only ever create NEW rows (reference DNA,
    candidates, an UNAPPROVED version, an AI preview) through the same
    service functions the HTTP API uses — never touch approved/locked
    data (DB-trigger-protected, ADR-0001).
  - validate_arabic / validate_manufacturing / rank_candidates /
    retrieve_design_memory are read/compute-only.
  - approve_design is wired for completeness (schema + real function),
    but is registered in agents.WRITE_TOOLS_REQUIRING_HUMAN, so
    Orchestrator.check_tool blocks it unconditionally before
    execute_tool is ever reached — no agent can lock a version.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Type

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DEFAULT_RULES
from ..db import models as m
from ..engines.arabic_engine import shape_text, verify_identity
from ..engines.generator import build_geometry_for_recipe
from ..engines.validator import validate as validate_geometry
from ..schemas.jewellery_design import RecipeParams
from ..services import design_memory as dm_service
from ..services import design_service as svc
from ..services import reference_intelligence as ref_service
from ..services import visual_studio as vs


# ------------------------------------------------------------- analyze_reference


class AnalyzeReferenceInput(BaseModel):
    reference_id: uuid.UUID


class AnalyzeReferenceOutput(BaseModel):
    reference_id: uuid.UUID
    dna: dict
    copy_risk_status: str


def _analyze_reference(session: Session, reference_id: uuid.UUID) -> dict:
    row = ref_service.analyze_reference(session, reference_id)
    return {"reference_id": row.reference_id, "dna": row.dna, "copy_risk_status": ref_service.copy_risk_status(row)}


# --------------------------------------------------------- retrieve_design_memory


class RetrieveDesignMemoryInput(BaseModel):
    #: Optional product focus. When given, the response also carries the
    #: expert specification brief (trade standards with evidence levels +
    #: proven lessons from the Golden Production Memory) for that product.
    product: str | None = None
    audience: str | None = None
    material: str | None = None
    text_length: int | None = None


class RetrieveDesignMemoryOutput(BaseModel):
    recipe_family_weights: dict[str, float]
    workshop_failure_constraints: list[dict]
    expert_brief: dict | None = None


def _retrieve_design_memory(session: Session, product: str | None = None, audience: str | None = None,
                            material: str | None = None, text_length: int | None = None) -> dict:
    from ..services.specifications import expert_brief

    out = {
        "recipe_family_weights": dm_service.recipe_family_weights(session),
        "workshop_failure_constraints": dm_service.workshop_failure_constraints(session),
        "expert_brief": None,
    }
    if product:
        out["expert_brief"] = expert_brief(product, audience=audience, material=material, text_length=text_length)
    return out


# --------------------------------------------------------- generate_design_recipes


class GenerateDesignRecipesInput(BaseModel):
    request_id: uuid.UUID


class GenerateDesignRecipesOutput(BaseModel):
    internal_count: int
    top_candidate_keys: list[str]


def _generate_design_recipes(session: Session, request_id: uuid.UUID) -> dict:
    result = svc.generate_and_persist_candidates(session, request_id)
    return {
        "internal_count": len(result["all"]),
        "top_candidate_keys": [c.candidate_id for c in result["top"]],
    }


# ------------------------------------------------------------------ validate_arabic


class ValidateArabicInput(BaseModel):
    text: str
    font_id: str = "amiri-regular"


class ValidateArabicOutput(BaseModel):
    verified: bool
    uncovered_codepoint_count: int
    notdef_glyph_count: int


def _validate_arabic(session: Session, text: str, font_id: str = "amiri-regular") -> dict:
    runs = shape_text(text, font_id)
    proof = verify_identity(text, runs)
    return {
        "verified": proof.verified,
        "uncovered_codepoint_count": len(proof.uncovered_codepoint_indices),
        "notdef_glyph_count": proof.notdef_glyph_count,
    }


# ------------------------------------------------------------- validate_manufacturing


class ValidateManufacturingInput(BaseModel):
    text: str
    recipe: dict
    font_id: str = "amiri-regular"


class ValidateManufacturingOutput(BaseModel):
    passed: bool
    production_export_allowed: bool
    violations: list[dict]


def _validate_manufacturing(session: Session, text: str, recipe: dict, font_id: str = "amiri-regular") -> dict:
    recipe_obj = RecipeParams(**{**recipe, "font_id": font_id})
    _runs, proof, built = build_geometry_for_recipe(text, recipe_obj, DEFAULT_RULES)
    from ..engines.generator import EXPECTED_LOOPS
    expected_loops = EXPECTED_LOOPS[recipe_obj.loops]
    report = validate_geometry(built, DEFAULT_RULES, proof, expected_loops=expected_loops)
    return {
        "passed": report.passed,
        "production_export_allowed": report.production_export_allowed,
        "violations": [v.model_dump(mode="json") for v in report.violations],
    }


# ----------------------------------------------------------------- repair_geometry


class RepairGeometryInput(BaseModel):
    version_id: uuid.UUID
    created_by: str = "ai_repair_tool"


class RepairGeometryOutput(BaseModel):
    version_id: uuid.UUID
    parent_version_id: uuid.UUID
    validation_passed: bool


def _repair_geometry(session: Session, version_id: uuid.UUID, created_by: str = "ai_repair_tool") -> dict:
    """Deterministic auto-repair only (see api/designs.py:apply_repair) —
    thickens strokes toward the manufacturable minimum. Never touches
    source text; always produces a NEW UNAPPROVED version."""
    parent = session.get(m.DesignVersion, version_id)
    if parent is None:
        raise KeyError("version not found")
    recipe = RecipeParams(**parent.recipe)
    overrides = {"stroke_delta_mm": round(recipe.stroke_delta_mm + 0.1, 3)}
    new_version = svc.edit_version(
        session, parent.id, overrides, note="auto-repair: thicken strokes", created_by=created_by
    )
    return {
        "version_id": new_version.id,
        "parent_version_id": parent.id,
        "validation_passed": new_version.validation_passed,
    }


# ------------------------------------------------------------------- rank_candidates


class RankCandidatesInput(BaseModel):
    request_id: uuid.UUID
    top_n: int = 10


class RankCandidatesOutput(BaseModel):
    ranked: list[dict]


def _rank_candidates(session: Session, request_id: uuid.UUID, top_n: int = 10) -> dict:
    """Reads the already-ranked/diverse candidates the deterministic
    generator+ranking engine persisted — this tool never re-scores."""
    rows = (
        session.execute(
            select(m.DesignCandidateRow)
            .where(
                m.DesignCandidateRow.request_id == request_id,
                m.DesignCandidateRow.diversity_rank.isnot(None),
            )
            .order_by(m.DesignCandidateRow.diversity_rank)
            .limit(top_n)
        )
        .scalars()
        .all()
    )
    return {
        "ranked": [
            {"candidate_key": r.candidate_key, "score": r.score, "diversity_rank": r.diversity_rank}
            for r in rows
        ]
    }


# -------------------------------------------------------------- create_visual_preview


class CreateVisualPreviewInput(BaseModel):
    version_id: uuid.UUID
    request_id: uuid.UUID
    scene: str = "clean_design"
    material: str = "silver-925"


class CreateVisualPreviewOutput(BaseModel):
    generation_id: uuid.UUID
    guard_status: str
    cost_usd: float


def _create_visual_preview(
    session: Session, version_id: uuid.UUID, request_id: uuid.UUID,
    scene: str = "clean_design", material: str = "silver-925",
) -> dict:
    version = session.get(m.DesignVersion, version_id)
    if version is None:
        raise KeyError("version not found")
    brief = vs.build_brief(version, scene=scene, material=material)
    record = vs.generate_preview(session, version, request_id, brief)
    return {"generation_id": record.id, "guard_status": record.guard_status, "cost_usd": record.cost_usd}


# ------------------------------------------------------------------- approve_design


class ApproveDesignInput(BaseModel):
    version_id: uuid.UUID
    confirmed_text: str
    source_text_sha256: str
    geometry_hash: str
    approved_by: str


class ApproveDesignOutput(BaseModel):
    approval_id: uuid.UUID
    status: str


def _approve_design(
    session: Session, version_id: uuid.UUID, confirmed_text: str,
    source_text_sha256: str, geometry_hash: str, approved_by: str,
) -> dict:
    """Wired for completeness only — see module docstring. This function
    is real and callable directly by the HTTP API/tests, but
    Orchestrator.call_tool can never reach it: 'approve_design' is in
    agents.WRITE_TOOLS_REQUIRING_HUMAN and check_tool blocks it first."""
    approval = svc.approve_version(
        session, version_id=version_id, confirmed_text=confirmed_text,
        source_text_sha256=source_text_sha256, geometry_hash=geometry_hash, approved_by=approved_by,
    )
    return {"approval_id": approval.id, "status": approval.status}


# ------------------------------------------------------------------------ registry


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    fn: Callable[..., dict]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "analyze_reference": ToolSpec("analyze_reference", AnalyzeReferenceInput, AnalyzeReferenceOutput, _analyze_reference),
    "retrieve_design_memory": ToolSpec("retrieve_design_memory", RetrieveDesignMemoryInput, RetrieveDesignMemoryOutput, _retrieve_design_memory),
    "generate_design_recipes": ToolSpec("generate_design_recipes", GenerateDesignRecipesInput, GenerateDesignRecipesOutput, _generate_design_recipes),
    "validate_arabic": ToolSpec("validate_arabic", ValidateArabicInput, ValidateArabicOutput, _validate_arabic),
    "validate_manufacturing": ToolSpec("validate_manufacturing", ValidateManufacturingInput, ValidateManufacturingOutput, _validate_manufacturing),
    "repair_geometry": ToolSpec("repair_geometry", RepairGeometryInput, RepairGeometryOutput, _repair_geometry),
    "rank_candidates": ToolSpec("rank_candidates", RankCandidatesInput, RankCandidatesOutput, _rank_candidates),
    "create_visual_preview": ToolSpec("create_visual_preview", CreateVisualPreviewInput, CreateVisualPreviewOutput, _create_visual_preview),
    "approve_design": ToolSpec("approve_design", ApproveDesignInput, ApproveDesignOutput, _approve_design),
}


def execute_tool(name: str, session: Session, **kwargs) -> dict:
    """Validate input, run the real service/engine call, validate output.
    Raises KeyError for an unknown tool name — callers (Orchestrator)
    are responsible for the allow-list/policy check beforehand."""
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {name}")
    spec = TOOL_REGISTRY[name]
    validated_input = spec.input_schema(**kwargs)
    result = spec.fn(session, **validated_input.model_dump())
    return spec.output_schema(**result).model_dump(mode="json")
