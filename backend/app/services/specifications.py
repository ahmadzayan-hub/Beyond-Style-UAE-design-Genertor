"""Jewellery specification knowledge — the copilot's "expert" layer.

Serves `app/data/jewellery_specifications.json`: trade standards, owner-stated
values and in-repo enforced limits, each carrying an evidence level. Online
verification of the trade-standard entries was attempted on 2026-09-10 and
blocked by the network egress policy; nothing here is presented as verified
online. Deterministic rules (materials.json, workshop profiles, the
manufacturing gate) always override anything in this file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SPEC_FILE = Path(__file__).resolve().parent.parent / "data" / "jewellery_specifications.json"

#: platform product id → specification sections that matter for it (ordered).
PRODUCT_SECTIONS: dict[str, list[str]] = {
    "necklace": ["product_size_envelopes", "chains", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                 "stones_and_pearls", "arabic_text_on_jewellery", "metals_fineness_and_marking"],
    "pendant": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                "stones_and_pearls", "arabic_text_on_jewellery", "metals_fineness_and_marking"],
    "multi_name": ["product_size_envelopes", "chains", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                   "arabic_text_on_jewellery"],
    "bracelet": ["product_size_envelopes", "chains", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                 "stones_and_pearls", "arabic_text_on_jewellery"],
    "ring": ["ring_sizing", "engraving", "metals_fineness_and_marking", "arabic_text_on_jewellery"],
    "cufflink": ["product_size_envelopes", "findings_and_attachments", "engraving", "sheet_thickness_and_cut_out_limits"],
    "single_letter_earring": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                              "stones_and_pearls"],
    "drop_earring": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits",
                     "stones_and_pearls"],
    "earring": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits"],
    "keychain": ["product_size_envelopes", "findings_and_attachments", "engraving"],
    "brooch": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits", "enamel"],
    "hanger": ["product_size_envelopes", "findings_and_attachments", "sheet_thickness_and_cut_out_limits"],
    "medallion": ["product_size_envelopes", "engraving", "findings_and_attachments"],
    "corporate_gift": ["product_size_envelopes", "engraving", "metals_fineness_and_marking"],
}

ENVELOPE_KEY: dict[str, str] = {
    "necklace": "name_necklace_women", "pendant": "name_necklace_women", "multi_name": "name_necklace_women",
    "bracelet": "bracelet_plate", "cufflink": "cufflink_face", "keychain": "keychain_disc", "brooch": "brooch_bar",
    "hanger": "car_mirror_hanger", "single_letter_earring": "single_letter_earring",
    "drop_earring": "single_letter_earring", "earring": "single_letter_earring",
}


@lru_cache(maxsize=1)
def load_specifications() -> dict:
    return json.loads(SPEC_FILE.read_text(encoding="utf-8"))


def research_status() -> dict:
    return dict(load_specifications()["research_status"])


def sections_for_product(product: str) -> dict[str, dict]:
    """Ordered specification sections relevant to a platform product.
    Unknown products get the always-relevant sections only."""
    spec = load_specifications()["sections"]
    keys = PRODUCT_SECTIONS.get(product, ["sheet_thickness_and_cut_out_limits", "arabic_text_on_jewellery"])
    return {k: spec[k] for k in keys if k in spec}


def size_envelope(product: str, audience: str | None = None) -> dict | None:
    envelopes = load_specifications()["sections"]["product_size_envelopes"]["envelopes_mm"]
    key = ENVELOPE_KEY.get(product)
    if product in ("necklace", "pendant", "multi_name") and audience == "kids":
        key = "name_necklace_kids"
    if product in ("pendant",) and audience == "men":
        key = "statement_pendant"
    return dict(envelopes[key]) if key in envelopes else None


def expert_brief(product: str, audience: str | None = None, material: str | None = None,
                 text_length: int | None = None) -> dict:
    """Compact, evidence-labelled guidance the copilot can quote back to a
    designer or use to propose parameters. It never overrides the
    manufacturing gate; it tells the designer what the trade expects."""
    from ..fonts.curation import golden_case_influence

    spec = load_specifications()
    sections = sections_for_product(product)
    envelope = size_envelope(product, audience)
    rules: list[dict] = []
    for key, sec in sections.items():
        for r in sec.get("rules", []):
            rules.append({"section": key, "rule": r, "evidence_level": sec["evidence_level"]})
    lessons = [{"case_id": c["case_id"], "evidence_tier": c["evidence_tier"], "lessons": c["lessons"][:3]}
               for c in golden_case_influence(product)[:4]]
    notes: list[str] = []
    if envelope and text_length:
        lo, hi = envelope["width"]
        if text_length > 8:
            notes.append(f"{text_length} characters is long for a {lo}–{hi} mm envelope: prefer a stacked/two-line layout or a bar/plate construction.")
        elif text_length <= 2:
            notes.append("One or two letters: treat as an initial — station, disc or single-letter construction.")
    if audience == "kids":
        notes.append("Kids audience: bold rounded lettering, stroke ≥ 1.0 mm, no free-hanging hairlines, short chain.")
    if material and "silver" in material:
        notes.append("925 silver: min stroke 0.6 mm / min bridge 0.8 mm per materials.json; oxidised recess is available for relief work.")
    return {
        "product": product,
        "audience": audience,
        "material": material,
        "size_envelope_mm": envelope,
        "rules": rules,
        "proven_lessons": lessons,
        "notes": notes,
        "research_status": spec["research_status"]["result"],
        "authority": "Deterministic rules (materials.json, workshop profile, manufacturing gate, text integrity) override this brief.",
    }
