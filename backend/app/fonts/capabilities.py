"""Script capability truth — what we can actually render, per script family.

`SCRIPT_FAMILIES` in app/ai/design_dna.py is a CLASSIFICATION vocabulary:
Reference Intelligence must stay free to label a customer's photo as
Diwani or Thuluth, because that is what the photo is. This module is the
separate, narrower question of what the GENERATOR can produce, and it is
derived from the installed registry rather than declared by hand.

Four distinct concepts, never conflated:
  script_family          — the script system a font genuinely is.
  font_family            — the typeface.
  style_influence        — a classical style a font merely leans toward.
  production_capability  — what may be promised to a customer.

A bridge font (Katibeh, Lemonada) has script_family=naskh with a
style_influence, so it yields THULUTH_INFLUENCED / DIWANI_INFLUENCED and
can never satisfy a request for the true classical script.
"""
from __future__ import annotations

from functools import lru_cache

from ..ai.design_dna import SCRIPT_FAMILIES
from .registry import get_registry

REAL = "REAL"
#: The TRUE classical script is not licensed. An influenced alternative may
#: still exist — that is reported separately and never upgrades this status,
#: because a Naskh-based bridge face is not the classical script.
LICENSE_REQUIRED = "LICENSE_REQUIRED"
PARAMETRIC_ONLY = "PARAMETRIC_ONLY"
NOT_APPLICABLE = "NOT_APPLICABLE"

#: Which production_capability truly satisfies each classification, and
#: which merely approximates it. A family absent from `true` with entries in
#: `influenced` is honestly LICENSE_REQUIRED until a real font is licensed.
SCRIPT_REQUIREMENTS: dict[str, dict] = {
    "naskh":          {"true": ["NASKH"], "influenced": []},
    "ruqaa":          {"true": ["RUQAA"], "influenced": []},
    "kufi":           {"true": ["KUFI"], "influenced": ["MODERN_ARABIC"]},
    "geometric_kufi": {"true": ["KUFI"], "influenced": []},
    "nastaliq":       {"true": ["NASTALIQ"], "influenced": []},
    "farsi":          {"true": [], "influenced": ["NASTALIQ"],
                       "note": "Farsi/Ta'liq is served only by the Urdu Nastaliq face; not a true Farsi cut."},
    "modern_arabic":  {"true": ["MODERN_ARABIC"], "influenced": []},
    "minimal":        {"true": ["MODERN_ARABIC"], "influenced": []},
    "thuluth":        {"true": ["THULUTH"], "influenced": ["THULUTH_INFLUENCED"]},
    "thuluth_jali":   {"true": ["THULUTH"], "influenced": ["THULUTH_INFLUENCED"]},
    "diwani":         {"true": ["DIWANI"], "influenced": ["DIWANI_INFLUENCED"]},
    "diwani_jali":    {"true": ["DIWANI"], "influenced": ["DIWANI_INFLUENCED"]},
    "square_kufi":    {"true": [], "influenced": [], "parametric": True,
                       "note": "Square Kufi is a geometric construction, not a typeface — a parametric composer slice, not a font purchase."},
    "monogram":       {"true": [], "influenced": [], "parametric": True,
                       "note": "Monogram is a composition mode built from any script's glyphs."},
    "latin_script":   {"true": ["NASKH", "MODERN_ARABIC"], "influenced": [],
                       "note": "Served by the Latin coverage of the installed Arabic families."},
    "unknown":        {"true": [], "influenced": [], "not_applicable": True},
}


def _fonts_by_capability() -> dict[str, list]:
    out: dict[str, list] = {}
    for record in get_registry().list():
        if not record.commercial_production_allowed:
            continue  # rights gate: never offer a font we cannot ship
        out.setdefault(record.production_capability, []).append(record)
    return out


@lru_cache(maxsize=1)
def script_capability_map() -> dict[str, dict]:
    """Per script family: what we can really do, and with which fonts."""
    by_cap = _fonts_by_capability()
    result: dict[str, dict] = {}
    for family in SCRIPT_FAMILIES:
        spec = SCRIPT_REQUIREMENTS.get(family, {"true": [], "influenced": []})
        true_fonts = [f for cap in spec.get("true", []) for f in by_cap.get(cap, [])]
        infl_fonts = [f for cap in spec.get("influenced", []) for f in by_cap.get(cap, [])]
        if spec.get("not_applicable"):
            status = NOT_APPLICABLE
        elif true_fonts:
            status = REAL
        elif spec.get("parametric"):
            status = PARAMETRIC_ONLY
        else:
            status = LICENSE_REQUIRED
        result[family] = {
            "script_family": family,
            "status": status,
            "fonts": [f.font_id for f in true_fonts],
            "influenced_fonts": [
                {"font_id": f.font_id, "family": f.family,
                 "production_capability": f.production_capability}
                for f in infl_fonts
            ],
            "influenced_available": bool(infl_fonts),
            "influenced_capability": infl_fonts[0].production_capability if infl_fonts else None,
            "note": spec.get("note", ""),
        }
    return result


