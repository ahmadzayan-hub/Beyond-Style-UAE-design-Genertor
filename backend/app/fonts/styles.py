"""Arabic Calligraphy Style Catalogue — the customer-facing style list with
availability derived from the rights-cleared registry, never declared.

Statuses:
  AVAILABLE            a commercial-OK font with the true capability exists
  INFLUENCED_ONLY      only a bridge face exists (labelled "inspired", never
                       claimed as the classical script)
  UPLOAD_REQUIRED      no legal source in the registry — "Install / Upload
                       Licensed Source"
  PARAMETRIC_NOT_BUILT a geometric construction (square Kufi, Bina'i) that is
                       a composer, not a font; not built yet — never faked
  ENGINE               a composition mode of the Vector Composition Engine,
                       not a typeface
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .capabilities import _fonts_by_capability
from .registry import get_registry

STYLE_CATALOGUE: list[dict] = [
    # id, en, ar, category, true capability tokens (any), influenced tokens, jewellery tags
    {"id": "thuluth", "en": "Thuluth", "ar": "ثلث", "category": "classical", "true": ["THULUTH"],
     "influenced": ["THULUTH_INFLUENCED"], "tags": ["classic", "luxury", "statement", "pendant", "brooch"]},
    {"id": "jali_thuluth", "en": "Jali Thuluth", "ar": "ثلث جلي", "category": "classical", "true": ["THULUTH"],
     "influenced": ["THULUTH_INFLUENCED"], "tags": ["classic", "luxury", "statement", "pendant"]},
    {"id": "diwani", "en": "Diwani", "ar": "ديواني", "category": "classical", "true": ["DIWANI"],
     "influenced": ["DIWANI_INFLUENCED"], "tags": ["classic", "luxury", "pendant", "necklace"]},
    {"id": "jali_diwani", "en": "Jali Diwani", "ar": "ديواني جلي", "category": "classical", "true": ["DIWANI"],
     "influenced": ["DIWANI_INFLUENCED"], "tags": ["classic", "luxury", "statement"]},
    {"id": "ruqaa", "en": "Ruq'ah", "ar": "رقعة", "category": "classical", "true": ["RUQAA"], "influenced": [],
     "tags": ["classic", "pendant", "necklace", "bracelet", "keychain", "manufacturing_safe"]},
    {"id": "naskh", "en": "Naskh", "ar": "نسخ", "category": "classical", "true": ["NASKH"], "influenced": [],
     "tags": ["classic", "pendant", "necklace", "ring", "bracelet", "manufacturing_safe"]},
    {"id": "kufi_traditional", "en": "Traditional Kufi", "ar": "كوفي تقليدي", "category": "classical",
     "true": ["KUFI"], "influenced": [], "tags": ["classic", "geometric", "pendant", "cufflinks", "manufacturing_safe"]},
    {"id": "kufi_modern", "en": "Modern Kufi", "ar": "كوفي حديث", "category": "modern", "true": ["MODERN_KUFI"],
     "influenced": ["KUFI"], "tags": ["modern", "minimal", "geometric", "pendant", "ring", "cufflinks", "manufacturing_safe"]},
    {"id": "kufi_square", "en": "Square Kufi", "ar": "كوفي مربع", "category": "geometric", "true": [],
     "influenced": [], "parametric": True, "tags": ["geometric", "modern", "pendant", "cufflinks"]},
    {"id": "binai", "en": "Bina'i (brick Kufi)", "ar": "بنائي", "category": "geometric", "true": [],
     "influenced": [], "parametric": True, "tags": ["geometric", "statement"]},
    {"id": "nastaliq_persian", "en": "Persian Nastaliq", "ar": "نستعليق فارسي", "category": "classical",
     "true": ["NASTALIQ"], "influenced": [], "tags": ["classic", "luxury", "pendant", "brooch"]},
    {"id": "nastaliq_levantine", "en": "Levantine Nastaliq", "ar": "نستعليق شامي", "category": "classical",
     "true": ["NASTALIQ_LEVANTINE"], "influenced": ["NASTALIQ"], "tags": ["classic", "pendant"]},
    {"id": "fatimid_foliated", "en": "Fatimid foliated Kufi", "ar": "كوفي فاطمي مورّق", "category": "historical",
     "true": ["FATIMID_FOLIATED"], "influenced": [], "tags": ["classic", "statement", "brooch"]},
    {"id": "historical", "en": "Historical Arabic calligraphy", "ar": "خط عربي تاريخي", "category": "historical",
     "true": ["HISTORICAL"], "influenced": [], "tags": ["classic", "statement"]},
    {"id": "decorative", "en": "Decorative Arabic", "ar": "عربي زخرفي", "category": "decorative",
     "true": ["DISPLAY"], "influenced": [], "tags": ["statement", "pendant", "brooch", "keychain"]},
    {"id": "calligraffiti", "en": "Calligraffiti", "ar": "كاليجرافيتي", "category": "experimental",
     "true": ["CALLIGRAFFITI"], "influenced": ["DISPLAY"], "tags": ["modern", "statement"]},
    {"id": "handwriting_soft", "en": "Soft handwriting", "ar": "خط يدوي ناعم", "category": "modern",
     "true": ["RUQAA"], "influenced": [], "fonts_hint": ["rakkas", "aref-ruqaa-ink"],
     "tags": ["modern", "pendant", "bracelet", "gift"]},
    {"id": "bold", "en": "Bold Arabic", "ar": "عربي جريء", "category": "modern", "true": ["BOLD"],
     "influenced": ["DISPLAY", "MODERN_KUFI"], "tags": ["modern", "statement", "pendant", "ring", "cufflinks", "manufacturing_safe"]},
    {"id": "geometric", "en": "Geometric Arabic", "ar": "عربي هندسي", "category": "geometric",
     "true": ["GEOMETRIC_KUFI"], "influenced": ["MODERN_KUFI"], "tags": ["geometric", "minimal", "modern", "cufflinks", "ring", "manufacturing_safe"]},
    {"id": "retro", "en": "Retro Arabic", "ar": "عربي ريترو", "category": "decorative", "true": ["DISPLAY"],
     "influenced": [], "fonts_hint": ["jomhuria", "lalezar"], "tags": ["statement", "pendant", "keychain"]},
    {"id": "sculpture", "en": "Sculpture-style Arabic", "ar": "عربي نحتي", "category": "decorative",
     "true": ["DISPLAY"], "influenced": ["BOLD"], "fonts_hint": ["blaka", "jomhuria"], "tags": ["statement", "luxury", "pendant", "brooch"]},
    {"id": "logo", "en": "Logo-style Arabic", "ar": "عربي بأسلوب الشعارات", "category": "modern", "true": ["LOGO"],
     "influenced": ["MODERN_ARABIC"], "tags": ["modern", "minimal", "cufflinks", "keychain", "pendant"]},
    {"id": "minimal_modern", "en": "Minimal modern Arabic", "ar": "عربي حديث بسيط", "category": "modern",
     "true": ["MODERN_ARABIC"], "influenced": [], "tags": ["modern", "minimal", "ring", "bracelet", "earrings", "manufacturing_safe"]},
    {"id": "experimental_composition", "en": "Experimental composition", "ar": "تكوين تجريبي", "category": "experimental",
     "true": [], "influenced": [], "engine": True, "tags": ["statement", "modern", "pendant"]},
]

PRODUCT_FILTERS = ["pendant", "ring", "earrings", "bracelet", "brooch", "keychain", "cufflinks", "necklace"]
MOOD_FILTERS = ["classic", "modern", "luxury", "geometric", "minimal", "statement", "manufacturing_safe"]


def _font_card(record) -> dict:
    return {
        "font_id": record.font_id, "family": record.family, "script_family": record.script_family,
        "style_influence": record.style_influence, "production_capability": record.production_capability,
        "license": record.license, "rights_status": record.rights_status.value,
        "source_url": record.source_url, "style_tags": record.style_tags,
    }


def style_status(entry: dict) -> tuple[str, list, list]:
    by_cap = _fonts_by_capability()
    true_fonts = [f for cap in entry.get("true", []) for f in by_cap.get(cap, [])]
    infl_fonts = [f for cap in entry.get("influenced", []) for f in by_cap.get(cap, [])]
    hint = entry.get("fonts_hint")
    if hint:
        true_fonts = [f for f in true_fonts if f.font_id in hint] or true_fonts
    if entry.get("engine"):
        return "ENGINE", [], []
    if true_fonts:
        return "AVAILABLE", true_fonts, infl_fonts
    if entry.get("parametric"):
        return "PARAMETRIC_NOT_BUILT", [], infl_fonts
    if infl_fonts:
        return "INFLUENCED_ONLY", [], infl_fonts
    return "UPLOAD_REQUIRED", [], []


ACTION_LABEL = {
    "AVAILABLE": ("Available", "متاح"),
    "INFLUENCED_ONLY": ("Inspired style only — install / upload the licensed source for the true script",
                        "أسلوب مستوحى فقط — ثبّت/ارفع المصدر المرخّص للخط الأصلي"),
    "UPLOAD_REQUIRED": ("Install / Upload Licensed Source", "تثبيت / رفع مصدر مرخّص"),
    "PARAMETRIC_NOT_BUILT": ("Geometric composer not built yet", "لم يُبنَ المكوّن الهندسي بعد"),
    "ENGINE": ("Composition engine mode", "وضع محرك التكوين"),
}


def style_catalogue(manufacturing_scores: dict[str, float] | None = None) -> list[dict]:
    """Style cards with truthful availability. `manufacturing_scores` maps
    font_id → pass rate from the recipe sweep (0..1)."""
    scores = manufacturing_scores or {}
    out = []
    for entry in STYLE_CATALOGUE:
        status, fonts, infl = style_status(entry)
        font_scores = [scores.get(f.font_id) for f in fonts if scores.get(f.font_id) is not None]
        en, ar = ACTION_LABEL[status]
        out.append({
            "id": entry["id"], "name_en": entry["en"], "name_ar": entry["ar"],
            "category": entry["category"], "tags": entry["tags"],
            "status": status, "action_en": en, "action_ar": ar,
            "fonts": [_font_card(f) for f in fonts],
            "influenced_fonts": [_font_card(f) for f in infl],
            "source": "registry" if fonts or infl else None,
            "license": sorted({f.license for f in fonts + infl}) if (fonts or infl) else [],
            "jewelry_suitability": [t for t in entry["tags"] if t in PRODUCT_FILTERS],
            "manufacturing_score": round(max(font_scores), 2) if font_scores else None,
            "manufacturing_safe": "manufacturing_safe" in entry["tags"],
        })
    return out


def registry_view() -> list[dict]:
    """Font & Glyph Registry rows (section 4G of the spec)."""
    rows = []
    for r in get_registry().list():
        rows.append({
            "font_id": r.font_id, "name": r.family, "script_family": r.script_family,
            "style_family": r.style_family, "style_influence": r.style_influence,
            "production_capability": r.production_capability, "source": r.source_url,
            "upstream_distribution": r.upstream_distribution, "version": r.version,
            "license": r.license, "license_file": r.license_file,
            "rights_status": r.rights_status.value,
            "commercial_use": r.commercial_production_allowed,
            "web_use": r.redistribution_permitted,
            "server_use": True,
            "production_use": r.commercial_production_allowed,
            "hash_sha256": r.file_sha256, "integrity_ok": r.integrity_ok,
            "imported_date": r.retrieved_at, "owner_source": r.upstream_repo or r.source_url,
            "glyph_count": _glyph_count(r), "arabic_codepoints": (r.script_coverage or {}).get("arabic_codepoints"),
            "shaping_engine": "harfbuzz", "shaping_status": "VERIFIED" if r.integrity_ok else "UNVERIFIED",
            "style_tags": r.style_tags, "diversity_index": r.diversity_index,
        })
    return rows


def _glyph_count(record) -> int | None:
    try:
        from fontTools.ttLib import TTFont

        return len(TTFont(str(record.path), lazy=True).getGlyphOrder())
    except Exception:  # noqa: BLE001
        return None
