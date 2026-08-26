"""Glyph Variant Library — deterministic, data-driven letterform variety.

Three variant axes, all reusable assets from `data/glyph_variants.json`:
- OT feature sets: real OpenType stylistic alternates in the licensed
  fonts (shaped by HarfBuzz, so positional init/medial/final/isolated
  behaviour and contextual joining stay correct).
- Dot styles: parametric restyling of detached dot components (identity
  gate still requires every source codepoint covered — dots move style,
  never disappear as *text*).
- Swashes: parametric decorative flourish geometry appended to the
  composition (pure ornament — never replaces letter geometry).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

VARIANTS_FILE = Path(__file__).resolve().parent.parent / "data" / "glyph_variants.json"


@lru_cache(maxsize=1)
def load_variants() -> dict:
    return json.loads(VARIANTS_FILE.read_text(encoding="utf-8"))


def feature_sets_for_font(font_id: str, production_only: bool = True) -> list[str]:
    """Named feature sets applicable to a font. `production_only` keeps out
    anything that did not survive the shaping regression."""
    lib = load_variants()
    return [
        name
        for name, spec in lib["ot_feature_sets"].items()
        if font_id in spec["fonts"]
        and (not production_only or spec.get("safe_for_production", True))
    ]


def font_variant_capabilities(font_id: str) -> list[dict]:
    """Full per-font variant descriptors for the Copilot/admin surfaces.

    Every entry traces back to a real table in the font binary: `provenance`
    says whether it was discovered by inspection or hand-curated and then
    verified, and `safe_for_production` reflects the corpus regression."""
    lib = load_variants()
    out = []
    for name, spec in lib["ot_feature_sets"].items():
        if font_id not in spec["fonts"]:
            continue
        out.append({
            "set_id": name,
            "font_id": font_id,
            "features": dict(spec["features"]),
            "feature_tags": sorted(spec["features"]),
            "label": spec["label"],
            "provenance": spec.get("provenance", "CURATED_VERIFIED_AGAINST_FONT_TABLES"),
            "safe_for_production": spec.get("safe_for_production", True),
            "affected_scripts": spec.get("affected_scripts", []),
        })
    return sorted(out, key=lambda e: e["set_id"])


def resolve_features(feature_set: str, font_id: str) -> dict:
    """Returns the HarfBuzz feature dict for a named set, validating
    applicability to the font. Unknown/inapplicable sets raise."""
    lib = load_variants()
    if feature_set not in lib["ot_feature_sets"]:
        raise KeyError(f"Unknown OT feature set: {feature_set}")
    spec = lib["ot_feature_sets"][feature_set]
    if font_id not in spec["fonts"]:
        raise ValueError(f"Feature set {feature_set} not applicable to {font_id}")
    return dict(spec["features"])


def dot_style_spec(name: str) -> dict:
    lib = load_variants()
    if name not in lib["dot_styles"]:
        raise KeyError(f"Unknown dot style: {name}")
    return lib["dot_styles"][name]


def swash_spec(name: str) -> dict:
    lib = load_variants()
    if name not in lib["swashes"]:
        raise KeyError(f"Unknown swash: {name}")
    return lib["swashes"][name]


def variant_axes() -> dict:
    """Everything the generator/Copilot may offer, per axis."""
    lib = load_variants()
    return {
        "ot_feature_sets": {k: v["label"] for k, v in lib["ot_feature_sets"].items()},
        "dot_styles": {k: v["label"] for k, v in lib["dot_styles"].items()},
        "swashes": {k: v["label"] for k, v in lib["swashes"].items()},
    }
