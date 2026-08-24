"""DesignMemoryService — practical retrieval/ranking learning from
feedback, WITHOUT model retraining and WITHOUT mutating history.

Signals are append-only design_events; ranking adjustments are computed
on the fly from them (fully reproducible from the audit trail):
  approved + produced designs boost their recipe families,
  rejections reduce them, workshop failures become blocking constraints.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from .design_service import _emit

FEEDBACK_EVENTS = {
    "REFERENCE_ANALYZED",
    "DESIGN_GENERATED",
    "CUSTOMER_SELECTED",
    "DESIGNER_EDITED",
    "CUSTOMER_APPROVED",
    "WORKSHOP_ACCEPTED",
    "WORKSHOP_REJECTED",
    "PRODUCED",
    "CUSTOMER_FEEDBACK",
}

#: Event → recipe-family weight delta (bounded, deterministic).
EVENT_WEIGHTS = {
    "CUSTOMER_SELECTED": 0.05,
    "CUSTOMER_APPROVED": 0.15,
    "WORKSHOP_ACCEPTED": 0.2,
    "PRODUCED": 0.3,
    "WORKSHOP_REJECTED": -0.3,
    "CUSTOMER_FEEDBACK_NEGATIVE": -0.05,
}


def record_feedback(
    session: Session,
    event_type: str,
    request_id: uuid.UUID | None = None,
    design_id: uuid.UUID | None = None,
    version_id: uuid.UUID | None = None,
    actor: str = "system",
    metadata: dict | None = None,
) -> None:
    if event_type not in FEEDBACK_EVENTS:
        raise ValueError(f"Unknown feedback event: {event_type}")
    _emit(session, event_type, request_id=request_id, design_id=design_id,
          version_id=version_id, actor=actor, actor_type="feedback",
          metadata=metadata)


def recipe_family_weights(session: Session) -> dict[str, float]:
    """Aggregate feedback into per-recipe-family ranking weights in
    [-0.5, +0.5]. Recomputed from events — history is never mutated."""
    weights: dict[str, float] = {}
    rows = session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type.in_(EVENT_WEIGHTS.keys() | {"CUSTOMER_FEEDBACK"}))
    ).scalars().all()
    for ev in rows:
        meta = ev.event_metadata or {}
        family = meta.get("recipe_family")
        if not family:
            continue
        key = ev.event_type
        if key == "CUSTOMER_FEEDBACK":
            key = "CUSTOMER_FEEDBACK_NEGATIVE" if meta.get("sentiment") == "negative" else None
        delta = EVENT_WEIGHTS.get(key or "", 0.0)
        weights[family] = max(-0.5, min(0.5, weights.get(family, 0.0) + delta))
    return weights


def workshop_failure_constraints(session: Session) -> list[dict]:
    """WORKSHOP_REJECTED reasons become reusable constraints (surfaced to
    the validator/designer — hard rules change only via human review)."""
    rows = session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "WORKSHOP_REJECTED")
    ).scalars().all()
    return [
        {
            "reason": (ev.event_metadata or {}).get("reason", "unspecified"),
            "recipe_family": (ev.event_metadata or {}).get("recipe_family"),
            "version_id": str(ev.version_id) if ev.version_id else None,
        }
        for ev in rows
    ]


def export_lora_dataset(session: Session, require_consent: bool = True) -> list[dict]:
    """Dataset export for FUTURE LoRA training — rights/consent-gated,
    never automatic. Only references with explicit reusable rights and
    designs that reached approval are exported."""
    allowed_provenance = {"BEYOND_STYLE_OWNED", "CUSTOMER_OWNED", "LICENSED"}
    out = []
    dna_rows = session.execute(select(m.ReferenceDNARow)).scalars().all()
    for dna in dna_rows:
        asset = session.get(m.ReferenceAsset, dna.reference_id)
        if asset is None or asset.deleted:
            continue
        if require_consent and asset.provenance not in allowed_provenance:
            continue
        approved = session.execute(
            select(m.DesignVersion)
            .join(m.Design, m.DesignVersion.design_id == m.Design.id)
            .where(
                m.Design.request_id == dna.design_request_id,
                m.DesignVersion.status == "APPROVED_LOCKED",
            )
        ).scalars().first()
        if approved is None:
            continue
        out.append(
            {
                "reference_sha256": asset.sha256,
                "provenance": asset.provenance,
                "design_dna": dna.dna,
                "product_type": dna.dna.get("product_type"),
                "approved_recipe": approved.recipe,
                "outcome": "APPROVED_LOCKED",
            }
        )
    return out
