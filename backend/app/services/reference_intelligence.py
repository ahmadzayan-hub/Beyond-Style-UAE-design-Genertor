"""Reference Intelligence pipeline.

image (already security-gated + rights-gated by intake)
→ VLM analysis (real model via worker when available; deterministic
  fallback DNA otherwise, source labelled)
→ DesignDNA → embedding → storage
→ retrieve similar APPROVED references
→ enrich the brief's generation hints (style grammar only — the
  deterministic Arabic/vector engine rebuilds all geometry; reference
  text NEVER becomes source text).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import config as ai_config
from ..ai.design_dna import DesignDNA, VLM_INSTRUCTION, fallback_dna, parse_vlm_dna
from ..ai.embeddings import ENCODER_VERSION, encode_dna, rank_by_similarity
from ..ai.providers import ModelUnavailable, get_visual_analyzer
from ..db import models as m
from ..security.uploads import get_storage
from .design_service import _emit

#: Copy-risk DNA indicators that force INSPIRED_ALTERNATIVE_REQUIRED.
HIGH_COPY_RISK = {"brand_logo", "watermark", "trademark", "designer_signature"}


def analyze_reference(session: Session, reference_id: uuid.UUID) -> m.ReferenceDNARow:
    """Produce (or return existing) DesignDNA for a reference. Uses the
    real visual analyzer when available; otherwise the deterministic
    fallback — the `source` field always says which one ran."""
    asset = session.get(m.ReferenceAsset, reference_id)
    if asset is None or asset.deleted:
        raise KeyError("reference not found")
    existing = session.execute(
        select(m.ReferenceDNARow).where(m.ReferenceDNARow.reference_id == reference_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    dna: DesignDNA
    try:
        analyzer = get_visual_analyzer()
        raw = analyzer.analyze(get_storage().get(asset.storage_key), VLM_INSTRUCTION)
        dna = parse_vlm_dna(raw, f"{ai_config.VISUAL_MODEL}")
    except ModelUnavailable:
        dna = fallback_dna(asset.analysis)

    # Merge intake copy-risk into DNA indicators.
    if asset.ip_risk == "POTENTIAL_COPY_RISK" and "intake_brand_cue" not in dna.copy_risk_indicators:
        dna.copy_risk_indicators.append("intake_brand_cue")

    row = m.ReferenceDNARow(
        reference_id=asset.id,
        design_request_id=asset.design_request_id,
        source=dna.source,
        analyzer_model=dna.analyzer_model,
        dna=dna.model_dump(),
        embedding=encode_dna(dna),
        encoder_version=ENCODER_VERSION,
    )
    session.add(row)
    session.flush()
    _emit(session, "REFERENCE_ANALYZED", request_id=asset.design_request_id,
          metadata={"reference_id": str(asset.id), "source": dna.source,
                    "analyzer_model": dna.analyzer_model,
                    "copy_risk": dna.copy_risk_indicators})
    return row


def copy_risk_status(dna_row: m.ReferenceDNARow) -> str:
    indicators = set(dna_row.dna.get("copy_risk_indicators", []))
    if indicators & (HIGH_COPY_RISK | {"intake_brand_cue"}):
        return "INSPIRED_ALTERNATIVE_REQUIRED"
    return "OK"


def retrieve_similar_approved(session: Session, dna_row: m.ReferenceDNARow, top_k: int = 5):
    """Retrieve similar references belonging to APPROVED designs — the
    highest-value memory. Returns [(reference_dna_id, similarity)]."""
    approved_request_ids = {
        row[0]
        for row in session.execute(
            select(m.Design.request_id)
            .join(m.DesignVersion, m.DesignVersion.design_id == m.Design.id)
            .where(m.DesignVersion.status == "APPROVED_LOCKED")
        )
    }
    rows = session.execute(
        select(m.ReferenceDNARow).where(m.ReferenceDNARow.id != dna_row.id)
    ).scalars().all()
    pool = [
        (str(r.id), r.embedding)
        for r in rows
        if r.design_request_id in approved_request_ids
    ]
    return rank_by_similarity(dna_row.embedding, pool, top_k)


def dna_generation_hints(dna: dict, style_strength: float = 0.5) -> dict:
    """DesignDNA → deterministic generator hints (visual grammar only).
    style_strength: 0 = 'more original', 1 = 'similar inspiration' —
    scales the hint bonus, never bypasses schema or validation."""
    hints: dict = {"source": "reference_dna", "style_strength": round(style_strength, 2)}
    comp_map = {
        "horizontal": ["baseline_bar", "underline_bar", "bare"],
        "vertical": ["plate_oval", "frame_circle"],
        "stacked": ["bare", "plate_rect"],
        "circular": ["frame_circle"],
        "medallion": ["frame_circle", "plate_oval"],
        "emblem": ["plate_rect", "frame_rect", "plate_oval"],
        "framed": ["frame_rect", "frame_circle"],
        "openwork": ["bare", "frame_rect"],
        "plate_engraving": ["plate_rect", "plate_oval"],
        "relief": ["plate_oval", "plate_rect"],
        "suspended": ["top_bar"],
    }
    if dna.get("composition") in comp_map:
        hints["preferred_compositions"] = comp_map[dna["composition"]]
    if dna.get("construction") == "openwork":
        hints.setdefault("preferred_compositions", []).extend(["bare", "frame_rect"])
    if dna.get("kashida") in ("present", "strong"):
        hints["prefer_kashida"] = True
    if dna.get("swashes") in ("present", "expressive"):
        hints["prefer_swash"] = True
    if dna.get("aspect_ratio"):
        hints["target_aspect_ratio"] = dna["aspect_ratio"]
    hints["bonus_scale"] = 0.5 + style_strength  # 0.5–1.5 × standard bonus
    # Visual-grammar fields only (never text) for archetype retrieval.
    fields = {k: dna.get(k) for k in ("script_family", "composition", "construction",
                                      "dot_style", "swashes", "kashida")
              if dna.get(k) not in (None, "unknown")}
    if fields:
        hints["dna_fields"] = fields
    return hints
