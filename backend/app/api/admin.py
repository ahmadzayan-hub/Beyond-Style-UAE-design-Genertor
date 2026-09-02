"""Admin API — Golden Production Cases.

Closed by default: ADMIN_API_TOKEN is unset unless a deployment
explicitly configures it, and every route 403s until it is. Customer
conversation evidence is never served here — it is not stored.
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from ..db import models as m
from ..db.base import get_session
from ..services.golden_memory import EVIDENCE_TIER_WEIGHTS, retrieve_golden_cases

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
#: Reviewer role: may read review packs and submit/inspect review decisions
#: only — never golden cases, curation, or customer-validation data.
REVIEWER_API_TOKEN = os.environ.get("REVIEWER_API_TOKEN", "")

REVIEWER_ALLOWED_PREFIXES = ("/api/admin/review/",)


def _role_for(token: str | None) -> str | None:
    if not token:
        return None
    if ADMIN_API_TOKEN and secrets.compare_digest(token, ADMIN_API_TOKEN):
        return "admin"
    if REVIEWER_API_TOKEN and secrets.compare_digest(token, REVIEWER_API_TOKEN):
        return "reviewer"
    return None


def require_admin(request: Request) -> None:
    """Role-scoped staff access. Admin: everything. Reviewer: review routes
    only (blinded pack, decision, history, agreement, wave). Closed by
    default — with no tokens configured every route 403s."""
    role = _role_for(request.headers.get("X-Admin-Token"))
    if role == "admin":
        return
    if role == "reviewer" and request.url.path.startswith(REVIEWER_ALLOWED_PREFIXES):
        return
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


class ConfirmTextRequest(BaseModel):
    """Owner enters the exact customer-confirmed text from the ORDER RECORD.
    Vision/OCR can never be the authority (enforced in the service)."""
    text: str
    authority: str = "ORDER_RECORD"
    order_reference: str | None = None
    actor: str = "workshop_admin"


@router.post("/golden-cases/{case_id}/confirm-text", dependencies=[Depends(require_admin)])
def confirm_golden_case_text(case_id: str, body: ConfirmTextRequest, session: Session = Depends(get_session)):
    """Promotes a PENDING_CUSTOMER_VERIFICATION golden case to production
    training memory once the exact text is supplied from an order record."""
    from ..services.golden_memory import confirm_customer_source_text

    try:
        case = confirm_customer_source_text(
            session, case_id, body.text, authority=body.authority, actor=body.actor
        )
    except KeyError:
        raise HTTPException(404, "Golden case not found.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {
        "case_id": case.case_id,
        "source_text_status": case.source_text_status,
        "source_text_authority": case.source_text_authority,
        "memory_tier": case.memory_tier,
        "source_text_sha256": case.source_text_sha256,
        "order_reference": body.order_reference,
    }


@router.post("/golden-cases/retrieve", dependencies=[Depends(require_admin)])
def retrieve(query: dict, session: Session = Depends(get_session)):
    """Rank golden cases for a prospective request — the same retrieval
    the generator uses. Returns descriptors, never geometry."""
    return {"results": retrieve_golden_cases(session, query, top_k=int(query.get("top_k", 5)))}


@router.get("/styles/{label_ar}", dependencies=[Depends(require_admin)])
def resolve_style(label_ar: str):
    """Internal resolution of a customer style label into the curated
    font + feature-set + axis-range bundle. Staff-only precisely because
    it exposes the raw OpenType layer the customer never sees."""
    from ..fonts.curation import resolve_style_label

    result = resolve_style_label(label_ar)
    if result["outcome"] == "UNKNOWN_STYLE":
        raise HTTPException(404, "Unknown style label.")
    return result


@router.get("/curation", dependencies=[Depends(require_admin)])
def curation_report():
    """Curation states across every variant set, with the count awaiting
    human aesthetic review."""
    from collections import Counter

    from ..fonts.curation import load_curation

    data = load_curation()
    states = Counter(v["state"] for v in data.get("features", {}).values())
    return {
        "states": dict(states),
        "awaiting_human_review": states.get("EXPERIMENTAL", 0),
        "features": data.get("features", {}),
        "axis_ranges": data.get("axis_ranges", {}),
        "safe_combinations": data.get("safe_combinations", []),
    }


# ---------------------------------------------------------------------------
# Human Aesthetic Review (internal Art Director screen)
# ---------------------------------------------------------------------------

class ReviewSubmission(BaseModel):
    item_id: str
    recipe_hash: str
    product: str
    font_id: str
    source_text: str
    reviewer: str
    decision: str
    mode: str = "quick"
    feature_set: str = "default"
    font_axes: dict = Field(default_factory=dict)
    scores: dict | None = None
    note: str | None = None
    engineering: dict = Field(default_factory=dict)


#: Fields that would tell a new reviewer what others already decided.
_PRIOR_OPINION_FIELDS = ("human_decision", "reviewer", "reviewed_at", "review_mode",
                         "weak_critical_dimensions")


def _blind(curation: dict, reviewer: str) -> dict:
    """Hide prior opinions from a reviewer who has not yet submitted.

    Engineering state stays visible — that is fact, not opinion. What is
    withheld is what other people concluded, so a second reviewer forms an
    independent judgement rather than anchoring on the first."""
    if not reviewer:
        return {k: v for k, v in curation.items() if k not in _PRIOR_OPINION_FIELDS}
    return curation


@router.get("/review/pack", dependencies=[Depends(require_admin)])
def review_pack(session: Session = Depends(get_session), max_per_product: int = 3,
                reviewer: str = ""):
    """The prioritised review pack, each item carrying its rendered proof.

    Human decisions are read from the append-only review log; an item that
    nobody has reviewed reports HUMAN_REVIEW_PENDING rather than any
    provisional verdict."""
    from ..services.review_items import generate_review_pack
    from ..services.review_workflow import (
        DIMENSION_LABELS, HUMAN_DIMENSIONS, ai_advisory_status,
        curation_decisions, summarize,
    )

    items = generate_review_pack(max_per_product=max_per_product)
    decisions = curation_decisions(session, items)
    by_item = {d["item_id"]: d for d in decisions}
    recorded = session.execute(select(m.DesignReview)).scalars().all()
    return {
        "items": [
            {**item, "curation": _blind(by_item[item["item_id"]], reviewer)}
            for item in items
        ],
        "dimensions": HUMAN_DIMENSIONS,
        "dimension_labels": DIMENSION_LABELS,
        "blinded": True,
        "blinding_note": (
            "Prior reviewers' decisions and scores are withheld so each review "
            "is independent. They become visible per item after you submit."
        ),
        "summary": summarize(decisions, len(recorded)),
        "ai_advisory": ai_advisory_status(),
    }


@router.post("/review/decision", dependencies=[Depends(require_admin)])
def submit_review(body: ReviewSubmission, session: Session = Depends(get_session)):
    """Record one human decision. Append-only: a revised opinion is a new
    record, and the previous one stays readable."""
    from ..services.review_workflow import (
        ReviewRejected, curation_for_item, record_review,
    )

    item = body.model_dump()
    try:
        review = record_review(
            session, item=item, reviewer=body.reviewer, decision=body.decision,
            mode=body.mode, scores=body.scores, note=body.note,
        )
    except ReviewRejected as exc:
        raise HTTPException(422, str(exc))
    session.commit()
    return {
        "recorded": True,
        "review_id": str(review.id),
        "curation": curation_for_item(item, review),
    }


@router.get("/review/history/{item_id}", dependencies=[Depends(require_admin)])
def review_item_history(item_id: str, session: Session = Depends(get_session)):
    from ..services.review_workflow import review_history

    rows = review_history(session, item_id)
    return {
        "item_id": item_id,
        "review_count": len(rows),
        "history": [
            {"review_id": str(r.id), "reviewer": r.reviewer, "decision": r.decision,
             "mode": r.review_mode, "scores": r.scores, "note": r.note,
             "recipe_hash": r.recipe_hash, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# P2 — curation analysis and customer validation
# ---------------------------------------------------------------------------

class CustomerResponseSubmission(BaseModel):
    item_id: str
    pack_id: str
    respondent_token: str
    would_buy: str
    premium_feel: int
    readability: int
    uniqueness: int
    preferred_product: str | None = None
    price_band: str | None = None
    comment: str | None = None


@router.get("/curation/analysis", dependencies=[Depends(require_admin)])
def curation_analysis_report(session: Session = Depends(get_session)):
    """Aesthetic and commercial curation derived from human review evidence.

    Every family claim is INSUFFICIENT_HUMAN_REVIEW_EVIDENCE until enough
    genuine reviews exist; no engineering or AI value substitutes for one."""
    from ..services.curation_analysis import (
        best_aesthetic_family_for_product, best_commercial_family_for_product,
        commercial_curation, derive_aesthetic_signals, golden_pattern_validation,
        load_review_evidence, overall_best_aesthetic_family,
        product_comparison_readiness, review_quality_check, threshold_audit,
    )
    from ..services.customer_validation import best_customer_family
    from ..services.review_items import generate_review_pack

    items = generate_review_pack(max_per_product=3)
    return {
        "evidence": load_review_evidence(session, items),
        "quality_check": review_quality_check(session, items),
        "aesthetic_signals": derive_aesthetic_signals(session, items),
        "commercial_curation": commercial_curation(session, items),
        "threshold_audit": threshold_audit(items),
        "comparison_readiness": product_comparison_readiness(session, items),
        "best_aesthetic_family": best_aesthetic_family_for_product(session, items),
        "best_commercial_family": best_commercial_family_for_product(session, items),
        "overall_best_aesthetic_family": overall_best_aesthetic_family(session, items),
        "best_customer_family": best_customer_family(session, items),
        "golden_pattern_validation": golden_pattern_validation(session, items),
    }


@router.get("/customer-validation/pack", dependencies=[Depends(require_admin)])
def customer_pack(session: Session = Depends(get_session)):
    """The customer test pack. Engineering metadata is stripped: a customer
    reacts to the piece, not to its manufacturing report."""
    from ..services.customer_validation import select_customer_pack
    from ..services.review_items import generate_review_pack

    pack = select_customer_pack(session, generate_review_pack(max_per_product=4))
    return {
        **{k: v for k, v in pack.items() if k != "items"},
        "items": [
            {"item_id": i["item_id"], "product": i["product"],
             "customer_style": i["customer_style"], "source_text": i["source_text"],
             "width_mm": i["width_mm"], "height_mm": i["height_mm"],
             "proof_path_d": i["proof_path_d"], "proof_view": i["proof_view"]}
            for i in pack["items"]
        ],
    }


@router.post("/customer-validation/response", dependencies=[Depends(require_admin)])
def submit_customer_response(
    body: CustomerResponseSubmission, session: Session = Depends(get_session)
):
    """Record one anonymous customer response. Stored in its own table and
    never merged into expert review scores."""
    from ..services.customer_validation import ResponseRejected, record_customer_response

    try:
        row = record_customer_response(session, **body.model_dump())
    except ResponseRejected as exc:
        raise HTTPException(422, str(exc))
    session.commit()
    return {"recorded": True, "response_id": str(row.id)}


@router.get("/review/wave-1", dependencies=[Depends(require_admin)])
def review_wave_1(session: Session = Depends(get_session), reviewer: str = ""):
    """HUMAN_REVIEW_WAVE_1 — the prioritised first slate.

    Blinded by default: prior reviewers' opinions are withheld until this
    reviewer has submitted for an item."""
    from ..services.curation_analysis import product_comparison_readiness
    from ..services.review_items import build_wave_1
    from ..services.review_workflow import (
        DIMENSION_LABELS, HUMAN_DIMENSIONS, curation_decisions,
    )

    wave = build_wave_1()
    decisions = curation_decisions(session, wave["items"])
    by_item = {d["item_id"]: d for d in decisions}
    reviewed = {
        r.item_id for r in session.execute(
            select(m.DesignReview).where(m.DesignReview.reviewer == reviewer)
        ).scalars()
    } if reviewer else set()
    return {
        **{k: v for k, v in wave.items() if k != "items"},
        "items": [
            {**item,
             "curation": _blind(by_item[item["item_id"]],
                                reviewer if item["item_id"] in reviewed else "")}
            for item in wave["items"]
        ],
        "dimensions": HUMAN_DIMENSIONS,
        "dimension_labels": DIMENSION_LABELS,
        "comparison_readiness": product_comparison_readiness(session, wave["items"]),
        "blinded": True,
    }


@router.get("/review/agreement/{item_id}", dependencies=[Depends(require_admin)])
def review_agreement(item_id: str, session: Session = Depends(get_session)):
    """Mean, spread and per-dimension disagreement across independent
    reviewers. Available AFTER review — it is comparison, not anchoring."""
    from ..services.curation_analysis import agreement_report

    return agreement_report(session, item_id)
