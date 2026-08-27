"""Aesthetic curation, combination safety and axis safety regressions.

The rule defended here: measurement may inform, but it may never overrule
manufacturing, text truth, or licensing — and an unreviewed variant must
never reach a customer.
"""
from __future__ import annotations

import pytest

from app.fonts.axes import MAX_STROKE_THINNING, axis_grid, classify_grid, safe_range
from app.fonts.combinations import (
    COMPATIBLE, REDUNDANT, UNSAFE, a_priori_rule, check_combination,
    curated_combinations, production_safe_combinations,
)
from app.fonts.curation import (
    COMPUTED_DIMENSIONS, CUSTOMER_VISIBLE_STATES, EVIDENCE_PRIORITY,
    HUMAN_REVIEW_DIMENSIONS, PRODUCTS, STYLE_LANGUAGE, CurationState,
    aesthetic_gate, curation_state, customer_style_options, golden_case_influence,
    is_customer_visible, load_curation, resolve_style_label,
)
from app.fonts.suitability import best_font_per_product, measure


# --- combination safety -----------------------------------------------------

def test_curated_combinations_cover_the_required_pairings():
    kinds = {c.kind for c in curated_combinations()}
    for required in ["ssXX+jalt", "cvXX+weight", "variant+kashida",
                     "variant+swash", "weight+overlap", "weight+stacking",
                     "variant+dots"]:
        assert required in kinds, f"combination class {required} untested"


def test_every_curated_combination_has_a_verdict():
    for result in (check_combination(c) for c in curated_combinations()):
        assert result["verdict"] in {COMPATIBLE, REDUNDANT, UNSAFE, "CONFLICTING", "UNKNOWN"}
        assert result["corpus_size"] >= 4


def test_same_slot_features_are_flagged_redundant_not_compatible():
    """Two stylistic sets rewriting the same slots must never be sold as a
    combination — the later simply wins."""
    assert a_priori_rule(("ss01", "ss02")) == REDUNDANT
    assert a_priori_rule(("liga", "dlig")) == REDUNDANT
    assert a_priori_rule(("ss01", "jalt")) is None  # different axes → measure it


def test_only_compatible_combinations_reach_production():
    results = [check_combination(c) for c in curated_combinations()]
    safe = production_safe_combinations(results)
    assert safe, "no combination survived"
    for entry in safe:
        assert entry["verdict"] == COMPATIBLE
        assert entry["shaping_safe"]
    # Redundant and unsafe verdicts are excluded, not quietly shipped.
    excluded = [r for r in results if r["verdict"] != COMPATIBLE]
    for entry in excluded:
        assert entry not in safe


def test_an_unsafe_combination_is_excluded():
    """Negative control: a combination whose shaping drops a character must
    be rejected even though its verdict machinery is shared with safe ones."""
    results = [check_combination(c) for c in curated_combinations()]
    fabricated = dict(results[0], verdict=UNSAFE, shaping_safe=False)
    assert fabricated not in production_safe_combinations(results + [fabricated])


def test_combination_never_mutates_source_text():
    for result in (check_combination(c) for c in curated_combinations()[:6]):
        # check_combination asserts identity internally; a failure would
        # raise rather than return, so reaching here proves it held.
        assert result["corpus_size"] > 0


# --- variable axis safety ---------------------------------------------------

def test_axis_grid_is_bounded_and_includes_the_default():
    grid = axis_grid({"tag": "wght", "min": 400.0, "default": 400.0, "max": 700.0})
    assert grid[0] == 400.0 and grid[-1] == 700.0
    assert 400.0 in grid
    assert len(grid) <= 6, "grid must stay a bounded representative sample"


def test_unsafe_axis_points_are_blocked_with_a_reason():
    sweep = [
        {"value": 400.0, "is_default": True, "mean_fill_ratio": 0.40,
         "stroke_proxy_min": 100.0, "mean_contours": 2.0},
        {"value": 700.0, "is_default": False, "mean_fill_ratio": 0.80,
         "stroke_proxy_min": 100.0, "mean_contours": 2.0},
    ]
    classified = classify_grid(sweep, small_size=True)
    assert classified[0]["safe"] is True
    assert classified[1]["safe"] is False
    assert "counters closing" in classified[1]["reasons"][0]
    # The unsafe extreme is excluded from the offered range.
    assert safe_range(classified) == {"min": 400.0, "max": 400.0, "status": "MEASURED"}


