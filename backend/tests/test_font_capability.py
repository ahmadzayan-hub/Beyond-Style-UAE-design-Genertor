"""Font capability truthfulness regressions.

The rule this file defends: what we ADVERTISE must equal what we can
RENDER. A licence must be on disk, a feature must exist in the font's own
tables, and a script we cannot truly produce must say so rather than being
quietly served by a different typeface.
"""
from __future__ import annotations

import hashlib

import pytest

from app.ai.design_dna import SCRIPT_FAMILIES
from app.fonts.capabilities import (
    LICENSE_REQUIRED,
    PARAMETRIC_ONLY,
    REAL,
    generator_capability_for_dna,
    production_capability_map,
    resolve_script_request,
    script_capability_map,
)
from app.fonts.feature_safety import GOLDEN_CORPUS, check_feature, check_font_coverage
from app.fonts.glyph_variants import font_variant_capabilities, load_variants
from app.fonts.ot_discovery import discover
from app.fonts.registry import get_registry

NEW_FONTS = ["aref-ruqaa", "reem-kufi", "noto-nastaliq-urdu", "tajawal", "katibeh", "lemonada"]
BRIDGE_FONTS = {"katibeh": "thuluth", "lemonada": "diwani"}


@pytest.fixture(scope="module")
def registry():
    return get_registry()


# --- licences and integrity -------------------------------------------------

def test_every_font_ships_its_licence_file(registry):
    for record in registry.list():
        assert record.license_file, f"{record.font_id} declares no licence file"
        licence = record.path.parent / record.license_file
        assert licence.is_file(), f"{record.font_id}: {licence} missing"
        assert licence.read_text(encoding="utf-8").strip(), "licence file is empty"


def test_recorded_hash_matches_the_binary_on_disk(registry):
    for record in registry.list():
        assert record.file_sha256, f"{record.font_id} has no recorded hash"
        actual = hashlib.sha256(record.path.read_bytes()).hexdigest()
        assert record.file_sha256 == actual, f"{record.font_id} binary was swapped"
        assert record.integrity_ok


def test_new_fonts_are_registered_with_full_provenance(registry):
    for font_id in NEW_FONTS:
        record = registry.get(font_id)
        assert record.rights_status.value == "VERIFIED_OPEN_SOURCE"
        assert record.license == "SIL OFL 1.1"
        assert record.version, "no version recorded"
        assert record.upstream_repo and record.upstream_path
        assert record.retrieved_at
        assert record.script_coverage["arabic_codepoints"] > 50


def test_unknown_rights_can_never_reach_production_export():
    """The rights gate is the rule, independent of today's registry."""
    from app.schemas.jewellery_design import COMMERCIAL_OK, FontRightsStatus

    assert FontRightsStatus.UNKNOWN_RIGHTS not in COMMERCIAL_OK
    assert FontRightsStatus.INTERNAL_ONLY not in COMMERCIAL_OK
    for status in (FontRightsStatus.VERIFIED_OPEN_SOURCE,
                   FontRightsStatus.COMMERCIAL_LICENSED,
                   FontRightsStatus.CUSTOMER_OWNED):
        assert status in COMMERCIAL_OK


def test_production_export_blocked_for_unlicensed_font(registry, monkeypatch):
    from app.schemas.jewellery_design import FontRightsStatus

    record = registry.get("amiri-regular")
    clone = record.model_copy(update={"rights_status": FontRightsStatus.UNKNOWN_RIGHTS})
    assert not clone.commercial_production_allowed
    monkeypatch.setitem(registry._fonts, "amiri-regular", clone)
    with pytest.raises(PermissionError):
        registry.assert_production_allowed("amiri-regular")


# --- OT feature discovery ---------------------------------------------------

def test_every_registered_feature_exists_in_the_font_binary(registry):
    """No invented feature sets: each tag must be in the font's own tables."""
    lib = load_variants()
    real_tags = {
        r.font_id: set(discover(r.font_id, r.path).gsub_features)
        | set(discover(r.font_id, r.path).gpos_features)
        for r in registry.list()
    }
    for set_id, spec in lib["ot_feature_sets"].items():
        for font_id in spec["fonts"]:
            for tag in spec["features"]:
                assert tag in real_tags[font_id], (
                    f"feature set '{set_id}' claims {tag} which {font_id} does not have"
                )


