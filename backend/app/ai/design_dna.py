"""DesignDNA — structured, schema-validated visual grammar of a reference.

Two sources, always labelled:
- "vlm": strict-JSON output of the real visual analyzer (when available).
- "deterministic_fallback": image-metadata-derived subset (always works).

Hard rule: any `detected_text`/`ocr_text` keys from a VLM are dropped —
reference text can NEVER become customer source text.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ValidationError

PRODUCT_TYPES = [
    "necklace", "pendant", "bracelet", "bangle", "ring", "earring", "stud",
    "drop_earring", "cufflinks", "brooch", "anklet", "keychain",
    "tasbih_accessory", "car_mirror_hanger", "bookmark", "pen_accessory",
    "wallet_accessory", "family_multi_name", "corporate_gift", "unknown",
]
SCRIPT_FAMILIES = [
    "diwani", "diwani_jali", "thuluth", "thuluth_jali", "naskh", "ruqaa",
    "kufi", "geometric_kufi", "square_kufi", "farsi", "nastaliq",
    "modern_arabic", "minimal", "monogram", "latin_script", "unknown",
]
COMPOSITIONS = [
    "horizontal", "vertical", "stacked", "circular", "radial", "oval",
    "teardrop", "medallion", "emblem", "monogram", "interlocking",
    "negative_space", "framed", "openwork", "plate_engraving", "relief",
    "suspended", "multi_name", "mixed_scripts", "unknown",
]


class DesignDNA(BaseModel):
    """Strict schema — VLM output is validated against this; extra keys
    (including any OCR/text fields) are rejected/dropped."""

    model_config = {"extra": "forbid"}

    source: str  # "vlm" | "deterministic_fallback"
    analyzer_model: str  # model id + version, or "none"
    product_type: str = "unknown"
    audience: str = "unknown"  # women | men | kids | unisex | unknown
    material: str = "unknown"
    metal_color: str = "unknown"
    script_family: str = "unknown"
    calligraphy_style: str = "unknown"
    composition: str = "unknown"
    shape_envelope: str = "unknown"
    construction: str = "unknown"  # openwork | plate | relief | engraving | unknown
    stroke_character: str = "unknown"
    kashida: str = "unknown"
    swashes: str = "unknown"
    tails: str = "unknown"
    dot_style: str = "unknown"
    harakat_style: str = "unknown"
    symmetry: str = "unknown"
    negative_space: str = "unknown"
    frame: str = "unknown"
    bail_loops: str = "unknown"
    chain_attachment: str = "unknown"
    stones: str = "unknown"
    pearls: str = "unknown"
    enamel: str = "unknown"
    ornament: str = "unknown"
    geometry_density: str = "unknown"
    luxury_score: float = Field(0.5, ge=0, le=1)
    minimal_score: float = Field(0.5, ge=0, le=1)
    heritage_score: float = Field(0.5, ge=0, le=1)
    modern_score: float = Field(0.5, ge=0, le=1)
    manufacturing_complexity: str = "unknown"  # low | medium | high | unknown
    reference_confidence: float = Field(0.0, ge=0, le=1)
    copy_risk_indicators: list[str] = Field(default_factory=list)
    aspect_ratio: Optional[float] = None
    orientation: Optional[str] = None


FORBIDDEN_TEXT_KEYS = {"detected_text", "ocr_text", "text", "arabic_text", "name", "inscription"}

VLM_INSTRUCTION = (
    "Analyze this jewellery/calligraphy reference image. Return STRICT JSON "
    "matching the DesignDNA schema fields (product_type, script_family, "
    "composition, construction, stroke_character, symmetry, frame, stones, "
    "ornament, luxury_score, ...). Describe visual/structural style only. "
    "Do NOT transcribe, read or return any text content from the image."
)


def parse_vlm_dna(raw: dict, analyzer_model: str) -> DesignDNA:
    """Validate VLM JSON strictly. Text-content keys are dropped before
    validation — reference text never becomes data."""
    cleaned = {k: v for k, v in raw.items() if k not in FORBIDDEN_TEXT_KEYS}
    cleaned["source"] = "vlm"
    cleaned["analyzer_model"] = analyzer_model
    allowed = set(DesignDNA.model_fields)
    cleaned = {k: v for k, v in cleaned.items() if k in allowed}
    try:
        return DesignDNA(**cleaned)
    except ValidationError as exc:
        raise ValueError(f"VLM output failed DesignDNA schema: {exc}") from exc


def fallback_dna(image_analysis: dict | None) -> DesignDNA:
    """Deterministic DNA from the existing safe image metadata (aspect
    ratio/orientation). Honest: most fields stay 'unknown'."""
    analysis = image_analysis or {}
    return DesignDNA(
        source="deterministic_fallback",
        analyzer_model="none",
        aspect_ratio=analysis.get("aspect_ratio"),
        orientation=analysis.get("orientation"),
        composition={
            "horizontal": "horizontal",
            "vertical": "vertical",
            "square": "emblem",
        }.get(analysis.get("orientation"), "unknown"),
        reference_confidence=0.2 if analysis else 0.0,
    )
