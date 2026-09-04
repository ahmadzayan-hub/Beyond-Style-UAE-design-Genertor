"""Reference / WhatsApp customer intake.

Deterministic, rule-based classification and reference analysis — the
basic flow never depends on an external AI provider. An optional
AI/vision analyzer can be plugged behind IntakeAnalyzer + feature flag
(INTAKE_AI_ENABLED); its output can only fill *suggested* metadata,
never confirmed text.

Hard rule (Arabic truth): OCR/vision-detected text is never authoritative.
`CustomerBrief.confirmed_text` is written exclusively by explicit customer
confirmation, which also drives DesignRequest text confirmation.
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..security.uploads import (
    UploadRejected,
    get_scanner,
    REQUIRE_MALWARE_SCAN,
    get_storage,
    sha256_of,
    validate_and_strip,
)
from .design_service import _emit

INTAKE_AI_ENABLED = os.environ.get("INTAKE_AI_ENABLED", "0") == "1"

REQUEST_TYPES = {
    "EXACT_TEXT_REPLACEMENT",
    "SAME_STRUCTURE_NEW_TEXT",
    "STYLE_INSPIRED_REDESIGN",
    "PRODUCT_CONVERSION",
    "MATERIAL_CONVERSION",
    "TEXT_ONLY_DESIGN",
    "NEEDS_CLARIFICATION",
}

PROVENANCES = {
    "BEYOND_STYLE_OWNED",
    "CUSTOMER_OWNED",
    "LICENSED",
    "INSPIRATION_ONLY",
    "UNKNOWN",
    "POTENTIAL_COPY_RISK",
}


class IntakeAnalyzer(Protocol):
    """Optional AI/vision adapter interface (feature-flagged)."""

    def analyze(self, image_bytes: bytes) -> dict: ...


def get_analyzer() -> IntakeAnalyzer | None:
    # No AI provider wired in P0; deterministic fallback is the default path.
    return None


# Arabic + English cue patterns for deterministic classification.
_SAME_STRUCTURE_CUES = [
    r"نفس\s+(الشكل|التصميم|الستايل|الموديل)",
    r"same\s+(style|design|shape|structure)",
]
_CHANGE_TEXT_CUES = [
    r"(غير|بدل|عدل)\s+(الكتابة|الاسم|النص)",
    r"change\s+the\s+(writing|text|name)",
    r"بس\s+(اسم|باسم)",
]
_INSPIRED_CUES = [r"مستوحى", r"شبيه", r"inspired", r"similar\s+vibe"]
_PRODUCT_CONVERSION_CUES = [
    r"(حول|حوّل|خل|اجعل)\S*\s+(خاتم|اسوار|سوار|حلق|تعليقة|قلادة)",
    r"(as|into)\s+a\s+(ring|bracelet|earring|pendant|necklace)",
]
_MATERIAL_CONVERSION_CUES = [
    r"(ذهب|فضة|روز|أصفر|أبيض)\s*(بدل|بدال)",
    r"in\s+(gold|silver|rose)\s+instead",
]
_BRAND_RISK_CUES = [
    r"(كارتير|تيفاني|فان\s*كليف|بولغري|شانيل|ماركة)",
    r"(cartier|tiffany|van\s*cleef|bulgari|chanel|brand(ed)?\s+(piece|design))",
]


def _match_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_request(message: str | None, has_reference: bool, has_text: bool) -> tuple[str, float]:
    """Deterministic classification. Returns (request_type, confidence)."""
    msg = (message or "").strip()
    if not has_reference:
        if has_text:
            return "TEXT_ONLY_DESIGN", 1.0
        return "NEEDS_CLARIFICATION", 1.0
    same = _match_any(_SAME_STRUCTURE_CUES, msg)
    change = _match_any(_CHANGE_TEXT_CUES, msg)
    if _match_any(_PRODUCT_CONVERSION_CUES, msg):
        return "PRODUCT_CONVERSION", 0.8
    if _match_any(_MATERIAL_CONVERSION_CUES, msg):
        return "MATERIAL_CONVERSION", 0.8
    if same and change:
        return "SAME_STRUCTURE_NEW_TEXT", 0.9
    if change:
        return "EXACT_TEXT_REPLACEMENT", 0.7
    if _match_any(_INSPIRED_CUES, msg) or same:
        return "STYLE_INSPIRED_REDESIGN", 0.7
    return "NEEDS_CLARIFICATION", 0.5


def assess_ip_risk(message: str | None, provenance: str) -> str:
    """Flag likely protected/branded references. Copy risk means we only
    produce inspired alternatives from abstract Design DNA — never promise
    an exact copy."""
    if provenance in ("BEYOND_STYLE_OWNED", "CUSTOMER_OWNED", "LICENSED"):
        return "CLEARED"
    if _match_any(_BRAND_RISK_CUES, message or ""):
        return "POTENTIAL_COPY_RISK"
    return "INSPIRATION_ONLY"


def add_reference(
    session: Session,
    request_id: uuid.UUID,
    data: bytes,
    filename: str,
    declared_type: str | None,
    provenance: str = "UNKNOWN",
    customer_message: str | None = None,
) -> m.ReferenceAsset:
    if provenance not in PROVENANCES:
        raise UploadRejected("Invalid provenance value.")
    clean, media_type, analysis = validate_and_strip(data, declared_type)
    scan_status = get_scanner().scan(clean)
    if scan_status.startswith("INFECTED"):
        raise UploadRejected("The file was rejected by the malware scanner.")
    if REQUIRE_MALWARE_SCAN and scan_status != "CLEAN":
        # Production policy: nothing unscanned is stored. Honest failure
        # (scanner down) is a refusal, never a silent "clean".
        raise UploadRejected("Uploads are temporarily unavailable: the malware scanner did not confirm the file.")

    analyzer = get_analyzer()
    if INTAKE_AI_ENABLED and analyzer is not None:
        try:
            suggested = analyzer.analyze(clean)
            # Vision output is suggestion-only; text keys are dropped hard.
            suggested.pop("detected_text", None)
            analysis["ai_suggested"] = suggested
        except Exception:
            analysis["ai_suggested"] = None  # fallback stays deterministic

    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[media_type]
    key = get_storage().put(clean, suffix)
    asset = m.ReferenceAsset(
        design_request_id=request_id,
        original_filename=filename[:255],
        media_type=media_type,
        storage_key=key,
        sha256=sha256_of(clean),
        size_bytes=len(clean),
        provenance=provenance,
        ip_risk=assess_ip_risk(customer_message, provenance),
        privacy_status="PRIVATE",
        scan_status=scan_status,
        analysis=analysis,
    )
    session.add(asset)
    session.flush()
    _emit(session, "REFERENCE_UPLOADED", request_id=request_id,
          metadata={"reference_id": str(asset.id), "media_type": media_type,
                    "sha256": asset.sha256, "ip_risk": asset.ip_risk,
                    "scan_status": scan_status})
    return asset


def generation_hints_from(analysis: dict | None, style_intent: str | None) -> dict:
    """Reference analysis + style intent → structured generator hints.
    Hints reorder/boost recipe families; they never bypass the schema and
    raster is never traced into geometry."""
    hints: dict = {"source": "deterministic_intake"}
    if analysis:
        orientation = analysis.get("orientation")
        if orientation == "horizontal":
            hints["preferred_compositions"] = ["baseline_bar", "underline_bar", "bare"]
        elif orientation == "vertical":
            hints["preferred_compositions"] = ["plate_oval", "frame_circle"]
        elif orientation == "square":
            hints["preferred_compositions"] = ["plate_rect", "frame_circle", "plate_oval"]
        if analysis.get("aspect_ratio"):
            hints["target_aspect_ratio"] = analysis["aspect_ratio"]
    if style_intent:
        hints["style_intent"] = style_intent  # archetype retrieval signal
        style_map = {
            "minimal": ["kufi-wide-minimal", "kufi-solid-plate-oval"],
            "luxury": ["naskh-condensed-luxury", "naskh-classic-bar"],
            "traditional": ["trad-naskh-circle", "trad-naskh-bar"],
            "modern": ["kufi-bold-bare", "kufi-rect-plate"],
        }
        if style_intent in style_map:
            hints["preferred_recipes"] = style_map[style_intent]
    return hints


def upsert_brief(
    session: Session,
    request_id: uuid.UUID,
    customer_message: str | None = None,
    product_type: str | None = None,
    material_preference: str | None = None,
    style_intent: str | None = None,
    language: str | None = None,
    quantity: int = 1,
    deadline: str | None = None,
    delivery_emirate: str | None = None,
    style_strength: float = 0.5,
    ring_size_eu: int | None = None,
    band_height_mm: float | None = None,
    script_family: str | None = None,
) -> m.CustomerBrief:
    req = session.get(m.DesignRequest, request_id)
    if req is None:
        raise KeyError("request not found")
    refs = session.execute(
        select(m.ReferenceAsset).where(
            m.ReferenceAsset.design_request_id == request_id,
            m.ReferenceAsset.deleted.is_(False),
        )
    ).scalars().all()
    has_text = bool(req.source_text_normalized.strip())
    request_type, confidence = classify_request(customer_message, bool(refs), has_text)

    missing = []
    if not req.confirmed:
        missing.append("confirmed_text")
    if not product_type:
        missing.append("product_type")
    if refs and request_type == "NEEDS_CLARIFICATION":
        missing.append("request_intent")

    analysis = refs[0].analysis if refs else None
    brief = session.execute(
        select(m.CustomerBrief).where(m.CustomerBrief.design_request_id == request_id)
    ).scalar_one_or_none()
    if brief is None:
        brief = m.CustomerBrief(design_request_id=request_id)
        session.add(brief)
    brief.customer_message = customer_message
    brief.request_type = request_type
    brief.confidence = confidence
    brief.language = language
    brief.product_type = product_type or req.product_type
    brief.material_preference = material_preference
    brief.style_intent = style_intent
    brief.reference_ids = [str(r.id) for r in refs]
    hints = generation_hints_from(analysis, style_intent)
    # Reference Intelligence: if DesignDNA exists for a reference, its
    # visual-grammar hints take precedence (style only — never text).
    dna_row = session.execute(
        select(m.ReferenceDNARow).where(
            m.ReferenceDNARow.design_request_id == request_id
        )
    ).scalars().first()
    if dna_row is not None:
        from .reference_intelligence import dna_generation_hints

        dna_hints = dna_generation_hints(dna_row.dna, style_strength)
        merged = dict(hints)
        merged.update(dna_hints)
        if "preferred_compositions" in hints and "preferred_compositions" in dna_hints:
            merged["preferred_compositions"] = list(
                dict.fromkeys(dna_hints["preferred_compositions"] + hints["preferred_compositions"])
            )
        hints = merged
    if product_type == "ring":
        ring_hint = {}
        if ring_size_eu is not None:
            ring_hint["size_eu"] = ring_size_eu
        if band_height_mm is not None:
            ring_hint["band_height_mm"] = band_height_mm
        hints["ring"] = ring_hint
        # Generation routes on the REQUEST's product type; the brief is the
        # customer's authoritative product choice, so keep them in sync.
        req.product_type = "ring"
    # Archetype retrieval filters by the customer's product; style/DNA keys
    # above are its similarity signal (see engines/archetype_library.py).
    hints["product_type"] = brief.product_type
    if script_family:
        from ..fonts.capabilities import resolve_script_request

        resolution = resolve_script_request(script_family)
        fonts = list(resolution.get("fonts") or [])
        if not fonts and resolution.get("recommended_font_id"):
            fonts = [resolution["recommended_font_id"]]
        hints["script_family"] = script_family
        hints["script_resolution"] = {
            k: resolution.get(k) for k in ("outcome", "font_id", "recommended_font_id",
                                           "recommended_capability", "message")
        }
        # The chosen script's faces surface first in the diverse top 10 —
        # a transparent bonus, never a bypass of Arabic/manufacturing QA.
        hints["preferred_fonts"] = fonts
    brief.generation_hints = hints
    brief.quantity = quantity
    brief.deadline = deadline
    brief.delivery_emirate = delivery_emirate
    brief.missing_fields = missing
    # confirmed_text mirrors the REQUEST's confirmation only (never OCR).
    brief.confirmed_text = req.source_text_normalized if req.confirmed else None
    brief.status = "READY" if not missing else "INCOMPLETE"
    session.flush()
    _emit(session, "BRIEF_UPDATED", request_id=request_id,
          metadata={"request_type": request_type, "missing": missing,
                    "confidence": confidence})
    return brief


def delete_references(session: Session, request_id: uuid.UUID) -> int:
    """Privacy: purge reference files and soft-delete rows for a session."""
    refs = session.execute(
        select(m.ReferenceAsset).where(
            m.ReferenceAsset.design_request_id == request_id,
            m.ReferenceAsset.deleted.is_(False),
        )
    ).scalars().all()
    storage = get_storage()
    for r in refs:
        storage.delete(r.storage_key)
        r.deleted = True
        r.privacy_status = "DELETED"
    _emit(session, "REFERENCES_DELETED", request_id=request_id,
          metadata={"count": len(refs)})
    return len(refs)