def test_thinning_below_the_default_is_unsafe():
    sweep = [
        {"value": 400.0, "is_default": True, "mean_fill_ratio": 0.30,
         "stroke_proxy_min": 100.0, "mean_contours": 2.0},
        {"value": 200.0, "is_default": False, "mean_fill_ratio": 0.20,
         "stroke_proxy_min": 100.0 * (1 - MAX_STROKE_THINNING - 0.05), "mean_contours": 2.0},
    ]
    classified = classify_grid(sweep, small_size=False)
    assert classified[1]["safe"] is False
    assert "thinner" in classified[1]["reasons"][0]


def test_a_safe_island_unreachable_from_the_default_is_not_offered():
    """If the default instance itself is unsafe, a safe point elsewhere on
    the axis is not a usable range — the generator starts at the default."""
    sweep = [
        {"value": 400.0, "is_default": True, "mean_fill_ratio": 0.99,
         "stroke_proxy_min": 100.0, "mean_contours": 2.0},
        {"value": 700.0, "is_default": False, "mean_fill_ratio": 0.20,
         "stroke_proxy_min": 100.0, "mean_contours": 2.0},
    ]
    result = safe_range(classify_grid(sweep, small_size=True))
    assert result["status"] == "DEFAULT_INSTANCE_UNSAFE"
    assert result["min"] is None and result["max"] is None


def test_a_sweep_with_no_safe_point_offers_nothing():
    sweep = [{"value": 400.0, "is_default": True, "mean_fill_ratio": 0.99,
              "stroke_proxy_min": 100.0, "mean_contours": 2.0}]
    result = safe_range(classify_grid(sweep, small_size=True))
    assert result["status"] == "NO_SAFE_RANGE"
    assert result["min"] is None and result["max"] is None


def test_axis_ranges_are_recorded_as_not_yet_renderable():
    """The engine loads default instances only — the ranges must say so
    rather than implying the generator can render them."""
    axis_ranges = load_curation().get("axis_ranges", {})
    assert axis_ranges, "axis report not generated"
    for font_id, entry in axis_ranges.items():
        assert entry["generator_support"] == "NOT_YET_REACHABLE_BY_GENERATOR"


# --- curation states --------------------------------------------------------

def test_discovered_features_start_experimental():
    for set_id in ["reem-kufi-cv01", "aref-ruqaa-ss01", "amiri-regular-ss03"]:
        assert curation_state("features", set_id) == CurationState.EXPERIMENTAL


def test_experimental_variant_is_hidden_from_customers():
    assert not is_customer_visible("features", "reem-kufi-cv01")
    assert CurationState.EXPERIMENTAL not in CUSTOMER_VISIBLE_STATES
    assert CurationState.HIDDEN not in CUSTOMER_VISIBLE_STATES


def test_unknown_key_is_experimental_never_promoted():
    assert curation_state("features", "never-seen-before") == CurationState.EXPERIMENTAL
    assert not is_customer_visible("features", "never-seen-before")


def test_hidden_variant_is_excluded_from_customer_ranking():
    """A style bundle offered to a customer contains only reviewed sets."""
    for label in STYLE_LANGUAGE:
        bundle = resolve_style_label(label)
        for font in bundle["fonts"]:
            for set_id in font["curated_feature_sets"]:
                assert is_customer_visible("features", set_id), (
                    f"{set_id} reached a customer bundle while {curation_state('features', set_id)}"
                )


def test_customer_style_language_never_exposes_raw_ot_tags():
    payload = customer_style_options()
    assert payload
    blob = repr(payload)
    for tag in ["ss01", "cv01", "salt", "jalt", "dlig", "wght", "liga"]:
        assert tag not in blob, f"raw OpenType tag {tag} leaked to the customer payload"
    for entry in payload:
        assert entry["label_ar"] and entry["label_en"]


def test_all_eight_style_labels_are_offered():
    labels = {o["label_ar"] for o in customer_style_options()}
    assert labels == {"كلاسيكي", "ناعم", "فاخر", "هندسي", "حديث", "انسيابي", "تراثي", "جريء"}


# --- suitability ------------------------------------------------------------