def resolve_script_request(script_family: str) -> dict:
    """What to do when a customer (or a DNA classification) asks for a
    script. Never silently substitutes: an unavailable true style returns
    STYLE_NOT_AVAILABLE plus the closest licensed alternative."""
    entry = script_capability_map().get(script_family)
    if entry is None:
        return {
            "requested": script_family,
            "outcome": "UNKNOWN_SCRIPT_FAMILY",
            "font_id": None,
            "alternatives": [],
            "message": f"'{script_family}' is not a recognised script family.",
        }
    if entry["status"] == REAL:
        return {
            "requested": script_family,
            "outcome": "AVAILABLE",
            "font_id": entry["fonts"][0],
            "fonts": entry["fonts"],
            "alternatives": [],
            "message": "",
        }
    if entry["status"] == LICENSE_REQUIRED and entry["influenced_fonts"]:
        alt = entry["influenced_fonts"][0]
        return {
            "requested": script_family,
            "outcome": "STYLE_NOT_AVAILABLE",
            "font_id": None,
            "alternatives": entry["influenced_fonts"],
            "recommended_font_id": alt["font_id"],
            "recommended_capability": alt["production_capability"],
            "message": (
                f"We do not hold a licensed true {script_family.replace('_', ' ').title()} "
                f"font. The closest we can produce is {alt['font_id']} "
                f"({alt['production_capability'].replace('_', ' ').lower()}), or a custom "
                "parametric composition designed by hand."
            ),
        }
    if entry["status"] == PARAMETRIC_ONLY:
        return {
            "requested": script_family,
            "outcome": "PARAMETRIC_COMPOSITION_REQUIRED",
            "font_id": None,
            "alternatives": [],
            "message": entry["note"],
        }
    return {
        "requested": script_family,
        "outcome": "STYLE_NOT_AVAILABLE",
        "font_id": None,
        "alternatives": [],
        "message": (
            f"No licensed font can produce {script_family}. "
            "HUMAN_DESIGN_REQUIRED: a designer must compose this by hand."
        ),
    }


def generator_capability_for_dna(dna_script_family: str) -> dict:
    """Bridge from a DesignDNA classification to what the generator may do.

    The DNA keeps its honest classification of the reference image; this
    decides, separately, what we build — and labels it explicitly so we
    never claim the chosen font is the classical script that was asked for.
    """
    resolved = resolve_script_request(dna_script_family)
    if resolved["outcome"] == "AVAILABLE":
        return {**resolved, "labelled_as": dna_script_family, "human_design_required": False}
    if resolved["outcome"] == "STYLE_NOT_AVAILABLE" and resolved.get("recommended_font_id"):
        return {
            **resolved,
            "labelled_as": resolved["recommended_capability"],
            "human_design_required": False,
            "must_not_claim": dna_script_family,
        }
    return {**resolved, "labelled_as": "HUMAN_DESIGN_REQUIRED", "human_design_required": True}


#: Capability tokens the customer-facing picker offers. Derived from the
#: registry: a token is REAL only while a rights-cleared font backs it.
def production_capability_map() -> dict[str, str]:
    """{capability_token: REAL | LICENSE_REQUIRED} for the style picker.

    Both halves of a bridge pair appear: THULUTH_INFLUENCED is REAL because
    Katibeh really renders it, while THULUTH stays LICENSE_REQUIRED because
    no licensed true Thuluth exists. The picker must show both truthfully.
    """
    available = set(_fonts_by_capability())
    tokens = {
        "NASKH", "RUQAA", "KUFI", "NASTALIQ", "MODERN_ARABIC",
        "THULUTH_INFLUENCED", "DIWANI_INFLUENCED",
        # True classical cuts become REAL the moment a licensed font with
        # that production_capability is onboarded (scripts/add_font.py).
        "THULUTH", "DIWANI",
    }
    out = {t: (REAL if t in available else LICENSE_REQUIRED) for t in sorted(tokens)}
    out["THULUTH_JALI"] = out["THULUTH"]
    out["DIWANI_JALI"] = out["DIWANI"]
    return out


@lru_cache(maxsize=1)
def _script_recipe_library() -> dict:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "script_recipes.json"
    return json.loads(path.read_text(encoding="utf-8"))


def recipes_for_script(script_family: str) -> list[dict]:
    """On-demand recipes for an explicitly requested script family.

    Deliberately separate from the default candidate pool: adding these to
    the ranked-10 Golden Path would change its immutable golden fixture, so
    they are offered only when the customer asks for that script."""
    resolved = resolve_script_request(script_family)
    font_ids = set(resolved.get("fonts") or ([resolved["font_id"]] if resolved.get("font_id") else []))
    if not font_ids and resolved.get("recommended_font_id"):
        font_ids = {resolved["recommended_font_id"]}
    return [
        r for r in _script_recipe_library()["recipes"] if r["font_id"] in font_ids
    ]
