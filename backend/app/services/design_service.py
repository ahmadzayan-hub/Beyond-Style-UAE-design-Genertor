"""Persistent design lifecycle service (P0 persistence slice).

DesignRequest → candidates → selection (Design + version 1) → designer
edits (new versions) → customer approval (immutable APPROVED_LOCKED) →
authorized production export. Every step emits append-only audit events.

PostgreSQL relational state is the source of truth; DB triggers back up
the immutability rules enforced here (ADR-0001).
"""
from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import (
    ARABIC_ENGINE_VERSION,
    GENERATOR_VERSION,
    SCHEMA_VERSION,
    DEFAULT_RULES,
    WorkshopRules,
)
from ..db import models as m
from ..engines.arabic_engine import shape_text, verify_identity
from ..engines.generator import (
    EXPECTED_LOOPS,
    build_geometry_for_recipe,
    diversity_score,
    generate_candidates,
    load_recipe_library,
)
from ..engines.geometry_engine import compose
from ..engines.ranking import DEFAULT_RANKING
from ..engines.validator import validate
from ..engines.vector_edit import VectorEditRejected, apply_ops
from ..exporters.dxf_exporter import ProductionExportBlocked, export_dxf
from ..exporters.svg_exporter import export_svg
from ..fonts.registry import get_registry
from ..schemas.jewellery_design import (
    DesignCandidate,
    ImmutableSourceText,
    RecipeParams,
    TextIdentityProof,
    ValidationReport,
    ValidationSeverity,
)

CONFIRMATION_STATEMENT_EN = "I confirm the spelling and final design."
CONFIRMATION_STATEMENT_AR = "أؤكد صحة الإملاء والتصميم النهائي."

#: Recipe fields a designer edit may override (visual only — never text).
EDITABLE_RECIPE_FIELDS = {
    "letter_spacing_mm",
    "x_scale",
    "y_scale",
    "stroke_delta_mm",
    "composition",
    "connector_height_mm",
    "loops",
    "frame_margin_mm",
    "target_height_mm",
    "dot_strategy",
    "font_id",
    # A weight change is a real design edit: it re-renders the geometry and
    # therefore creates a NEW immutable version, never mutating an approved
    # one. Coordinates are validated against the font before use.
    "font_axes",
    "ot_feature_set",
    # Ring spec (size/band height/border) — a resize is a real geometry
    # change and versions like any other edit. Never present on silhouette
    # products, so it cannot convert a pendant into a ring by edit.
    "ring",
    "dot_style",
    "swash",
    "kashida_count",
    "max_lines",
    "line_spacing_ratio",
}


class ConflictError(Exception):
    """State conflict (wrong status, race, duplicate)."""


class ApprovalRejected(Exception):
    """Approval preconditions failed."""


def _geometry_hash(wkt: str) -> str:
    return hashlib.sha256(wkt.encode("utf-8")).hexdigest()


def _design_geometry_hash(
    recipe: dict, geometry_wkt: str, text_wkt: str | None, inner_wkt: str | None
) -> str:
    """Version identity hash. Silhouette products: the CUT geometry alone
    (unchanged, so no existing version is renumbered). Engraved bands: every
    ring shares the same CUT rectangle, so the hash must also bind BOTH
    engrave layers — otherwise two different engravings would be
    hash-identical and the approval lock would not distinguish them."""
    if (recipe or {}).get("ring") is not None:
        payload = f"{geometry_wkt}|ENGRAVE|{text_wkt or ''}|INNER|{inner_wkt or ''}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return _geometry_hash(geometry_wkt)