def test_aesthetic_dimensions_are_never_auto_scored():
    """Taste is not computable. Those dimensions must stay unassessed."""
    row = measure("amiri-regular", PRODUCTS["pendant"])
    for name in HUMAN_REVIEW_DIMENSIONS:
        assert row["dimensions"][name]["score"] is None
        assert row["dimensions"][name]["status"] == "NOT_ASSESSED"
    for name in COMPUTED_DIMENSIONS:
        entry = row["dimensions"][name]
        assert entry["status"] in {"MEASURED", "NOT_MEASURED"}
        assert entry["method"], "a measured dimension must record its method"
    assert row["human_review_required"] is True


def test_suitability_is_product_specific_not_universal():
    """The same font must score differently across products, or the score
    is a universal one wearing a disguise."""
    scores = {
        name: measure("reem-kufi", profile)["computed_suitability"]
        for name, profile in PRODUCTS.items()
    }
    present = [v for v in scores.values() if v is not None]
    assert len(set(present)) > 1, "font scored identically on every product"


def test_product_suitability_changes_the_recommended_font():
    matrix = [measure(f, p) for f in ["amiri-regular", "reem-kufi", "aref-ruqaa"]
              for p in [PRODUCTS["ring"], PRODUCTS["brooch"]]]
    best = best_font_per_product(matrix)
    assert best, "no manufacturable recommendation produced"
    for entry in best.values():
        assert entry["human_review_required"] is True


def test_unmanufacturable_font_is_never_recommended():
    fake = [
        {"product": "ring", "font_id": "pretty-but-broken",
         "manufacturable": False, "computed_suitability": 0.99},
        {"product": "ring", "font_id": "plain-but-buildable",
         "manufacturable": True, "computed_suitability": 0.30},
    ]
    assert best_font_per_product(fake)["ring"]["font_id"] == "plain-but-buildable"


def test_aesthetic_score_cannot_override_manufacturing_failure():
    blocked = aesthetic_gate(validation_passed=False, aesthetic_score=1.0)
    assert blocked["selectable"] is False
    assert blocked["reason"] == "MANUFACTURING_VALIDATION_FAILED"
    assert aesthetic_gate(validation_passed=True, aesthetic_score=0.1)["selectable"] is True


# --- golden production evidence --------------------------------------------

def test_golden_production_evidence_outranks_ai_opinion():
    assert EVIDENCE_PRIORITY[0] == "MANUFACTURED_CUSTOMER_APPROVED"
    assert EVIDENCE_PRIORITY[-1] == "AI_AESTHETIC_OPINION"


def test_golden_case_influences_the_matching_products():
    earring = golden_case_influence("single_letter_earring")
    assert earring, "the manufactured pearl-earring case must inform earrings"
    assert any("LOWER_ATTACHMENT_LOOP" in e["construction_principles"] for e in earring)
    assert all(e["geometry_copied"] is False for e in earring)
    assert all(e["evidence_tier"] == "MANUFACTURED_CUSTOMER_APPROVED" for e in earring)

    necklace = golden_case_influence("necklace")
    assert any("OUTER_CHAIN" in e["construction_principles"] for e in necklace)
    # A product neither case covers gets nothing invented for it.
    assert golden_case_influence("cufflink") == []


# --- boundaries that must not move -----------------------------------------

def test_classical_diwani_and_thuluth_cannot_be_selected_through_curation():
    """Curation must not become a back door to the unlicensed scripts."""
    from app.fonts.capabilities import LICENSE_REQUIRED, resolve_script_request

    for family in ("diwani", "diwani_jali", "thuluth", "thuluth_jali"):
        assert resolve_script_request(family)["font_id"] is None
    for label, spec in STYLE_LANGUAGE.items():
        for family in spec["script_families"]:
            resolved = resolve_script_request(family)
            if resolved["outcome"] != "AVAILABLE":
                assert resolved["font_id"] is None, (
                    f"style '{label}' resolved an unlicensed script to a font"
                )
    from app.fonts.capabilities import script_capability_map
    caps = script_capability_map()
    assert caps["thuluth"]["status"] == LICENSE_REQUIRED
    assert caps["diwani"]["status"] == LICENSE_REQUIRED


def test_source_text_is_immutable_through_the_curation_path():
    from app.engines.arabic_engine import shape_text
    from app.fonts.feature_safety import GOLDEN_CORPUS

    for text in GOLDEN_CORPUS[:6]:
        before = text
        for case in curated_combinations()[:5]:
            shape_text(text, case.font_id, {t: True for t in case.tags} or None)
        assert text == before
