"""Admin API — Golden Production Cases.

Closed by default: ADMIN_API_TOKEN is unset unless a deployment
explicitly configures it, and every route 403s until it is. Customer
conversation evidence is never served here — it is not stored.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..db.base import get_session
from ..services.golden_memory import EVIDENCE_TIER_WEIGHTS, retrieve_golden_cases

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")


def require_admin(request: Request) -> None:
    if not ADMIN_API_TOKEN or request.headers.get("X-Admin-Token") != ADMIN_API_TOKEN:
        raise HTTPException(403, "Admin endpoints require a valid X-Admin-Token.")


def _summary(row: m.GoldenProductionCase) -> dict:
    return {
        "case_id": row.case_id,
        "product_type": row.product_type,
        "language": row.language,
        "layout_style": row.layout_style,
        "memory_tier": row.memory_tier,
        "evidence_tier": row.evidence_tier,
        "ranking_weight": row.ranking_weight,
        "tier_weight": EVIDENCE_TIER_WEIGHTS.get(row.evidence_tier, 0.2),
        "production_result": row.manufacturing_result,
        "customer_sentiment": row.customer_sentiment,
        "customer_approved": row.customer_approved,
        "design_fidelity_score": row.design_fidelity_score,
        "source_text_status": row.source_text_status,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/golden-cases", dependencies=[Depends(require_admin)])
def list_golden_cases(session: Session = Depends(get_session)):
    rows = session.execute(
        select(m.GoldenProductionCase).order_by(m.GoldenProductionCase.case_id)
    ).scalars().all()
    return {"cases": [_summary(r) for r in rows]}


@router.get("/golden-cases/{case_id}", dependencies=[Depends(require_admin)])
def get_golden_case(case_id: str, session: Session = Depends(get_session)):
    """Full case view, grouped into the sections the admin screen renders:
    Concept · Reference Style · Layout Proof / Workshop Drawing · Final
    Product · Customer Feedback · Production Result · DesignDNA ·
    Lessons Learned."""
    row = session.execute(
        select(m.GoldenProductionCase).where(m.GoldenProductionCase.case_id == case_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Golden production case not found.")

    by_role: dict[str, list[dict]] = {}
    for item in row.evidence:
        by_role.setdefault(item["role"], []).append(item)

    return {
        **_summary(row),
        "sections": {
            "customer_selection": by_role.get("customer_selection", [])
            + by_role.get("shop_annotation", []),
            "concept": by_role.get("concept_sketch", []) + by_role.get("concept_selection", []),
            "reference_style": by_role.get("style_reference", []) + by_role.get("reference_image", []),
            "writing_variants": {
                "proposals": by_role.get("writing_variant_proposal", []),
                "selection": row.variant_selection,
            },
            "layout_proof": by_role.get("layout_proof", []) + by_role.get("workshop_outline", []),
            "final_product": by_role.get("final_product", []) + by_role.get("final_product_video", []),
            "customer_feedback": {
                "normalized_feedback": row.customer_feedback,
                "sentiment": row.customer_sentiment,
                "approved": row.customer_approved,
                "original_conversation_stored": False,
                "privacy_note": (
                    "WhatsApp conversation evidence is registered by content hash only. "
                    "Name, avatar, phone number and timestamps are not persisted; retaining "
                    "the original screenshot would require explicit customer consent."
                ),
            },
            "production_result": {
                "manufacturing_result": row.manufacturing_result,
                "production_success": row.production_success,
                "material": row.material,
                "finish": row.finish,
                "dimensions": row.dimensions,
                "stone_or_pearl_details": row.stone_or_pearl_details,
                "construction": row.construction,
                "construction_topology": row.construction_topology,
                "attachment_topology": row.attachment_topology,
                "attachment_points": row.attachment_points,
                "chain_topology": row.chain_topology,
                "workshop_changes": row.workshop_changes,
                "lineage_status": row.lineage_status,
            },
            "design_dna": row.design_dna,
            "design_process": row.design_process or [],
            "lessons_learned": row.lessons_learned or [],
            "stage_comparison": row.stage_comparison,
        },
        "text_truth": {
            "customer_source_text": row.customer_source_text,
            "primary_names": row.primary_names,
            "status": row.source_text_status,
            "authority": row.source_text_authority,
            "sha256": row.source_text_sha256,
        },
        "rights_provenance": row.rights_provenance,
        "privacy_status": row.privacy_status,
        "evidence": row.evidence,
    }


@router.post("/golden-cases/retrieve", dependencies=[Depends(require_admin)])
def retrieve(query: dict, session: Session = Depends(get_session)):
    """Rank golden cases for a prospective request — the same retrieval
    the generator uses. Returns descriptors, never geometry."""
    return {"results": retrieve_golden_cases(session, query, top_k=int(query.get("top_k", 5)))}