def _version_geometry_hash(version: "m.DesignVersion") -> str:
    return _design_geometry_hash(
        version.recipe or {},
        version.geometry_wkt,
        version.text_geometry_wkt,
        version.inner_text_geometry_wkt,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _emit(
    session: Session,
    event_type: str,
    request_id=None,
    design_id=None,
    version_id=None,
    actor: str = "system",
    actor_type: str = "system",
    metadata: dict | None = None,
) -> None:
    session.add(
        m.DesignEvent(
            request_id=request_id,
            design_id=design_id,
            version_id=version_id,
            event_type=event_type,
            actor=actor,
            actor_type=actor_type,
            event_metadata=metadata,
        )
    )


# ---------------------------------------------------------------- requests


def create_request(
    session: Session,
    text: str,
    product_type: str,
    actor: str = "customer",
    session_token_hash: str | None = None,
) -> m.DesignRequest:
    from ..engines.text_integrity import TextIntegrityError, inspect

    report = inspect(text)
    if report.status == "FAIL":
        # Never auto-correct: the customer re-enters the text explicitly.
        raise TextIntegrityError(report)
    src = ImmutableSourceText.create(text)
    req = m.DesignRequest(
        schema_version=SCHEMA_VERSION,
        source_text_raw=src.raw_text,
        source_text_normalized=src.normalized_text,
        source_text_sha256=src.sha256,
        product_type=product_type,
        status="DRAFT",
        session_token_hash=session_token_hash,
    )
    session.add(req)
    session.flush()
    _emit(session, "REQUEST_CREATED", request_id=req.id, actor=actor, actor_type="customer",
          metadata={"sha256": src.sha256})
    return req


def confirm_request_text(session: Session, request_id: uuid.UUID, confirmed_text: str, actor: str = "customer") -> m.DesignRequest:
    req = session.get(m.DesignRequest, request_id)
    if req is None:
        raise KeyError("request not found")
    if req.status != "DRAFT":
        raise ConflictError("Text already confirmed.")
    if unicodedata.normalize("NFC", confirmed_text) != req.source_text_normalized:
        raise ApprovalRejected(
            "Confirmed text does not exactly match the original text. "
            "Source text is immutable; create a new request to change it."
        )
    req.confirmed = True
    req.confirmed_at = _utcnow()
    req.status = "TEXT_CONFIRMED"
    # Mirror into the intake brief: confirmed_text comes ONLY from here
    # (explicit customer confirmation) — never from OCR/vision.
    brief = session.execute(
        select(m.CustomerBrief).where(m.CustomerBrief.design_request_id == req.id)
    ).scalar_one_or_none()
    if brief is not None:
        brief.confirmed_text = req.source_text_normalized
        brief.missing_fields = [f for f in (brief.missing_fields or []) if f != "confirmed_text"]
        if not brief.missing_fields:
            brief.status = "READY"
    _emit(session, "TEXT_CONFIRMED", request_id=req.id, actor=actor, actor_type="customer")
    return req


# -------------------------------------------------------------- candidates


def generate_and_persist_candidates(
    session: Session, request_id: uuid.UUID, rules: WorkshopRules = DEFAULT_RULES
) -> dict:
    req = session.get(m.DesignRequest, request_id)
    if req is None:
        raise KeyError("request not found")
    if req.status == "DRAFT":
        raise ConflictError("Exact source text must be confirmed before generation.")

    brief = session.execute(
        select(m.CustomerBrief).where(m.CustomerBrief.design_request_id == req.id)
    ).scalar_one_or_none()
    hints = brief.generation_hints if brief else None
    trace: dict = {}

    source = ImmutableSourceText.create(req.source_text_raw, confirmed=True)
    if req.product_type == "ring":
        from ..engines.ring_band import generate_ring_candidates

        all_candidates, top = generate_ring_candidates(str(req.id), source, rules, hints=hints)
    else:
        all_candidates, top = generate_candidates(str(req.id), source, rules, hints=hints, trace=trace)

    # Idempotent per request: regeneration replaces nothing — same
    # deterministic candidate_keys conflict-skip via unique constraint.
    existing = set(
        session.execute(
            select(m.DesignCandidateRow.candidate_key).where(
                m.DesignCandidateRow.request_id == req.id
            )
        ).scalars()
    )
    rank_by_key = {c.candidate_id: c.diversity_rank for c in top}
    for c in all_candidates:
        if c.candidate_id in existing:
            continue
        session.add(
            m.DesignCandidateRow(
                request_id=req.id,
                candidate_key=c.candidate_id,
                schema_version=SCHEMA_VERSION,
                recipe=c.recipe.model_dump(),
                features=c.features.model_dump() if c.features else None,
                validation=c.validation.model_dump() if c.validation else None,
                identity_verified=c.identity_proof.verified,
                validation_passed=bool(c.validation and c.validation.passed),
                score=c.score,
                score_breakdown=c.score_breakdown,
                ranking_config_version=c.ranking_config_version or DEFAULT_RANKING.version,
                diversity_rank=rank_by_key.get(c.candidate_id),
                geometry_wkt=c.geometry_wkt,
                text_geometry_wkt=c.text_geometry_wkt or None,
                inner_text_geometry_wkt=c.inner_text_geometry_wkt or None,
                quality_report=c.quality_report,
                source_text_sha256=c.source_text_sha256,
            )
        )
    req.status = "CANDIDATES_GENERATED"
    req.ranking_config_version = DEFAULT_RANKING.version
    _emit(
        session,
        "CANDIDATES_GENERATED",
        request_id=req.id,
        metadata={
            "internal": len(all_candidates),
            "valid": sum(1 for c in all_candidates if c.validation and c.validation.passed),
            "top": [c.candidate_id for c in top],
            "diversity_min_pairwise": diversity_score(top),
            "ranking_config_version": DEFAULT_RANKING.version,
            "retrieval": trace.get("retrieval"),
        },
    )
    return {"all": all_candidates, "top": top, "request": req}


# ------------------------------------------------------ selection/versions


def select_candidate(
    session: Session, request_id: uuid.UUID, candidate_key: str, actor: str = "customer"
) -> tuple[m.Design, m.DesignVersion]:
    req = session.get(m.DesignRequest, request_id)
    if req is None:
        raise KeyError("request not found")
    row = session.execute(
        select(m.DesignCandidateRow).where(
            m.DesignCandidateRow.request_id == request_id,
            m.DesignCandidateRow.candidate_key == candidate_key,
        )
    ).scalar_one_or_none()
    if row is None:
        raise KeyError("candidate not found")
    if not row.validation_passed:
        raise ConflictError("Cannot select a candidate that failed validation.")

    design = m.Design(request_id=request_id, selected_candidate_id=row.id)
    session.add(design)
    session.flush()
    version = _create_version_row(
        session,
        design,
        source_text=req.source_text_normalized,
        source_sha=req.source_text_sha256,
        recipe=RecipeParams(**row.recipe),
        geometry_wkt=row.geometry_wkt,
        text_geometry_wkt=row.text_geometry_wkt,
        inner_text_geometry_wkt=row.inner_text_geometry_wkt,
        validation=row.validation,
        identity_verified=row.identity_verified,
        score=row.score,
        created_by=actor,
        parent_version_id=None,
        edit_metadata={"origin": "candidate_selection", "candidate_key": candidate_key},
    )
    _emit(session, "DESIGN_SELECTED", request_id=req.id, design_id=design.id,
          version_id=version.id, actor=actor, actor_type="customer",
          metadata={"candidate_key": candidate_key})
    return design, version


def _create_version_row(
    session: Session,
    design: m.Design,
    source_text: str,
    source_sha: str,
    recipe: RecipeParams,
    geometry_wkt: str,
    validation: dict,
    text_geometry_wkt: str | None,
    inner_text_geometry_wkt: str | None,
    identity_verified: bool,
    score: float,
    created_by: str,
    parent_version_id,
    edit_metadata: dict | None,
) -> m.DesignVersion:
    # Row-lock the design to serialize version-number allocation.
    locked = session.execute(
        select(m.Design).where(m.Design.id == design.id).with_for_update()
    ).scalar_one()
    next_number = locked.current_version_number + 1
    font = get_registry().get(recipe.font_id)
    lib = load_recipe_library()
    version = m.DesignVersion(
        design_id=design.id,
        version_number=next_number,
        parent_version_id=parent_version_id,
        status="UNAPPROVED",
        immutable_source_text=source_text,
        source_text_sha256=source_sha,
        geometry_wkt=geometry_wkt,
        text_geometry_wkt=text_geometry_wkt,
        inner_text_geometry_wkt=inner_text_geometry_wkt,
        geometry_hash=_design_geometry_hash(
            recipe.model_dump(), geometry_wkt, text_geometry_wkt, inner_text_geometry_wkt
        ),
        schema_version=SCHEMA_VERSION,
        arabic_engine_version=ARABIC_ENGINE_VERSION,
        font_id=font.font_id,
        font_version=font.computed_sha256,
        recipe_id=recipe.recipe_id,
        recipe_version=lib["library_version"],
        recipe=recipe.model_dump(),
        manufacturing_rules_version=DEFAULT_RULES.rules_version,
        validation=validation,
        validation_passed=bool(validation and validation.get("passed")),
        identity_verified=identity_verified,
        manufacturing_score=score,
        created_by=created_by,
        edit_metadata=edit_metadata,
    )
    session.add(version)
    locked.current_version_number = next_number
    session.flush()
    _emit(session, "VERSION_CREATED", design_id=design.id, version_id=version.id,
          actor=created_by, actor_type="designer" if parent_version_id else "system",
          metadata={"version_number": next_number})
    session.add(
        m.ManufacturingValidationRun(
            version_id=version.id,
            rules_profile=DEFAULT_RULES.profile_name,
            rules_version=DEFAULT_RULES.rules_version,
            rules_snapshot=DEFAULT_RULES.model_dump(),
            passed=version.validation_passed,
            violations=(validation or {}).get("violations"),
        )
    )
    _emit(
        session,
        "VALIDATION_PASSED" if version.validation_passed else "VALIDATION_FAILED",
        design_id=design.id,
        version_id=version.id,
    )
    return version


def edit_version(
    session: Session,
    version_id: uuid.UUID,
    recipe_overrides: dict,
    note: str | None,
    created_by: str,
    rules: WorkshopRules = DEFAULT_RULES,
) -> m.DesignVersion:
    """Designer edit → NEW version. Never mutates the parent. Never touches
    source text (overrides limited to visual recipe parameters)."""
    parent = session.get(m.DesignVersion, version_id)
    if parent is None:
        raise KeyError("version not found")
    illegal = set(recipe_overrides) - EDITABLE_RECIPE_FIELDS
    if illegal:
        raise ApprovalRejected(f"Fields not editable (source text is immutable): {sorted(illegal)}")
    if "ring" in recipe_overrides:
        # A ring edit adjusts the ring spec; it can never convert a
        # silhouette product into a ring (or back) mid-lineage.
        was_ring = (parent.recipe or {}).get("ring") is not None
        will_be_ring = recipe_overrides["ring"] is not None
        if was_ring != will_be_ring:
            raise ApprovalRejected("Product construction cannot change by edit.")

    design = session.get(m.Design, parent.design_id)
    base_recipe = RecipeParams(**parent.recipe)
    new_recipe = base_recipe.model_copy(update=recipe_overrides)

    # Deterministic re-run of the pipeline on the unchanged source text.
    source = ImmutableSourceText.create(parent.immutable_source_text, confirmed=True)
    runs, proof, built = build_geometry_for_recipe(source.normalized_text, new_recipe, rules)
    # Manual vector edits carried by the lineage are replayed on the
    # regenerated base (fail-safe: a replay that no longer fits is refused
    # with the reason instead of silently dropping the designer's work).
    vector_ops = list((parent.edit_metadata or {}).get("vector_ops") or [])
    op_log: list[dict] = []
    if vector_ops:
        try:
            built, op_log = apply_ops(built, vector_ops, rules)
        except VectorEditRejected as exc:
            raise ApprovalRejected(
                f"Recipe edit refused: replaying the {len(vector_ops)} manual vector edit(s) on the new base failed — {exc}"
            )
    font = get_registry().get(new_recipe.font_id)
    expected_loops = EXPECTED_LOOPS[new_recipe.loops]
    report = validate(
        built, rules, proof,
        font_production_allowed=font.commercial_production_allowed,
        expected_loops=expected_loops,
    )
    version = _create_version_row(
        session,
        design,
        source_text=parent.immutable_source_text,  # unchanged, byte-exact
        source_sha=parent.source_text_sha256,
        recipe=new_recipe,
        geometry_wkt=built.geometry.wkt if not built.geometry.is_empty else "",
        text_geometry_wkt=(built.text_geometry.wkt if built.text_geometry is not None and not built.text_geometry.is_empty else None),
        inner_text_geometry_wkt=(built.inner_text_geometry.wkt if built.inner_text_geometry is not None and not built.inner_text_geometry.is_empty else None),
        validation=report.model_dump(),
        identity_verified=proof.verified,
        score=0.0,
        created_by=created_by,
        parent_version_id=parent.id,
        edit_metadata={"overrides": recipe_overrides, "note": note,
                       "vector_ops": vector_ops, "vector_op_log": op_log},
    )
    _emit(session, "DESIGN_EDITED", design_id=design.id, version_id=version.id,
          actor=created_by, actor_type="designer",
          metadata={"parent_version": parent.version_number, "overrides": recipe_overrides,
                    "vector_ops_replayed": len(vector_ops)})
    return version


def preview_vector_ops(
    version: m.DesignVersion, ops: list[dict], rules: WorkshopRules = DEFAULT_RULES
):
    """Dry run: replay (lineage ops + ops) on the regenerated base and
    validate. Nothing is persisted. Returns (built, report, op_log).
    Raises VectorEditRejected."""
    recipe = RecipeParams(**version.recipe)
    source = ImmutableSourceText.create(version.immutable_source_text, confirmed=True)
    _runs, proof, base = build_geometry_for_recipe(source.normalized_text, recipe, rules)
    prior = list((version.edit_metadata or {}).get("vector_ops") or [])
    cumulative = prior + [{"op": o.get("op"), "params": o.get("params") or {}} for o in ops]
    built, op_log = apply_ops(base, cumulative, rules)
    font = get_registry().get(recipe.font_id)
    report = validate(
        built, rules, proof,
        font_production_allowed=font.commercial_production_allowed,
        expected_loops=max(EXPECTED_LOOPS[recipe.loops], len(built.loop_centers_mm)),
    )
    return built, report, op_log


VECTOR_TOOLS = [
    {"op": "translate", "label_ar": "تحريك", "label_en": "Move",
     "params": {"dx_mm": "number [-200, 200]", "dy_mm": "number [-200, 200]"}},
    {"op": "rotate", "label_ar": "تدوير", "label_en": "Rotate",
     "params": {"angle_deg": "number [-180, 180], about the design centre"}},
    {"op": "scale", "label_ar": "تكبير/تصغير موحّد", "label_en": "Uniform scale",
     "params": {"factor": "number [0.5, 2.0]; strokes re-validated"}},
    {"op": "add_bridge", "label_ar": "إضافة جسر", "label_en": "Add bridge",
     "params": {"from": "[x_mm, y_mm]", "to": "[x_mm, y_mm]", "width_mm": "≥ workshop min bridge"}},
    {"op": "add_ring", "label_ar": "إضافة حلقة تعليق", "label_en": "Add chain ring",
     "params": {"position": "top_center | top_left | top_right | left | right | bottom_center",
                "center": "[x_mm, y_mm] (alternative to position)",
                "inner_diameter_mm": "≥ workshop min", "wall_mm": "≥ workshop min"}},
    {"op": "add_shape", "label_ar": "دمج شكل", "label_en": "Union shape",
     "params": {"shape": "circle | rect | capsule", "center/origin/from/to": "mm", "diameter_mm/width_mm/height_mm": "mm"}},
    {"op": "cut_shape", "label_ar": "قصّ شكل (خارج الحروف فقط)", "label_en": "Cut shape (outside letters only)",
     "params": {"shape": "circle | rect | capsule", "…": "same as add_shape"}},
]
VECTOR_REFUSED = [
    {"op": "mirror", "label_ar": "انعكاس", "label_en": "Mirror",
     "reason_ar": "مرفوض: يعكس اتجاه قراءة النص العربي.", "reason_en": "Refused: would reverse the Arabic reading direction."},
    {"op": "node_edit", "label_ar": "تحرير النقاط (العُقد)", "label_en": "Node editing",
     "reason_ar": "غير متاح بعد — لا نعرض أدوات وهمية.", "reason_en": "Not available yet — no fake tools."},
    {"op": "pen", "label_ar": "أداة القلم", "label_en": "Pen tool",
     "reason_ar": "غير متاح بعد — لا نعرض أدوات وهمية.", "reason_en": "Not available yet — no fake tools."},
]


def fix_ops_from_report(report: ValidationReport, rules: WorkshopRules = DEFAULT_RULES) -> dict[str, list[dict]]:
    """Translate validator-proposed fixes into ready-to-apply vector ops,
    grouped by repair id. Only fixes that map to a real op are emitted."""
    grouped: dict[str, list[dict]] = {}
    for v in report.violations:
        fx = v.proposed_fix
        if fx is None:
            continue
        if fx.action == "add_bridge" and "from" in fx.params and "to" in fx.params:
            width = max(float(fx.params.get("width_mm", rules.min_bridge_mm)), rules.min_bridge_mm)
            grouped.setdefault("connect_floating_parts", []).append(
                {"op": "add_bridge", "params": {"from": list(fx.params["from"]), "to": list(fx.params["to"]), "width_mm": round(width, 3)}}
            )
        elif fx.action == "widen_gap" and v.location_mm is not None:
            gap = float(fx.params.get("min_gap_mm", rules.min_gap_mm)) + 2 * rules.kerf_mm + 0.1
            grouped.setdefault("widen_gaps", []).append(
                {"op": "cut_shape", "params": {"shape": "circle", "center": [v.location_mm[0], v.location_mm[1]],
                                               "diameter_mm": round(gap, 3)}}
            )
        elif fx.action == "enlarge_loop" and v.location_mm is not None:
            grouped.setdefault("rebuild_chain_ring", []).append(
                {"op": "add_ring", "params": {"center": [v.location_mm[0], v.location_mm[1]],
                                              "inner_diameter_mm": rules.loop_inner_diameter_mm,
                                              "wall_mm": rules.loop_wall_mm}}
            )
    return grouped


_REPAIR_LABELS = {
    "connect_floating_parts": ("وصل الأجزاء المنفصلة بجسور حقيقية", "Connect floating parts with real bridges"),
    "rebuild_chain_ring": ("إعادة بناء حلقة التعليق بالمقاس الصحيح", "Rebuild the chain ring at workshop size"),
    "thicken_strokes": ("تحسين قابلية التصنيع (تسميك الخطوط)", "Improve manufacturability (thicken strokes)"),
    "widen_gaps": ("توسيع الفتحات الضيقة (خارج الحروف)", "Widen narrow cut-outs (outside letters)"),
}


def repair_options_for_version(version: m.DesignVersion, rules: WorkshopRules = DEFAULT_RULES) -> list[dict]:
    """Validated repair proposals. Vector repairs are dry-run and offered
    only when they reduce the manufacturing error count; the recipe
    thicken option is offered while there is headroom and is dry-run when
    the version currently fails."""
    recipe = RecipeParams(**version.recipe)
    if recipe.ring is not None:
        return []   # ring-mode repairs are a future slice — offer nothing rather than an untested transformation
    report = ValidationReport(**version.validation)
    errors_before = sum(1 for x in report.violations if x.severity == ValidationSeverity.ERROR)
    options: list[dict] = []
    for repair_id, ops in fix_ops_from_report(report, rules).items():
        try:
            _built, after, _log = preview_vector_ops(version, ops, rules)
        except VectorEditRejected as exc:
            options.append({"repair_id": repair_id, "kind": "vector", "available": False, "reason": str(exc),
                            "label_ar": _REPAIR_LABELS[repair_id][0], "label_en": _REPAIR_LABELS[repair_id][1]})
            continue
        errors_after = sum(1 for x in after.violations if x.severity == ValidationSeverity.ERROR)
        if errors_after < errors_before:
            options.append({"repair_id": repair_id, "kind": "vector", "available": True, "ops": ops,
                            "label_ar": _REPAIR_LABELS[repair_id][0], "label_en": _REPAIR_LABELS[repair_id][1],
                            "errors_before": errors_before, "errors_after": errors_after,
                            "passes_after": after.passed})
    if recipe.stroke_delta_mm < 0.45:
        overrides = {"stroke_delta_mm": round(recipe.stroke_delta_mm + 0.1, 3)}
        opt = {"repair_id": "thicken_strokes", "kind": "recipe", "available": True, "overrides": overrides,
               "label_ar": _REPAIR_LABELS["thicken_strokes"][0], "label_en": _REPAIR_LABELS["thicken_strokes"][1],
               "errors_before": errors_before}
        if errors_before:
            try:
                source = ImmutableSourceText.create(version.immutable_source_text, confirmed=True)
                new_recipe = recipe.model_copy(update=overrides)
                _r, proof, built = build_geometry_for_recipe(source.normalized_text, new_recipe, rules)
                prior = list((version.edit_metadata or {}).get("vector_ops") or [])
                if prior:
                    built, _ = apply_ops(built, prior, rules)
                font = get_registry().get(new_recipe.font_id)
                after = validate(built, rules, proof, font_production_allowed=font.commercial_production_allowed,
                                 expected_loops=max(EXPECTED_LOOPS[new_recipe.loops], len(built.loop_centers_mm)))
                opt["errors_after"] = sum(1 for x in after.violations if x.severity == ValidationSeverity.ERROR)
                opt["passes_after"] = after.passed
                if opt["errors_after"] > errors_before:
                    opt["available"] = False
                    opt["reason"] = "Thickening would add manufacturing errors on this design."
            except VectorEditRejected as exc:
                opt["available"] = False
                opt["reason"] = str(exc)
        options.append(opt)
    return [o for o in options if o.get("available")] + [o for o in options if not o.get("available")]


def vector_tool_catalogue(version: m.DesignVersion, rules: WorkshopRules = DEFAULT_RULES) -> dict:
    from shapely import wkt as shapely_wkt

    geom = shapely_wkt.loads(version.geometry_wkt) if version.geometry_wkt else None
    bounds = [round(b, 3) for b in geom.bounds] if geom is not None and not geom.is_empty else None
    report = ValidationReport(**version.validation)
    meta = version.edit_metadata or {}
    return {
        "version_id": str(version.id),
        "status": version.status,
        "editable": version.status != "APPROVED_LOCKED",
        "bounds_mm": bounds,
        "loop_centers_mm": meta.get("loop_centers_mm"),
        "workshop_minimums": {"bridge_mm": rules.min_bridge_mm, "ring_inner_diameter_mm": rules.loop_inner_diameter_mm,
                              "ring_wall_mm": rules.loop_wall_mm, "stroke_mm": rules.min_stroke_mm},
        "tools": VECTOR_TOOLS,
        "refused": VECTOR_REFUSED,
        "lineage_ops": meta.get("vector_ops") or [],
        "proposed_fix_ops": fix_ops_from_report(report, rules),
        "errors": [x.model_dump(mode="json") for x in report.violations if x.severity == ValidationSeverity.ERROR],
    }


def vector_edit_version(
    session: Session,
    version_id: uuid.UUID,
    ops: list[dict],
    note: str | None,
    created_by: str,
    rules: WorkshopRules = DEFAULT_RULES,
) -> m.DesignVersion:
    """Manual vector edit → NEW version. The parent is never mutated and the
    source text is untouched by construction (ops only see geometry).

    The version records the CUMULATIVE ordered op list (parent ops + new
    ops) replayed on the deterministic base generated from the recipe, so
    the geometry is reproducible from (source text, recipe, ops)."""
    parent = session.get(m.DesignVersion, version_id)
    if parent is None:
        raise KeyError("version not found")
    if not ops:
        raise VectorEditRejected("No operations given.")
    design = session.get(m.Design, parent.design_id)
    recipe = RecipeParams(**parent.recipe)
    source = ImmutableSourceText.create(parent.immutable_source_text, confirmed=True)
    runs, proof, base = build_geometry_for_recipe(source.normalized_text, recipe, rules)
    prior = list((parent.edit_metadata or {}).get("vector_ops") or [])
    cumulative = prior + [{"op": o.get("op"), "params": o.get("params") or {}} for o in ops]
    built, op_log = apply_ops(base, cumulative, rules)   # raises VectorEditRejected
    font = get_registry().get(recipe.font_id)
    report = validate(
        built, rules, proof,
        font_production_allowed=font.commercial_production_allowed,
        expected_loops=max(EXPECTED_LOOPS[recipe.loops], len(built.loop_centers_mm)),
    )
    version = _create_version_row(
        session,
        design,
        source_text=parent.immutable_source_text,
        source_sha=parent.source_text_sha256,
        recipe=recipe,
        geometry_wkt=built.geometry.wkt if not built.geometry.is_empty else "",
        text_geometry_wkt=(built.text_geometry.wkt if built.text_geometry is not None and not built.text_geometry.is_empty else None),
        inner_text_geometry_wkt=(built.inner_text_geometry.wkt if built.inner_text_geometry is not None and not built.inner_text_geometry.is_empty else None),
        validation=report.model_dump(),
        identity_verified=proof.verified,
        score=0.0,
        created_by=created_by,
        parent_version_id=parent.id,
        edit_metadata={"vector_ops": cumulative, "applied_ops": cumulative[len(prior):],
                       "vector_op_log": op_log, "note": note,
                       "loop_centers_mm": [[round(x, 3), round(y, 3)] for x, y in built.loop_centers_mm]},
    )
    _emit(session, "DESIGN_EDITED", design_id=design.id, version_id=version.id,
          actor=created_by, actor_type="designer",
          metadata={"parent_version": parent.version_number, "kind": "vector",
                    "ops": [o["op"] for o in cumulative[len(prior):]], "total_ops": len(cumulative)})
    return version


def change_source_text(
    session: Session,
    version_id: uuid.UUID,
    new_text: str,
    confirmed: bool,
    created_by: str,
    rules: WorkshopRules = DEFAULT_RULES,
) -> m.DesignVersion:
    """Intentional source-text change: new version with new immutable text
    and forced invalidation of ALL active approvals of this design."""
    if not confirmed:
        raise ApprovalRejected("Source text change requires explicit confirmation flag.")
    parent = session.get(m.DesignVersion, version_id)
    if parent is None:
        raise KeyError("version not found")
    design = session.get(m.Design, parent.design_id)
    source = ImmutableSourceText.create(new_text, confirmed=True)
    recipe = RecipeParams(**parent.recipe)
    runs, proof, built = build_geometry_for_recipe(source.normalized_text, recipe, rules)
    font = get_registry().get(recipe.font_id)
    report = validate(
        built, rules, proof,
        font_production_allowed=font.commercial_production_allowed,
        expected_loops=EXPECTED_LOOPS[recipe.loops],
    )
    version = _create_version_row(
        session, design,
        source_text=source.normalized_text,
        source_sha=source.sha256,
        recipe=recipe,
        geometry_wkt=built.geometry.wkt if not built.geometry.is_empty else "",
        text_geometry_wkt=(built.text_geometry.wkt if built.text_geometry is not None and not built.text_geometry.is_empty else None),
        inner_text_geometry_wkt=(built.inner_text_geometry.wkt if built.inner_text_geometry is not None and not built.inner_text_geometry.is_empty else None),
        validation=report.model_dump(),
        identity_verified=proof.verified,
        score=0.0,
        created_by=created_by,
        parent_version_id=parent.id,
        edit_metadata={"source_text_revision": True,
                       # Manual vector edits are anchored in mm to the OLD
                       # text's geometry; they are not carried onto new text.
                       "vector_ops_dropped": len((parent.edit_metadata or {}).get("vector_ops") or [])},
    )
    # Force invalidation of every active approval on this design.
    active = session.execute(
        select(m.CustomerApproval)
        .join(m.DesignVersion, m.CustomerApproval.design_version_id == m.DesignVersion.id)
        .where(m.DesignVersion.design_id == design.id, m.CustomerApproval.status == "ACTIVE")
    ).scalars().all()
    for approval in active:
        approval.status = "INVALIDATED"
        _emit(session, "APPROVAL_INVALIDATED", design_id=design.id,
              version_id=approval.design_version_id,
              metadata={"reason": "source_text_changed", "new_version_id": str(version.id)})
    return version


# ---------------------------------------------------------------- approval


def approve_version(
    session: Session,
    version_id: uuid.UUID,
    confirmed_text: str,
    source_text_sha256: str,
    geometry_hash: str,
    approved_by: str,
    approval_method: str = "api",
) -> m.CustomerApproval:
    """Bind customer confirmation to one exact version and lock it.

    Server-side verification: NFC-exact text, identity PASS, manufacturing
    PASS, font rights PASS, hashes match. Lock is race-safe via
    conditional UPDATE on status.
    """
    version = session.get(m.DesignVersion, version_id)
    if version is None:
        raise KeyError("version not found")
    if version.status != "UNAPPROVED":
        raise ConflictError(f"Version status {version.status} cannot be approved.")
    if unicodedata.normalize("NFC", confirmed_text) != version.immutable_source_text:
        raise ApprovalRejected("Confirmed text does not match the version's immutable source text.")
    if source_text_sha256 != version.source_text_sha256:
        raise ApprovalRejected("Source text hash mismatch.")
    if geometry_hash != version.geometry_hash:
        raise ApprovalRejected("Geometry hash mismatch — the design changed since it was shown.")
    if _version_geometry_hash(version) != version.geometry_hash:
        raise ApprovalRejected("Stored geometry failed hash re-verification.")
    if not version.identity_verified:
        raise ApprovalRejected("Text identity is not verified for this version.")
    if not version.validation_passed:
        raise ApprovalRejected("Manufacturing validation did not pass for this version.")
    font = get_registry().get(version.font_id)
    if not font.commercial_production_allowed:
        raise ApprovalRejected("Font rights do not allow commercial production.")

    approved_at = _utcnow()
    approval_hash = hashlib.sha256(
        f"{version.id}|{version.source_text_sha256}|{version.geometry_hash}|{approved_at.isoformat()}".encode()
    ).hexdigest()

    # Race-safe lock: only one transaction can flip UNAPPROVED → LOCKED.
    locked = (
        session.query(m.DesignVersion)
        .filter(m.DesignVersion.id == version_id, m.DesignVersion.status == "UNAPPROVED")
        .update({"status": "APPROVED_LOCKED"}, synchronize_session="fetch")
    )
    if locked != 1:
        raise ConflictError("Version was approved concurrently.")

    approval = m.CustomerApproval(
        design_version_id=version.id,
        confirmed_text=confirmed_text,
        confirmation_statement=CONFIRMATION_STATEMENT_EN,
        source_text_sha256=version.source_text_sha256,
        geometry_hash=version.geometry_hash,
        approval_hash=approval_hash,
        approved_at=approved_at,
        approved_by=approved_by,
        approval_method=approval_method,
        status="ACTIVE",
    )
    session.add(approval)
    try:
        session.flush()
    except IntegrityError as exc:  # unique(design_version_id) — concurrent double insert
        raise ConflictError("Version already has an approval.") from exc
    # The dimensioned agreement proof is deterministic per version; its hash
    # in the audit trail binds the approval to the exact picture (design +
    # real-mm dimensions + spec block) the customer saw and agreed to.
    proof_sha256 = hashlib.sha256(
        agreement_proof_for_version(session, version).encode("utf-8")
    ).hexdigest()
    _emit(session, "CUSTOMER_APPROVED", design_id=version.design_id, version_id=version.id,
          actor=approved_by, actor_type="customer",
          metadata={"approval_hash": approval_hash, "method": approval_method,
                    "agreement_proof_sha256": proof_sha256})
    _emit(session, "VERSION_LOCKED", design_id=version.design_id, version_id=version.id,
          metadata={"approval_hash": approval_hash})
    return approval


# ------------------------------------------------------------------ export


# ---------------------------------------------------------------- secure link

APPROVAL_LINK_TTL_HOURS = 72
APPROVAL_METHOD_SECURE_LINK = "SECURE_LINK"


class LinkInvalid(ValueError):
    """Link unknown, expired, revoked, already used, or stale (design changed)."""

    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.code = code   # NOT_FOUND | EXPIRED | USED | REVOKED | STALE | VERSION_NOT_APPROVABLE


def create_approval_link(session: Session, version_id: uuid.UUID, created_by: str,
                         ttl_hours: int = APPROVAL_LINK_TTL_HOURS) -> tuple[str, m.ApprovalLink]:
    """Issue a single-use link for an approvable version. Returns the secret
    token (shown once) and the row. Any earlier open link for the version
    is revoked so exactly one link is live."""
    from ..security.sessions import hash_token, issue_token

    version = session.get(m.DesignVersion, version_id)
    if version is None:
        raise KeyError("version not found")
    if version.status != "UNAPPROVED":
        raise ConflictError(f"Version status {version.status} cannot be sent for approval.")
    if not (version.validation_passed and version.identity_verified):
        raise ApprovalRejected("Only a version that passes JEWELRY QA and text identity can be sent for approval.")
    now = _utcnow()
    for old in session.execute(
        select(m.ApprovalLink).where(m.ApprovalLink.design_version_id == version.id,
                                     m.ApprovalLink.used_at.is_(None), m.ApprovalLink.revoked_at.is_(None))
    ).scalars():
        old.revoked_at = now
    token, token_hash = issue_token()
    link = m.ApprovalLink(
        design_version_id=version.id, token_hash=token_hash,
        expires_at=now + timedelta(hours=max(1, min(int(ttl_hours), 24 * 14))),
        created_by=created_by, geometry_hash=version.geometry_hash,
    )
    session.add(link)
    session.flush()
    _emit(session, "APPROVAL_LINK_ISSUED", design_id=version.design_id, version_id=version.id,
          actor=created_by, actor_type="designer",
          metadata={"link_id": str(link.id), "expires_at": link.expires_at.isoformat()})
    return token, link


def resolve_approval_link(session: Session, token: str) -> tuple[m.ApprovalLink, m.DesignVersion]:
    """Validate a token → (link, version). Raises LinkInvalid with a code."""
    from ..security.sessions import hash_token

    link = session.execute(
        select(m.ApprovalLink).where(m.ApprovalLink.token_hash == hash_token(token or ""))
    ).scalar_one_or_none()
    if link is None:
        raise LinkInvalid("Unknown approval link.", "NOT_FOUND")
    if link.revoked_at is not None:
        raise LinkInvalid("This approval link was replaced by a newer one.", "REVOKED")
    if link.used_at is not None:
        raise LinkInvalid("This approval link has already been used.", "USED")
    if link.expires_at <= _utcnow():
        raise LinkInvalid("This approval link has expired.", "EXPIRED")
    version = session.get(m.DesignVersion, link.design_version_id)
    if version is None or version.geometry_hash != link.geometry_hash:
        raise LinkInvalid("The design changed after this link was issued.", "STALE")
    if version.status != "UNAPPROVED":
        raise LinkInvalid(f"Version status {version.status} cannot be approved.", "VERSION_NOT_APPROVABLE")
    return link, version


def approve_via_link(session: Session, token: str, confirmed_text: str, approver_name: str) -> m.CustomerApproval:
    """Customer approval through a secure link: same server-side checks as
    the internal path (exact text, hashes, QA), method SECURE_LINK, link
    consumed atomically with the lock."""
    link, version = resolve_approval_link(session, token)
    approval = approve_version(
        session, version.id,
        confirmed_text=confirmed_text,
        source_text_sha256=version.source_text_sha256,
        geometry_hash=version.geometry_hash,
        approved_by=approver_name.strip() or "customer",
        approval_method=APPROVAL_METHOD_SECURE_LINK,
    )
    link.used_at = _utcnow()
    link.approval_id = approval.id
    session.flush()
    return approval


def _version_to_candidate(version: m.DesignVersion) -> tuple[DesignCandidate, ImmutableSourceText]:
    """Adapter: reuse the existing exporters for persisted versions."""
    source = ImmutableSourceText.create(version.immutable_source_text, confirmed=True)
    candidate = DesignCandidate(
        candidate_id=str(version.id)[:16],
        design_id=str(version.design_id),
        source_text_sha256=version.source_text_sha256,
        recipe=RecipeParams(**version.recipe),
        shaped_runs=[],
        identity_proof=TextIdentityProof(
            verified=version.identity_verified,
            covered_codepoint_indices=[],
            uncovered_codepoint_indices=[],
            notdef_glyph_count=0,
        ),
        validation=ValidationReport(**version.validation),
        geometry_wkt=version.geometry_wkt,
        text_geometry_wkt=version.text_geometry_wkt or "",
        inner_text_geometry_wkt=version.inner_text_geometry_wkt or "",
    )
    return candidate, source


def agreement_proof_for_version(session: Session, version: m.DesignVersion) -> str:
    """Deterministic dimensioned approval artifact for one version. Same
    version → byte-identical SVG, so its sha256 identifies the exact picture
    the customer agreed to."""
    from ..exporters.agreement_proof import export_agreement_proof_svg

    candidate, source = _version_to_candidate(version)
    design = session.get(m.Design, version.design_id)
    req = session.get(m.DesignRequest, design.request_id) if design else None
    return export_agreement_proof_svg(
        candidate,
        source,
        version_number=version.version_number,
        geometry_hash=version.geometry_hash,
        product_type=req.product_type if req else "pendant",
    )


def export_version(
    session: Session,
    version_id: uuid.UUID,
    fmt: str,
    idempotency_key: str | None = None,
    actor: str = "system",
) -> tuple[str, m.ExportRecord]:
    """Authorized production export. Requires APPROVED_LOCKED + hash
    re-verification + stored validation PASS + rights PASS."""
    if fmt not in ("svg", "dxf", "pdf", "png"):
        # Only deterministic vector formats are exportable. AI rasters
        # (ai_generations) are display artifacts and can never become a
        # manufacturing file — see ADR-0002.
        raise ValueError("format must be svg, dxf or pdf (AI raster output is never exportable)")
    version = session.get(m.DesignVersion, version_id)
    if version is None:
        raise KeyError("version not found")

    # Idempotency: same key returns the original record without re-export.
    if idempotency_key:
        existing = session.execute(
            select(m.ExportRecord).where(m.ExportRecord.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.version_id != version.id or existing.format != fmt:
                raise ConflictError("Idempotency key already used for a different export.")
            return "", existing

    if version.status != "APPROVED_LOCKED":
        raise ProductionExportBlocked(
            "BLOCK_PRODUCTION_EXPORT: version is not customer-approved/locked."
        )
    approval = session.execute(
        select(m.CustomerApproval).where(m.CustomerApproval.design_version_id == version.id)
    ).scalar_one_or_none()
    if approval is None or approval.status != "ACTIVE":
        raise ProductionExportBlocked("BLOCK_PRODUCTION_EXPORT: no active approval bound to version.")
    if _version_geometry_hash(version) != version.geometry_hash or approval.geometry_hash != version.geometry_hash:
        raise ProductionExportBlocked("BLOCK_PRODUCTION_EXPORT: geometry hash verification failed.")
    if not (version.identity_verified and version.validation_passed):
        raise ProductionExportBlocked("BLOCK_PRODUCTION_EXPORT: QA state not PASS.")
    font = get_registry().get(version.font_id)
    if not font.commercial_production_allowed:
        raise ProductionExportBlocked("BLOCK_PRODUCTION_EXPORT: font rights.")

    candidate, source = _version_to_candidate(version)
    from shapely import wkt as shapely_wkt

    from ..exporters import fidelity as fid
    from ..exporters.pdf_exporter import export_pdf, manifest_for

    master = shapely_wkt.loads(version.geometry_wkt)
    if fmt == "svg":
        content: str | bytes = export_svg(candidate, source)
        reimported = fid.reimport_svg(content)
    elif fmt == "dxf":
        content = export_dxf(candidate, source)
        reimported = fid.reimport_dxf(content)
    elif fmt == "pdf":
        content = export_pdf(candidate, source, version_id=str(version.id), geometry_hash=version.geometry_hash)
        reimported = fid.reimport_pdf(content)
    else:
        # PNG is a preview raster of the same master at a declared scale —
        # shareable, printable at true size, never manufacturing truth.
        from ..exporters.png_exporter import compare_raster, export_png, reimport_png

        content = export_png(candidate, source, version_id=str(version.id), geometry_hash=version.geometry_hash)
        reimported = None
    raw = content.encode("utf-8") if isinstance(content, str) else content
    content_sha = hashlib.sha256(raw).hexdigest()
    loops = (version.recipe or {}).get("loops", "none")
    # Export Fidelity Gate: what was written must equal the master vector
    # (vectors: re-import and compare; raster: extent + ink area + hash chunk).
    if fmt == "png":
        fidelity = compare_raster(master, reimport_png(raw), geometry_hash=version.geometry_hash)
    else:
        fidelity = fid.compare(master, reimported)
    features = ValidationReport(**version.validation)  # noqa: F841 (validated above)
    bounds = master.bounds
    record = m.ExportRecord(
        version_id=version.id,
        kind="preview" if fmt == "png" else "production",
        format=fmt,
        content_sha256=content_sha,
        width_mm=round(bounds[2] - bounds[0], 3),
        height_mm=round(bounds[3] - bounds[1], 3),
        units="mm",
        validation_rules_version=version.manufacturing_rules_version,
        idempotency_key=idempotency_key,
        fidelity=fidelity,
        manifest=manifest_for(candidate, source, fmt, content_sha, str(version.id), version.geometry_hash),
    )
    session.add(record)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ConflictError("Duplicate idempotency key (race).") from exc
    _emit(session, "PRODUCTION_EXPORT_CREATED", design_id=version.design_id,
          version_id=version.id, actor=actor,
          metadata={"format": fmt, "content_sha256": record.content_sha256,
                    "fidelity": fidelity["status"]})
    return content, record


# ------------------------------------------------------------------- fonts


def sync_font_references(session: Session) -> int:
    """Record the exact font binaries (id + sha256) in the DB for provenance."""
    import json
    from ..fonts.registry import REGISTRY_FILE

    registry_version = json.loads(REGISTRY_FILE.read_text())["registry_version"]
    count = 0
    for font in get_registry().list():
        exists = session.execute(
            select(m.FontReference).where(
                m.FontReference.font_id == font.font_id,
                m.FontReference.file_sha256 == font.computed_sha256,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                m.FontReference(
                    font_id=font.font_id,
                    family=font.family,
                    license=font.license,
                    rights_status=font.rights_status.value,
                    file_sha256=font.computed_sha256,
                    registry_version=registry_version,
                )
            )
            count += 1
    return count
