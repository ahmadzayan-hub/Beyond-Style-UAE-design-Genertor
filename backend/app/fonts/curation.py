"""Aesthetic curation — product-specific suitability, curation states and
the customer-facing style language.

The honesty rule that shapes this module: some of the thirteen suitability
dimensions can be MEASURED from real geometry, and some are genuine
aesthetic judgements that no deterministic function can make. They are kept
in two separate sets. A computed dimension carries a number and its method;
a judgement dimension stays `None` with `NOT_ASSESSED` until a human at
Beyond Style reviews the proof sheets. Nothing here invents a taste score.

Consequently every newly discovered OT feature starts EXPERIMENTAL and is
hidden from customers until that human review happens.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

CURATION_FILE = Path(__file__).resolve().parent.parent / "data" / "curation.json"


class CurationState(str, Enum):
    #: Reviewed and preferred — offered first.
    PRODUCTION_RECOMMENDED = "PRODUCTION_RECOMMENDED"
    #: Safe and selectable, not actively promoted.
    PRODUCTION_ALLOWED = "PRODUCTION_ALLOWED"
    #: Technically safe, aesthetically unreviewed. Internal surfaces only.
    EXPERIMENTAL = "EXPERIMENTAL"
    #: Never offered anywhere.
    HIDDEN = "HIDDEN"


#: Only these may be shown to a customer or used in customer-facing ranking.
CUSTOMER_VISIBLE_STATES = {
    CurationState.PRODUCTION_RECOMMENDED,
    CurationState.PRODUCTION_ALLOWED,
}


@dataclass(frozen=True)
class ProductProfile:
    """Physical envelope a piece must live inside. Suitability is always
    asked per product — a face that sings on a medallion can be unreadable
    on a single-letter earring."""

    product: str
    target_height_mm: float
    max_width_mm: float
    representative_text: str
    preferred_compositions: tuple[str, ...]
    small_size: bool = False
    multi_name: bool = False
    openwork: bool = False


PRODUCTS: dict[str, ProductProfile] = {
    p.product: p
    for p in [
        ProductProfile("single_letter_earring", 11, 18, "ع", ("bare", "plate_oval"), small_size=True),
        ProductProfile("drop_earring", 13, 20, "نورة", ("bare", "top_bar"), small_size=True),
        ProductProfile("pendant", 16, 34, "نورة", ("baseline_bar", "plate_oval", "frame_circle")),
        ProductProfile("necklace", 16, 40, "ميثة", ("baseline_bar", "underline_bar")),
        ProductProfile("ring", 7, 14, "ع", ("bare", "plate_rect"), small_size=True),
        ProductProfile("bracelet", 11, 30, "محمد", ("baseline_bar", "plate_rect")),
        ProductProfile("cufflink", 10, 16, "محمد", ("plate_rect", "plate_oval"), small_size=True),
        ProductProfile("brooch", 18, 36, "فاطمة", ("plate_oval", "frame_rect")),
        ProductProfile("multi_name", 22, 44, "حامد محمد سلطان ميثة حمد خالد مهرة",
                       ("baseline_bar", "plate_rect"), multi_name=True),
        ProductProfile("medallion", 22, 40, "كن ما تبحث عنه في عيون الآخرين",
                       ("frame_circle", "plate_oval")),
        ProductProfile("engraving", 14, 34, "سلطان", ("plate_rect", "plate_oval")),
        ProductProfile("openwork", 18, 36, "خالد", ("bare", "frame_rect"), openwork=True),
    ]
}

#: Measured from the built geometry — each carries its method, and each is
#: reproducible from the same inputs.
COMPUTED_DIMENSIONS = {
    "Readability": "min effective gap + identity proof (geometry)",
    "Rhythm": "variance of glyph advances (shaping)",
    "Balance": "centroid offset from bounding-box centre (geometry)",
    "NegativeSpace": "1 - fill ratio (geometry)",
    "StrokeRobustness": "stroke slack above the workshop minimum (validator)",
    "DotIslandRisk": "disconnected component + hole count (geometry)",
    "Compactness": "fill ratio within the product envelope (geometry)",
    "SmallSizeSuitability": "validator pass at the product's target height",
    "MultiNameSuitability": "validator pass on the seven-name string",
    "ManufacturingHarmony": "validator pass rate across the product's compositions",
}

#: Genuine aesthetic judgements. No deterministic proxy is honest here, so
#: they stay unscored until a human reviews the proof sheets.
HUMAN_REVIEW_DIMENSIONS = {
    "CalligraphicGrace": "requires human review of the proof sheets",
    "OrnamentalPotential": "requires human review of the proof sheets",
    "LuxuryFeel": "requires human review of the proof sheets",
}

ALL_DIMENSIONS = {**COMPUTED_DIMENSIONS, **HUMAN_REVIEW_DIMENSIONS}


# ---------------------------------------------------------------------------
# Customer style language — Arabic labels, never raw OpenType tags
# ---------------------------------------------------------------------------

#: What a customer picks. Each maps INTERNALLY to curated font + features +
#: axis range + composition. A customer never sees `ss03` or `wght`.
STYLE_LANGUAGE: dict[str, dict] = {
    "كلاسيكي": {"en": "classical", "script_families": ["naskh"],
                "fonts": ["amiri-regular", "scheherazade-new"]},
    "ناعم": {"en": "soft", "script_families": ["naskh"], "fonts": ["lemonada", "scheherazade-new"]},
    "فاخر": {"en": "luxurious", "script_families": ["naskh"], "fonts": ["katibeh", "amiri-regular"]},
    "هندسي": {"en": "geometric", "script_families": ["kufi", "geometric_kufi"], "fonts": ["reem-kufi"]},
    "حديث": {"en": "modern", "script_families": ["modern_arabic", "minimal"],
             "fonts": ["tajawal", "cairo"]},
    "انسيابي": {"en": "flowing", "script_families": ["nastaliq"], "fonts": ["noto-nastaliq-urdu", "lemonada"]},
    "تراثي": {"en": "heritage", "script_families": ["ruqaa", "naskh"], "fonts": ["aref-ruqaa", "amiri-regular"]},
    "جريء": {"en": "bold", "script_families": ["kufi"], "fonts": ["reem-kufi", "katibeh"]},
}


@lru_cache(maxsize=1)
def load_curation() -> dict:
    if not CURATION_FILE.is_file():
        return {"features": {}, "recipes": {}, "note": "not yet generated"}
    return json.loads(CURATION_FILE.read_text(encoding="utf-8"))


def curation_state(kind: str, key: str) -> CurationState:
    """State of one feature set or recipe. Unknown keys are EXPERIMENTAL,
    never silently promoted."""
    entry = load_curation().get(kind, {}).get(key)
    if entry is None:
        return CurationState.EXPERIMENTAL
    return CurationState(entry["state"])


def is_customer_visible(kind: str, key: str) -> bool:
    return curation_state(kind, key) in CUSTOMER_VISIBLE_STATES


def customer_style_options() -> list[dict]:
    """The picker payload: Arabic label, English gloss, and the curated
    fonts behind it — with raw OT tags deliberately absent."""
    from .capabilities import script_capability_map

    caps = script_capability_map()
    out = []
    for label, spec in STYLE_LANGUAGE.items():
        statuses = {caps[f]["status"] for f in spec["script_families"] if f in caps}
        out.append({
            "label_ar": label,
            "label_en": spec["en"],
            "available": "REAL" in statuses,
            "fonts": spec["fonts"],
            "script_families": spec["script_families"],
        })
    return out


def resolve_style_label(label_ar: str) -> dict:
    """Arabic style label → internal bundle. Raw OT tags never leave this
    boundary as customer-facing data; they are generation inputs only."""
    from .glyph_variants import font_variant_capabilities

    spec = STYLE_LANGUAGE.get(label_ar)
    if spec is None:
        return {"label_ar": label_ar, "outcome": "UNKNOWN_STYLE", "fonts": []}
    bundle = []
    for font_id in spec["fonts"]:
        visible = [
            v for v in font_variant_capabilities(font_id)
            if is_customer_visible("features", v["set_id"])
        ]
        bundle.append({
            "font_id": font_id,
            "curated_feature_sets": [v["set_id"] for v in visible],
            "axis_ranges": safe_axis_ranges(font_id),
        })
    return {"label_ar": label_ar, "label_en": spec["en"], "outcome": "RESOLVED", "fonts": bundle}


def safe_axis_ranges(font_id: str, product: str | None = None) -> dict:
    """Product-scoped safe variable-axis ranges from the sweep report."""
    axes = load_curation().get("axis_ranges", {}).get(font_id, {})
    if product is None:
        return axes.get("default", {})
    return axes.get("products", {}).get(product, axes.get("default", {}))


# ---------------------------------------------------------------------------
# The gate aesthetics may never cross
# ---------------------------------------------------------------------------

def aesthetic_gate(validation_passed: bool, aesthetic_score: float | None) -> dict:
    """Beauty never buys a pass. A candidate that fails manufacturing is
    rejected whatever it scores aesthetically — the aesthetic number is
    carried for reporting only."""
    if not validation_passed:
        return {
            "selectable": False,
            "reason": "MANUFACTURING_VALIDATION_FAILED",
            "aesthetic_score": aesthetic_score,
            "note": "aesthetic score is advisory and cannot override a manufacturing failure",
        }
    return {"selectable": True, "reason": None, "aesthetic_score": aesthetic_score}


def golden_case_influence(product: str) -> list[dict]:
    """Proven lessons from real manufactured, customer-approved orders that
    apply to this product.

    Evidence priority (highest first): manufactured + customer-approved,
    workshop-approved, designer-approved, AI aesthetic opinion. AI taste
    ranks last and is advisory; a lesson from a delivered piece outranks it.
    Construction principles transfer — geometry never does."""
    from ..data.golden_production_cases import GOLDEN_PRODUCTION_CASES

    earring_products = {"single_letter_earring", "drop_earring"}
    necklace_products = {"necklace", "pendant", "multi_name"}
    out = []
    for case in GOLDEN_PRODUCTION_CASES:
        is_earring = "EARRING" in case["product_type"]
        applies = earring_products if is_earring else necklace_products
        if product not in applies:
            continue
        out.append({
            "case_id": case["case_id"],
            "evidence_tier": case["evidence_tier"],
            "construction_principles": list(case["construction"]),
            "lessons": list(case["lessons_learned"]),
            "geometry_copied": False,
        })
    return out


#: Evidence ranks. AI aesthetic opinion is last and advisory only.
EVIDENCE_PRIORITY = [
    "MANUFACTURED_CUSTOMER_APPROVED",
    "WORKSHOP_APPROVED",
    "DESIGNER_APPROVED",
    "AI_AESTHETIC_OPINION",
]


def designer_axis_bounds(font_id: str, product: str) -> dict:
    """Bounds for the designer's weight slider.

    Only ranges whose evidence_level is GEOMETRY_VERIFIED_SAFE are offered.
    An untested or unsafe combination returns `available: False` with the
    reason, so the control is visibly unavailable rather than silently
    permissive."""
    from .instances import font_axis_specs

    specs = font_axis_specs(font_id)
    if not specs:
        return {"font_id": font_id, "product": product, "available": False,
                "reason": "STATIC_FONT_NO_AXES", "axes": {}}
    ranges = load_curation().get("product_axis_ranges", {}).get(font_id, {})
    axes = {}
    for tag, spec in specs.items():
        entry = ranges.get(tag, {}).get(product)
        if not entry or entry.get("min_safe") is None:
            axes[tag] = {
                "available": False,
                "reason": "NOT_GEOMETRY_VERIFIED_FOR_THIS_PRODUCT",
                "font_min": spec["min"], "font_max": spec["max"],
                "default": spec["default"],
            }
            continue
        axes[tag] = {
            "available": True,
            "min": entry["min_safe"], "max": entry["max_safe"],
            "default": spec["default"],
            "font_min": spec["min"], "font_max": spec["max"],
            "evidence_level": entry["evidence_level"],
            "tested_values": entry.get("tested_values", []),
            "manufacturing_profile": entry.get("manufacturing_profile"),
        }
    return {
        "font_id": font_id, "product": product,
        "available": any(a["available"] for a in axes.values()),
        "axes": axes,
        "note": "Designer-mode control. Customers never see numeric axis values.",
    }


def customer_axis_for_style(label_ar: str, font_id: str, product: str) -> dict:
    """What a CUSTOMER's style choice resolves to internally.

    The customer picks a word; this returns the curated coordinate. The
    value is clamped to nothing — if the style's intent falls outside the
    verified range, the safe bound is used and that substitution is
    reported, never hidden."""
    bounds = designer_axis_bounds(font_id, product)
    wght = bounds["axes"].get("wght")
    if not wght or not wght["available"]:
        return {"font_axes": {}, "reason": "NO_VERIFIED_AXIS_RANGE", "style": label_ar}
    #: Style intent as a fraction of the verified safe span.
    intent = {"ناعم": 0.0, "كلاسيكي": 0.25, "تراثي": 0.25, "حديث": 0.4,
              "هندسي": 0.5, "انسيابي": 0.4, "فاخر": 0.6, "جريء": 1.0}
    fraction = intent.get(label_ar, 0.25)
    value = wght["min"] + fraction * (wght["max"] - wght["min"])
    return {
        "style": label_ar,
        "font_axes": {"wght": round(value, 1)},
        "within_verified_range": [wght["min"], wght["max"]],
        "evidence_level": wght["evidence_level"],
    }