def test_discovery_reports_real_tables_for_the_new_fonts(registry):
    ruqaa = discover("aref-ruqaa", registry.get("aref-ruqaa").path)
    assert "jalt" in ruqaa.optional_features       # justification alternates
    assert "ss01" in ruqaa.optional_features
    kufi = discover("reem-kufi", registry.get("reem-kufi").path)
    assert {"cv01", "cv02", "cv03"} <= set(kufi.optional_features)
    assert any(a["tag"] == "wght" for a in kufi.variation_axes)
    assert "arab" in kufi.scripts


def test_always_on_shaping_features_are_never_offered_as_variants():
    """Turning off init/medi/fina/rlig would break joining, not restyle it."""
    from app.fonts.ot_discovery import ALWAYS_ON, optional_letterform_features

    offered = optional_letterform_features({"init", "medi", "fina", "rlig", "ss01"})
    assert offered == ["ss01"]
    assert {"init", "medi", "fina", "rlig"} <= ALWAYS_ON


# --- feature safety ---------------------------------------------------------

def test_golden_corpus_covers_the_required_names():
    for name in ["ع", "نورة", "ميثة", "محمد", "سلطان", "فاطمة", "حامد", "خالد", "مهرة"]:
        assert name in GOLDEN_CORPUS
    assert any(" " in t for t in GOLDEN_CORPUS), "no phrase in corpus"
    assert any(len(t.split()) >= 5 for t in GOLDEN_CORPUS), "no multi-name case"


@pytest.mark.parametrize("font_id", NEW_FONTS)
def test_new_font_shapes_the_whole_corpus(font_id):
    verdict = check_font_coverage(font_id)
    assert verdict["shaping_pass"], verdict["failures"]


def test_every_production_feature_passed_the_shaping_regression(registry):
    lib = load_variants()
    for set_id, spec in lib["ot_feature_sets"].items():
        if not spec.get("safe_for_production", True):
            continue
        for font_id in spec["fonts"]:
            for tag in spec["features"]:
                verdict = check_feature(font_id, tag, corpus=GOLDEN_CORPUS[:4])
                assert verdict["safe_for_production"], (
                    f"{set_id}/{font_id}/{tag} regressed: {verdict['failures']}"
                )


def test_safety_probe_detects_dropped_characters():
    """Negative control — the gate must be able to fail, not just pass."""
    from app.fonts.feature_safety import _probe

    probe = _probe("نورة", "amiri-regular", None)
    assert probe.recovered_text == "نورة"
    assert probe.covered == set(range(4))
    # A codepoint the font cannot render shows up as .notdef.
    missing = _probe("字", "amiri-regular", None)
    assert missing.notdef_count == 1


def test_shaping_never_mutates_the_source_text():
    from app.engines.arabic_engine import shape_text

    for text in GOLDEN_CORPUS:
        before = text
        for font_id in ["amiri-regular"] + NEW_FONTS:
            shape_text(text, font_id)
        assert text == before


# --- glyph variant library --------------------------------------------------

def test_glyph_variants_expose_provenance_and_safety():
    for font_id in ["aref-ruqaa", "reem-kufi"]:
        variants = font_variant_capabilities(font_id)
        assert variants, f"{font_id} exposes no variant sets"
        for v in variants:
            assert v["provenance"] in (
                "DISCOVERED_FROM_FONT_TABLES", "CURATED_VERIFIED_AGAINST_FONT_TABLES"
            )
            assert v["safe_for_production"] is True
            assert v["feature_tags"]
            assert v["label"]


def test_reem_kufi_character_variants_are_selectable():
    tags = {t for v in font_variant_capabilities("reem-kufi") for t in v["feature_tags"]}
    assert {"cv01", "cv02", "cv03"} <= tags


def test_aref_ruqaa_alternates_are_selectable():
    tags = {t for v in font_variant_capabilities("aref-ruqaa") for t in v["feature_tags"]}
    assert "jalt" in tags and "ss01" in tags


# --- capability truthfulness ------------------------------------------------

def test_capability_map_covers_every_classification_value():
    caps = script_capability_map()
    assert set(caps) == set(SCRIPT_FAMILIES), "a classification value has no capability verdict"


def test_newly_real_scripts_are_backed_by_a_real_font():
    caps = script_capability_map()
    for family, font_id in [("ruqaa", "aref-ruqaa"), ("nastaliq", "noto-nastaliq-urdu"),
                            ("kufi", "reem-kufi"), ("geometric_kufi", "reem-kufi")]:
        assert caps[family]["status"] == REAL, family
        assert font_id in caps[family]["fonts"]


