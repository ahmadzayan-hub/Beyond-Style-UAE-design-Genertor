"""Final intelligence/quality layer: Design Jury, confidence engine,
taste memory hooks, lineage assembly, shadow-model routing.

All of this is retrieval/scoring on top of existing deterministic data —
none of it can override the source-of-truth hierarchy in `agents.py`.
Design Jury uses ONE structured Claude call (not 4 agent round-trips) per
the cost-aware routing principle.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from .llm import LLMUnavailable, get_provider

# ------------------------------------------------------------ Design Jury


class JuryScore(BaseModel):
    score: float = Field(ge=0, le=1)
    explanation: str


class DesignJuryVerdict(BaseModel):
    """One structured Claude call standing in for 4 critic roles —
    Arabic Art Critic, Jewellery Aesthetic Critic, Manufacturing Critic,
    Customer-Fit Critic — normalized 0..1 with explanations."""

    arabic_art: JuryScore
    jewellery_aesthetic: JuryScore
    manufacturing: JuryScore
    customer_fit: JuryScore

    @property
    def overall(self) -> float:
        return round(
            0.3 * self.arabic_art.score
            + 0.3 * self.jewellery_aesthetic.score
            + 0.25 * self.manufacturing.score
            + 0.15 * self.customer_fit.score,
            4,
        )


JURY_SYSTEM = (
    "You are a structured jewellery design jury. Score the described candidate "
    "0.0-1.0 on four roles: arabic_art (calligraphic quality/authenticity), "
    "jewellery_aesthetic (visual balance, luxury feel), manufacturing "
    "(constructability given the reported validation), customer_fit (matches "
    "stated intent/product). Give a one-sentence explanation per role. This is "
    "advisory only — deterministic Arabic identity and manufacturing validation "
    "are the actual gates, not your score."
)


def run_design_jury(candidate_summary: dict, tier: str = "primary") -> tuple[DesignJuryVerdict, dict]:
    """Raises LLMUnavailable when no Claude credential exists — callers
    must report SKIPPED_EXTERNAL_MODEL, never fabricate a verdict."""
    provider = get_provider(tier)
    return provider.structured(
        system=JURY_SYSTEM,
        user_content=str(candidate_summary),
        schema=DesignJuryVerdict,
        effort="low",
    )


# --------------------------------------------------------- confidence engine


class ConfidenceReport(BaseModel):
    arabic_confidence: float
    design_confidence: float
    reference_match_confidence: float
    manufacturing_confidence: float
    preview_fidelity_confidence: Optional[float] = None
    ip_confidence: float
    requires_human_review: bool
    reasons: list[str] = Field(default_factory=list)


#: Below this, the dimension forces HUMAN_REVIEW.
CONFIDENCE_THRESHOLD = 0.7


def compute_confidence(
    identity_verified: bool,
    validation_passed: bool,
    reference_similarity: float | None = None,
    preview_guard: dict | None = None,
    ip_risk_status: str = "OK",
) -> ConfidenceReport:
    """Deterministic confidence scoring from already-computed signals —
    no model call needed for this part."""
    reasons: list[str] = []
    arabic = 1.0 if identity_verified else 0.0
    if not identity_verified:
        reasons.append("Arabic identity not verified")
    manufacturing = 1.0 if validation_passed else 0.0
    if not validation_passed:
        reasons.append("Manufacturing validation failed")
    design = 0.85 if (identity_verified and validation_passed) else 0.3
    ref_match = reference_similarity if reference_similarity is not None else 1.0
    preview_fidelity = None
    if preview_guard is not None:
        preview_fidelity = round(max(0.0, 1.0 - preview_guard.get("divergence", 1.0)), 4)
        if preview_fidelity < CONFIDENCE_THRESHOLD:
            reasons.append("Preview fidelity below threshold")
    ip_conf = {"OK": 1.0, "INSPIRED_ALTERNATIVE_REQUIRED": 0.4}.get(ip_risk_status, 0.5)
    if ip_conf < CONFIDENCE_THRESHOLD:
        reasons.append(f"IP risk status: {ip_risk_status}")

    dims = [arabic, design, ref_match, manufacturing, ip_conf]
    if preview_fidelity is not None:
        dims.append(preview_fidelity)
    requires_review = any(d < CONFIDENCE_THRESHOLD for d in dims)
    return ConfidenceReport(
        arabic_confidence=arabic,
        design_confidence=design,
        reference_match_confidence=round(ref_match, 4),
        manufacturing_confidence=manufacturing,
        preview_fidelity_confidence=preview_fidelity,
        ip_confidence=ip_conf,
        requires_human_review=requires_review,
        reasons=reasons,
    )


# ------------------------------------------------------------- taste memory


def record_taste_signal(
    session: Session, event_type: str, request_id: uuid.UUID, dna: dict | None, metadata: dict | None = None
) -> None:
    """Opt-in preference signal. Never restricts customer choice or
    touches confirmed source text — purely a future-ranking input."""
    from .design_dna import DesignDNA  # noqa: F401  (documents the expected shape)
    from ..services.design_service import _emit

    meta = dict(metadata or {})
    if dna:
        meta["script_family"] = dna.get("script_family")
        meta["composition"] = dna.get("composition")
        meta["luxury_score"] = dna.get("luxury_score")
    _emit(session, "CUSTOMER_FEEDBACK", request_id=request_id, actor="customer",
          metadata={"taste_signal": event_type, **meta})


def taste_profile(session: Session, request_ids: list[uuid.UUID]) -> dict:
    """Aggregate opt-in taste signals across a customer's own requests only."""
    if not request_ids:
        return {"script_family_counts": {}, "avg_luxury_score": None, "sample_size": 0}
    rows = session.execute(
        select(m.DesignEvent).where(
            m.DesignEvent.event_type == "CUSTOMER_FEEDBACK",
            m.DesignEvent.request_id.in_(request_ids),
        )
    ).scalars().all()
    scripts: dict[str, int] = {}
    luxury = []
    for r in rows:
        meta = r.event_metadata or {}
        sf = meta.get("script_family")
        if sf:
            scripts[sf] = scripts.get(sf, 0) + 1
        if meta.get("luxury_score") is not None:
            luxury.append(meta["luxury_score"])
    return {
        "script_family_counts": scripts,
        "avg_luxury_score": round(sum(luxury) / len(luxury), 3) if luxury else None,
        "sample_size": len(rows),
    }


