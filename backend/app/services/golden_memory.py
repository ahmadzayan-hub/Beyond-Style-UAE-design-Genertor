"""Golden Production Memory — retrieval over real manufactured, delivered
and customer-approved orders.

Learning priority (CLAUDE.md "Memory / Learning"): a design that was
actually manufactured and approved by the customer outranks a
designer-approved concept, which outranks an unmanufactured AI concept,
which outranks external inspiration. That ordering is the multiplier
applied to similarity in `retrieve_golden_cases`.

Two invariants this module enforces:

1. NO GEOMETRY CLONING. `golden_case_generation_hints` emits DesignDNA
   style grammar and construction principles only. Lineage columns
   (`canonical_geometry_hash`, `design_version_id`) and any geometry
   payload are refused by an explicit assertion, so a proven case steers
   NEW original geometry built by the deterministic engines from the
   customer's own confirmed text.

2. NO INFERRED SOURCE TEXT. A case whose `source_text_status` is not
   CONFIRMED cannot hold the GOLDEN_PRODUCTION tier; it is stored as
   GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION and excluded from any
   text-bearing training export until an order record or an explicit
   confirmation supplies the text via `confirm_customer_source_text`.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.design_dna import DesignDNA
from ..ai.embeddings import ENCODER_VERSION, encode_dna, rank_by_similarity
from ..data.golden_production_cases import GOLDEN_PRODUCTION_CASES
from ..db import models as m
from .design_service import _emit

#: Evidence tier → ranking multiplier. Manufactured + customer-approved
#: memory is weighted above everything an engine merely generated.
EVIDENCE_TIER_WEIGHTS = {
    "MANUFACTURED_CUSTOMER_APPROVED": 1.0,
    "DESIGNER_APPROVED": 0.7,
    "AI_GENERATED_UNMANUFACTURED": 0.4,
    "EXTERNAL_INSPIRATION": 0.2,
}

GOLDEN_TIER = "GOLDEN_PRODUCTION"
PENDING_TIER = "GOLDEN_PRODUCTION_PENDING_TEXT_VERIFICATION"

#: Never emitted as a generation hint — retrieval transfers style and
#: engineering principles, never the original outline.
GEOMETRY_KEYS = {
    "canonical_geometry_hash",
    "design_version_id",
    "geometry_wkt",
    "text_geometry_wkt",
    "geometry_hash",
    "recipe",
}


def effective_memory_tier(case: dict | m.GoldenProductionCase) -> str:
    """GOLDEN_PRODUCTION requires all three: manufactured successfully,
    approved by the customer, AND an authoritative source text. Anything
    less is held at the pending tier — it still contributes style memory,
    but it is not production training truth."""
    get = case.get if isinstance(case, dict) else lambda k, d=None: getattr(case, k, d)
    if not (get("production_success") and get("customer_approved")):
        return PENDING_TIER
    if get("source_text_status") != "CONFIRMED":
        return PENDING_TIER
    return GOLDEN_TIER


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_golden_cases(session: Session) -> list[str]:
    """Idempotently load the curated real cases. Returns the case_ids
    that were newly inserted (empty on a repeat run)."""
    existing = {
        row[0]
        for row in session.execute(select(m.GoldenProductionCase.case_id))
    }
    inserted: list[str] = []
    for spec in GOLDEN_PRODUCTION_CASES:
        if spec["case_id"] in existing:
            continue
        dna: DesignDNA = spec["dna"]
        text = spec.get("customer_source_text")
        row = m.GoldenProductionCase(
            case_id=spec["case_id"],
            customer_source_text=text,
            source_text_status=spec["source_text_status"],
            source_text_authority=spec["source_text_authority"],
            source_text_sha256=_sha256(text) if text else None,
            primary_names=spec.get("primary_names"),
            language=spec["language"],
            product_type=spec["product_type"],
            layout_style=spec.get("layout_style"),
            composition_type=spec.get("composition_type"),
            construction=spec["construction"],
            construction_topology=spec.get("construction_topology"),
            attachment_topology=spec.get("attachment_topology"),
            attachment_points=spec.get("attachment_points"),
            chain_topology=spec.get("chain_topology"),
            design_version_id=spec.get("design_version_id"),
            canonical_geometry_hash=spec.get("canonical_geometry_hash"),
            lineage_status=spec["lineage_status"],
            material=spec.get("material"),
            finish=spec.get("finish"),
            dimensions=spec.get("dimensions"),
            stone_or_pearl_details=spec.get("stone_or_pearl_details"),
            workshop_changes=spec.get("workshop_changes"),
            design_process=spec.get("design_process"),
            variant_selection=spec.get("variant_selection"),
            manufacturing_result=spec["manufacturing_result"],
            production_success=spec["production_success"],
            customer_feedback=spec.get("customer_feedback"),
            customer_sentiment=spec["customer_sentiment"],
            customer_approved=spec["customer_approved"],
            memory_tier=effective_memory_tier(spec),
            evidence_tier=spec["evidence_tier"],
            ranking_weight=spec["ranking_weight"],
            design_fidelity_score=aggregate_fidelity(spec["stage_comparison"]),
            stage_comparison=compare_case_stages(spec["stage_comparison"]),
            lessons_learned=spec.get("lessons_learned"),
            design_dna=dna.model_dump(),
            dna_embedding=encode_dna(dna),
            encoder_version=ENCODER_VERSION,
            retrieval_keywords=[k.lower() for k in spec["retrieval_keywords"]],
            rights_provenance=spec["rights_provenance"],
            privacy_status=spec["privacy_status"],
            evidence=spec["evidence"],
        )
        session.add(row)
        session.flush()
        _emit(
            session,
            "GOLDEN_CASE_REGISTERED",
            actor="golden_memory_seed",
            actor_type="system",
            metadata={
                "case_id": row.case_id,
                "memory_tier": row.memory_tier,
                "evidence_tier": row.evidence_tier,
                "source_text_status": row.source_text_status,
                "excluded_personal_evidence": sum(
                    1 for e in row.evidence if e["storage_status"] == "EXCLUDED_PERSONAL_DATA"
                ),
            },
        )
        inserted.append(row.case_id)
    return inserted


# ---------------------------------------------------------------------------
# Stage comparison (concept → proof/outline → manufactured product)
# ---------------------------------------------------------------------------

def compare_case_stages(stage_comparison: dict) -> dict:
    """Normalize a case's per-dimension stage comparison and attach the
    aggregate. Scores are recorded human visual assessments — this is NOT
    a computed geometry metric, and the `measurement_method` on every
    result says so. Dimensions that cannot be assessed stay None with a
    status, never a filled-in number."""
    dims = stage_comparison.get("dimensions", {})
    assessed = {k: v for k, v in dims.items() if isinstance(v.get("score"), (int, float))}
    not_assessed = [k for k, v in dims.items() if not isinstance(v.get("score"), (int, float))]
    return {
        "stages": stage_comparison.get("stages", []),
        "measurement_method": stage_comparison.get(
            "measurement_method", "VISUAL_REVIEW_NO_VECTOR_GEOMETRY"
        ),
        "computed_from_vector_geometry": False,
        "dimensions": dims,
        "assessed_count": len(assessed),
        "not_assessed": not_assessed,
        "aggregate_score": aggregate_fidelity(stage_comparison),
    }


def aggregate_fidelity(stage_comparison: dict) -> float | None:
    """Mean of the assessed dimensions, or None when nothing is assessed."""
    scores = [
        v["score"]
        for v in stage_comparison.get("dimensions", {}).values()
        if isinstance(v.get("score"), (int, float))
    ]
    return round(sum(scores) / len(scores), 3) if scores else None


# ---------------------------------------------------------------------------
# Text-truth promotion
# ---------------------------------------------------------------------------

def confirm_customer_source_text(
    session: Session,
    case_id: str,
    source_text: str,
    authority: str,
    actor: str = "staff",
) -> m.GoldenProductionCase:
    """Supply the authoritative customer text for a pending case and
    promote it. `authority` must name a real source (an order record or
    an explicit customer confirmation) — vision/OCR is never one."""
    if authority in ("OCR", "VISION", "INFERRED", ""):
        raise ValueError("Source text authority must be an order record or explicit confirmation, not OCR/vision.")
    if not source_text.strip():
        raise ValueError("Source text cannot be empty.")
    case = session.execute(
        select(m.GoldenProductionCase).where(m.GoldenProductionCase.case_id == case_id)
    ).scalar_one_or_none()
    if case is None:
        raise KeyError(f"Unknown golden case: {case_id}")
    case.customer_source_text = source_text
    case.source_text_sha256 = _sha256(source_text)
    case.source_text_status = "CONFIRMED"
    case.source_text_authority = authority
    case.memory_tier = effective_memory_tier(case)
    session.flush()
    _emit(
        session,
        "GOLDEN_CASE_TEXT_CONFIRMED",
        actor=actor,
        actor_type="human",
        metadata={
            "case_id": case.case_id,
            "authority": authority,
            "source_text_sha256": case.source_text_sha256,
            "memory_tier": case.memory_tier,
        },
    )
    return case


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _query_dna(query: dict) -> DesignDNA:
    """Build a DesignDNA probe from a customer request's structured
    attributes. Never contains the customer's text — only style axes."""
    return DesignDNA(
        source="query_probe",
        analyzer_model="none",
        product_type=query.get("product_type", "unknown"),
        script_family=query.get("script_family", "unknown"),
        composition=query.get("composition", "unknown"),
        construction=query.get("construction", "unknown"),
        luxury_score=query.get("luxury_score", 0.5),
        minimal_score=query.get("minimal_score", 0.5),
        heritage_score=query.get("heritage_score", 0.5),
        modern_score=query.get("modern_score", 0.5),
        manufacturing_complexity=query.get("manufacturing_complexity", "unknown"),
    )