def test_true_thuluth_and_diwani_stay_license_required():
    caps = script_capability_map()
    # Diwani: no rights-cleared source yet → licence required, bridge fonts only.
    for family in ("diwani", "diwani_jali"):
        assert caps[family]["status"] == LICENSE_REQUIRED, family
        assert caps[family]["fonts"] == [], "a bridge font must never count as the true script"
        assert caps[family]["influenced_available"] is True
    # Thuluth: TRUE via the OFL AMoshref Thulth (vendored 2026-09-10); the
    # bridge font (Katibeh) still never counts as the true script.
    for family in ("thuluth", "thuluth_jali"):
        assert caps[family]["status"] == REAL, family
        assert caps[family]["fonts"] == ["amoshref-thulth"]

    tokens = production_capability_map()
    assert tokens["THULUTH"] == REAL
    assert tokens["DIWANI"] == LICENSE_REQUIRED
    assert tokens["THULUTH_INFLUENCED"] == REAL
    assert tokens["DIWANI_INFLUENCED"] == REAL


def test_bridge_fonts_are_never_labelled_as_the_classical_script(registry):
    for font_id, influence in BRIDGE_FONTS.items():
        record = registry.get(font_id)
        assert record.script_family == "naskh", "bridge fonts are Naskh-based"
        assert record.style_influence == influence
        assert record.production_capability == f"{influence.upper()}_INFLUENCED"
        assert "NOT true" in record.notes


def test_unavailable_true_style_returns_a_labelled_alternative():
    result = resolve_script_request("diwani")
    assert result["outcome"] == "STYLE_NOT_AVAILABLE"
    assert result["font_id"] is None, "must not silently pick a font"
    assert result["recommended_font_id"] == "lemonada"
    assert result["recommended_capability"] == "DIWANI_INFLUENCED"
    assert "do not hold a licensed true" in result["message"]


def test_diwani_request_is_never_silently_served_by_amiri():
    for family in ("diwani", "diwani_jali"):
        result = resolve_script_request(family)
        assert result["font_id"] is None
        assert "amiri-regular" not in str(result.get("recommended_font_id"))
    # Thuluth resolves to its rights-cleared true source, never to a Naskh face.
    for family in ("thuluth", "thuluth_jali"):
        assert resolve_script_request(family)["font_id"] == "amoshref-thulth"


def test_available_style_resolves_to_its_real_font():
    result = resolve_script_request("ruqaa")
    assert result["outcome"] == "AVAILABLE"
    assert result["font_id"] == "aref-ruqaa"


def test_parametric_only_scripts_ask_for_a_composition_not_a_font():
    for family in ("square_kufi", "monogram"):
        entry = script_capability_map()[family]
        assert entry["status"] == PARAMETRIC_ONLY
        assert resolve_script_request(family)["outcome"] == "PARAMETRIC_COMPOSITION_REQUIRED"


def test_dna_classification_is_preserved_while_generation_is_relabelled():
    """DesignDNA may honestly call a reference Diwani; the generator must
    then say what it actually built instead of claiming Diwani."""
    decision = generator_capability_for_dna("diwani")
    assert decision["must_not_claim"] == "diwani"
    assert decision["labelled_as"] == "DIWANI_INFLUENCED"
    assert decision["human_design_required"] is False

    real = generator_capability_for_dna("nastaliq")
    assert real["labelled_as"] == "nastaliq"
    assert real["font_id"] == "noto-nastaliq-urdu"


def test_registry_accepts_a_future_licensed_font_without_code_changes(registry):
    """A licensed true-Diwani font must flip the capability by data alone."""
    from app.fonts import capabilities as caps_mod
    from app.schemas.jewellery_design import FontRightsStatus

    future = registry.get("lemonada").model_copy(update={
        "font_id": "future-diwani",
        "production_capability": "DIWANI",
        "script_family": "diwani",
        "style_influence": None,
        "rights_status": FontRightsStatus.COMMERCIAL_LICENSED,
    })
    registry._fonts["future-diwani"] = future
    caps_mod.script_capability_map.cache_clear()
    try:
        caps_mod.SCRIPT_REQUIREMENTS["diwani"]["true"] = ["DIWANI"]
        entry = caps_mod.script_capability_map()["diwani"]
        assert entry["status"] == REAL
        assert "future-diwani" in entry["fonts"]
    finally:
        caps_mod.SCRIPT_REQUIREMENTS["diwani"]["true"] = []
        registry._fonts.pop("future-diwani")
        caps_mod.script_capability_map.cache_clear()