# ------------------------------------------------------------ design lineage


def design_lineage(session: Session, design_id: uuid.UUID) -> dict:
    """Complete traceable chain: Request → Reference(s) → DNA → Candidates →
    Versions (incl. edits/repairs) → Approval → AI previews → Exports.
    Every node carries its own id — no orphan assets."""
    design = session.get(m.Design, design_id)
    if design is None:
        raise KeyError("design not found")
    request = session.get(m.DesignRequest, design.request_id)
    references = session.execute(
        select(m.ReferenceAsset).where(m.ReferenceAsset.design_request_id == request.id)
    ).scalars().all()
    dna_rows = session.execute(
        select(m.ReferenceDNARow).where(m.ReferenceDNARow.design_request_id == request.id)
    ).scalars().all()
    versions = session.execute(
        select(m.DesignVersion)
        .where(m.DesignVersion.design_id == design.id)
        .order_by(m.DesignVersion.version_number)
    ).scalars().all()
    approvals = session.execute(
        select(m.CustomerApproval).where(
            m.CustomerApproval.design_version_id.in_([v.id for v in versions] or [uuid.uuid4()])
        )
    ).scalars().all()
    generations = session.execute(
        select(m.AIGeneration).where(m.AIGeneration.design_request_id == request.id)
    ).scalars().all()
    exports = session.execute(
        select(m.ExportRecord).where(
            m.ExportRecord.version_id.in_([v.id for v in versions] or [uuid.uuid4()])
        )
    ).scalars().all()
    return {
        "request_id": str(request.id),
        "source_text": request.source_text_normalized,
        "source_text_sha256": request.source_text_sha256,
        "references": [{"id": str(r.id), "provenance": r.provenance, "sha256": r.sha256} for r in references],
        "reference_dna": [{"id": str(d.id), "source": d.source} for d in dna_rows],
        "design_id": str(design.id),
        "versions": [
            {
                "id": str(v.id), "version_number": v.version_number,
                "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                "status": v.status, "created_by": v.created_by,
                "geometry_hash": v.geometry_hash,
            }
            for v in versions
        ],
        "approvals": [
            {"id": str(a.id), "version_id": str(a.design_version_id),
             "status": a.status, "approval_hash": a.approval_hash}
            for a in approvals
        ],
        "ai_previews": [
            {"id": str(g.id), "version_id": str(g.design_version_id),
             "guard_status": g.guard_status, "kind": g.kind}
            for g in generations
        ],
        "exports": [
            {"id": str(e.id), "version_id": str(e.version_id), "format": e.format,
             "content_sha256": e.content_sha256}
            for e in exports
        ],
    }


# --------------------------------------------------------- shadow evaluation


class ShadowResult(BaseModel):
    production_model: str
    candidate_model: str
    production_verdict: DesignJuryVerdict
    candidate_verdict: DesignJuryVerdict
    quality_delta: float  # candidate.overall - production.overall
    recommend_promotion: bool


def run_shadow_evaluation(
    candidate_summary: dict, production_tier: str = "primary", candidate_model: str | None = None
) -> ShadowResult:
    """Run the SAME job against the production model and a shadow
    candidate model. Never serves the shadow result to users; only
    compares. Promotion is a human decision — this only recommends."""
    prod_provider = get_provider(production_tier)
    prod_verdict, _ = prod_provider.structured(
        JURY_SYSTEM, str(candidate_summary), DesignJuryVerdict, effort="low"
    )
    from .llm import ClaudeProvider

    shadow_provider = ClaudeProvider(production_tier)
    if candidate_model:
        shadow_provider.model = candidate_model  # e.g. a newer Claude snapshot
    cand_verdict, _ = shadow_provider.structured(
        JURY_SYSTEM, str(candidate_summary), DesignJuryVerdict, effort="low"
    )
    delta = round(cand_verdict.overall - prod_verdict.overall, 4)
    return ShadowResult(
        production_model=prod_provider.model,
        candidate_model=shadow_provider.model,
        production_verdict=prod_verdict,
        candidate_verdict=cand_verdict,
        quality_delta=delta,
        recommend_promotion=delta > 0.05,  # never auto-promotes; advisory only
    )