def retrieve_golden_cases(session: Session, query: dict, top_k: int = 5) -> list[dict]:
    """Rank real production cases for a new customer request.

    `query` carries style axes (product_type/script_family/composition)
    and optional free-text `keywords`. Score = DNA cosine similarity ×
    evidence-tier weight, plus a bounded keyword-match bonus. Returns
    descriptors — never geometry."""
    rows = session.execute(select(m.GoldenProductionCase)).scalars().all()
    if not rows:
        return []
    probe = encode_dna(_query_dna(query))
    similarity = dict(
        rank_by_similarity(probe, [(str(r.id), r.dna_embedding) for r in rows], top_k=len(rows))
    )
    terms = [t.lower() for t in query.get("keywords", []) if t.strip()]

    scored = []
    for row in rows:
        sim = similarity.get(str(row.id), 0.0)
        tier = EVIDENCE_TIER_WEIGHTS.get(row.evidence_tier, 0.2)
        hits = [
            kw for kw in row.retrieval_keywords
            if any(t in kw or kw in t for t in terms)
        ]
        keyword_bonus = min(0.3, 0.1 * len(hits))
        scored.append(
            {
                "case_id": row.case_id,
                "product_type": row.product_type,
                "language": row.language,
                "memory_tier": row.memory_tier,
                "evidence_tier": row.evidence_tier,
                "ranking_weight": row.ranking_weight,
                "similarity": round(sim, 4),
                "evidence_tier_weight": tier,
                "keyword_matches": hits,
                "score": round(sim * tier + keyword_bonus, 4),
                "design_fidelity_score": row.design_fidelity_score,
                "lessons_learned": row.lessons_learned or [],
            }
        )
    scored.sort(key=lambda c: (-c["score"], c["case_id"]))
    return scored[:top_k]


