"""Review item generation and prioritisation.

Every possible combination would be tens of thousands of items and would
waste the scarcest resource in this system — an Art Director's attention.
So items are generated only where they could matter and ranked by:

  manufacturing PASS · engineering suitability · Golden Production
  relevance · diversity

Diversity is enforced explicitly: the pack must not be nine near-identical
Naskh pendants. Each item carries the rendered proof plus the engineering
gates, so a reviewer judges a real jewellery piece, never a font specimen.
"""
from __future__ import annotations

from shapely import wkt as _wkt

from ..config import DEFAULT_RULES
from ..engines.generator import build_candidate
from ..engines.geometry_metrics import measure_mm, meets_workshop_rules
from ..exporters.svg_exporter import geometry_to_path_d
from ..fonts.curation import PRODUCTS, STYLE_LANGUAGE, golden_case_influence
from ..fonts.registry import get_registry
from ..fonts.suitability import _recipe
from ..schemas.jewellery_design import ImmutableSourceText
from .review_workflow import item_id, recipe_hash

#: §3 review order — the products the shop actually sells most.
REVIEW_PRODUCTS = [
    "single_letter_earring", "pendant", "necklace", "cufflink",
    "ring", "bracelet", "multi_name", "medallion", "openwork",
]

#: §4 — a font is never judged on one word.
REVIEW_CORPUS = ["ع", "نورة", "ميثة", "محمد", "فاطمة", "حامد", "سلطان", "خالد", "مهرة"]
PHRASE = "كن ما تبحث عنه في عيون الآخرين"
SEVEN_NAMES = "حامد محمد سلطان ميثة حمد خالد مهرة"


def _customer_style_for(font_id: str) -> str | None:
    """The customer-facing word this font sits behind. The reviewer sees
    the word; the OT tags stay in secondary metadata."""
    for label, spec in STYLE_LANGUAGE.items():
        if font_id in spec["fonts"]:
            return label
    return None


def _texts_for(product: str) -> list[str]:
    profile = PRODUCTS[product]
    if profile.multi_name:
        return [SEVEN_NAMES]
    if product == "medallion":
        return [PHRASE]
    if profile.small_size:
        return ["ع", "نورة", "ميثة"]
    return ["نورة", "محمد", "فاطمة"]


def build_review_item(font_id: str, product: str, text: str,
                      composition: str, feature_set: str = "default",
                      font_axes: dict | None = None) -> dict | None:
    """Build one item, complete with its rendered proof and its gates."""
    profile = PRODUCTS[product]
    source = ImmutableSourceText.create(text, confirmed=True)
    record = get_registry().get(font_id)
    words = len(text.split())
    recipe = _recipe(font_id, profile, composition, stroke_delta_mm=0.35,
                     max_lines=3 if words > 2 else 1,
                     loops="left_right", dot_strategy="bridge",
                     font_axes=font_axes or {})
    try:
        candidate = build_candidate("review", source, recipe, DEFAULT_RULES)
    except Exception:
        return None
    if not candidate.geometry_wkt:
        return None

    geom = _wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    mm = measure_mm(geom)
    gate = meets_workshop_rules(mm, DEFAULT_RULES)
    validator_pass = bool(candidate.validation and candidate.validation.passed)
    golden = golden_case_influence(product)

    recipe_dict = recipe.model_dump()
    return {
        "item_id": item_id(font_id, feature_set, font_axes, product, composition, text),
        "recipe_hash": recipe_hash(recipe_dict),
        "variant_key": f"{font_id}/{feature_set}",
        # --- what the reviewer sees ---
        "product": product,
        "font_family": record.family,
        "customer_style": _customer_style_for(font_id),
        "source_text": text,
        "composition": composition,
        "width_mm": mm.get("width_mm"),
        "height_mm": mm.get("height_mm"),
        "manufacturing_pass": validator_pass and gate["passed"],
        "golden_production_pattern": [g["case_id"] for g in golden],
        "proof_path_d": geometry_to_path_d(geom, maxy),
        "proof_view": [round(maxx - minx, 2), round(maxy - miny, 2)],
        # --- secondary/technical metadata, not shown as the headline ---
        "technical": {
            "font_id": font_id,
            "feature_set": feature_set,
            "font_axes": dict(font_axes or {}),
            "recipe_id": recipe.recipe_id,
        },
        # --- hard gates a human may not open ---
        "engineering": {
            "arabic_identity_pass": candidate.identity_proof.verified,
            "manufacturing_pass": validator_pass and gate["passed"],
            "rights_pass": record.commercial_production_allowed,
            "validator_pass": validator_pass,
            "mm_gate_pass": gate["passed"],
            "min_material_width_mm": mm.get("min_material_width_mm"),
            "min_gap_mm": mm.get("min_gap_mm"),
            "counter_clearance_mm": mm.get("counter_clearance_mm"),
            "mm_failures": gate.get("failures", [])[:2],
            "basis": mm.get("basis"),
        },
        "human_review_status": "HUMAN_REVIEW_PENDING",
    }


def generate_review_pack(max_per_product: int = 4) -> list[dict]:
    """Prioritised, diverse review pack across the review products."""
    registry = get_registry()
    pack: list[dict] = []
    for product in REVIEW_PRODUCTS:
        profile = PRODUCTS[product]
        candidates: list[dict] = []
        for record in registry.list():
            for text in _texts_for(product)[:2]:
                for composition in list(dict.fromkeys(
                        profile.preferred_compositions[:1] + ("baseline_bar",))):
                    item = build_review_item(record.font_id, product, text, composition)
                    if item:
                        candidates.append(item)
        # Manufacturable first, then Golden-Case-relevant, then by material
        # margin — a reviewer's time goes to what could actually ship.
        candidates.sort(key=lambda c: (
            not c["manufacturing_pass"],
            not c["golden_production_pattern"],
            -(c["engineering"].get("min_material_width_mm") or 0),
        ))
        # Diversity: at most one item per font family per product, so the
        # pack cannot fill up with variations of one face.
        seen_fonts: set[str] = set()
        chosen: list[dict] = []
        for item in candidates:
            font_id = item["technical"]["font_id"]
            if font_id in seen_fonts:
                continue
            seen_fonts.add(font_id)
            chosen.append(item)
            if len(chosen) >= max_per_product:
                break
        pack.extend(chosen)
    return pack
