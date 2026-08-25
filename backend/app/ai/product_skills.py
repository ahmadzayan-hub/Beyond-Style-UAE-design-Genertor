"""Product-specific Hermes skills: minimal, data-driven knowledge slices
loaded only when routing to a given product — progressive disclosure
keeps agent context small instead of injecting the whole design library.
"""
from __future__ import annotations

from pydantic import BaseModel


class ProductSkill(BaseModel):
    product: str
    audience: list[str]
    default_workshop_profile: str  # matches config.get_profile(product, material)
    typical_compositions: list[str]
    design_notes: str
    context_tokens_budget: int = 1500


PRODUCT_SKILLS: dict[str, ProductSkill] = {
    "necklace": ProductSkill(
        product="necklace", audience=["women", "men", "unisex"],
        default_workshop_profile="pendant", typical_compositions=["baseline_bar", "bare", "top_bar"],
        design_notes="Chain-hung; center-of-gravity and single top loop matter most.",
    ),
    "pendant": ProductSkill(
        product="pendant", audience=["women", "men", "kids", "unisex"],
        default_workshop_profile="pendant",
        typical_compositions=["bare", "plate_oval", "plate_rect", "frame_circle", "top_bar"],
        design_notes="Most flexible product; supports all composition families.",
    ),
    "earring": ProductSkill(
        product="earring", audience=["women"],
        default_workshop_profile="earring", typical_compositions=["bare", "plate_oval"],
        design_notes="Pair-weight and comfort dominate; keep the envelope small (see workshop profile).",
    ),
    "medallion": ProductSkill(
        product="medallion", audience=["men", "women", "unisex"],
        default_workshop_profile="medallion", typical_compositions=["frame_circle", "plate_oval"],
        design_notes="Radial bridge routing; thicker plate class for engraving/relief.",
    ),
    "ring": ProductSkill(
        product="ring", audience=["women", "men"],
        default_workshop_profile="pendant", typical_compositions=["frame_circle"],
        design_notes="Ring-top only in this slice; band sizing is a later product skill.",
    ),
    "bracelet": ProductSkill(
        product="bracelet", audience=["women", "men", "kids"],
        default_workshop_profile="pendant", typical_compositions=["baseline_bar", "bare"],
        design_notes="Wrist-length constraint is out of scope for this slice's geometry engine.",
    ),
    "cufflink": ProductSkill(
        product="cufflink", audience=["men"],
        default_workshop_profile="earring", typical_compositions=["plate_rect", "frame_circle"],
        design_notes="Small compact monogram-style forms; pair symmetry matters.",
    ),
    "corporate_gift": ProductSkill(
        product="corporate_gift", audience=["men", "women", "unisex"],
        default_workshop_profile="pendant", typical_compositions=["plate_rect", "frame_rect"],
        design_notes="Bulk/consistent branding; conservative compositions preferred.",
    ),
}


def load_skill(product: str) -> ProductSkill:
    """Progressive disclosure entry point — agents call this instead of
    receiving the full product catalogue up front."""
    if product not in PRODUCT_SKILLS:
        raise KeyError(f"No product skill for '{product}'")
    return PRODUCT_SKILLS[product]