def golden_case_generation_hints(
    case: m.GoldenProductionCase, style_strength: float = 0.5
) -> dict:
    """Turn a proven case into deterministic generator hints.

    Style grammar + construction topology + workshop-proven engineering
    principles only. The returned payload is asserted to be free of every
    geometry/lineage key, so the generator produces NEW geometry from the
    customer's own confirmed text rather than reproducing this piece."""
    from .reference_intelligence import dna_generation_hints

    hints = dna_generation_hints(case.design_dna, style_strength=style_strength)
    hints.update(
        {
            "source": "golden_production_case",
            "case_id": case.case_id,
            "evidence_tier": case.evidence_tier,
            "memory_tier": case.memory_tier,
            "construction_principles": list(case.construction),
            "construction_topology": case.construction_topology,
            "attachment_topology": case.attachment_topology,
            "chain_topology": case.chain_topology,
            "proven_lessons": list(case.lessons_learned or []),
            "proven_process": list(case.design_process or []),
            "copies_original_geometry": False,
            "requires_customer_confirmed_text": True,
        }
    )
    leaked = GEOMETRY_KEYS & set(hints)
    assert not leaked, f"golden case hints must never carry geometry: {leaked}"
    return hints


def golden_training_export(session: Session) -> list[dict]:
    """Rights- and text-gated export of golden cases for future training.

    Excluded: any case not at the GOLDEN_PRODUCTION tier (i.e. whose
    source text is unverified), any case without reusable rights, and
    every evidence item marked EXCLUDED_PERSONAL_DATA."""
    allowed_provenance = {"BEYOND_STYLE_OWNED", "CUSTOMER_OWNED", "LICENSED"}
    out = []
    for row in session.execute(select(m.GoldenProductionCase)).scalars().all():
        if row.memory_tier != GOLDEN_TIER:
            continue
        if row.rights_provenance not in allowed_provenance:
            continue
        out.append(
            {
                "case_id": row.case_id,
                "product_type": row.product_type,
                "language": row.language,
                "source_text_sha256": row.source_text_sha256,
                "design_dna": row.design_dna,
                "construction": row.construction,
                "lessons_learned": row.lessons_learned or [],
                "design_process": row.design_process or [],
                "evidence_tier": row.evidence_tier,
                "tier_weight": EVIDENCE_TIER_WEIGHTS[row.evidence_tier],
                "evidence": [
                    e for e in row.evidence
                    if e["storage_status"] != "EXCLUDED_PERSONAL_DATA"
                ],
            }
        )
    return out
