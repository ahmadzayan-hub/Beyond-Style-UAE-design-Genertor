"""Variable-font axis plumbing and real-mm geometry validation.

The invariant: coordinates are real production inputs — validated, carried
identically through shaping AND outline extraction, part of design identity,
traceable in exports, and gated on millimetres rather than proxies.
"""
from __future__ import annotations

import json
import re

import pytest
from shapely import wkt as _wkt

from app.config import DEFAULT_RULES
from app.engines.generator import build_candidate
from app.engines.geometry_metrics import (
    MEASUREMENT_BASIS, measure_mm, meets_workshop_rules,
)
from app.exporters.svg_exporter import export_svg
from app.fonts.curation import customer_axis_for_style, designer_axis_bounds
from app.fonts.instances import (
    AxisValueOutOfRange, UnsupportedAxis, font_axis_specs, get_instance,
    glyphset_for, hb_font_for, validate_axes,
)
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams

VAR_FONT = "reem-kufi"
STATIC_FONT = "amiri-regular"


def _recipe(**over) -> RecipeParams:
    base = dict(recipe_id="axis-test", name="axis test", font_id=VAR_FONT,
                composition="plate_rect", target_height_mm=16, stroke_delta_mm=0.35,
                dot_strategy="bridge", loops="left_right")
    base.update(over)
    return RecipeParams(**base)


def _build(axes: dict, text: str = "نورة"):
    source = ImmutableSourceText.create(text, confirmed=True)
    return build_candidate("d", source, _recipe(font_axes=axes), DEFAULT_RULES), source


# --- validation: never silently clamp --------------------------------------

def test_out_of_range_axis_is_rejected_not_clamped():
    with pytest.raises(AxisValueOutOfRange) as exc:
        validate_axes(VAR_FONT, {"wght": 5000})
    assert exc.value.detail["code"] == "AXIS_VALUE_OUT_OF_RANGE"
    assert exc.value.detail["font_max"] == 700.0
    with pytest.raises(AxisValueOutOfRange):
        validate_axes(VAR_FONT, {"wght": 100})


def test_unsupported_axis_is_rejected():
    with pytest.raises(UnsupportedAxis) as exc:
        validate_axes(VAR_FONT, {"wdth": 100})
    assert exc.value.detail["code"] == "UNSUPPORTED_AXIS"
    # A static font supports no axis at all.
    with pytest.raises(UnsupportedAxis):
        validate_axes(STATIC_FONT, {"wght": 500})


def test_non_numeric_axis_value_is_rejected():
    with pytest.raises(AxisValueOutOfRange):
        validate_axes(VAR_FONT, {"wght": "heavy"})


def test_product_unsafe_axis_value_is_refused():
    """A value inside the font range but outside the geometry-verified
    product range must still be refused."""
    from app.fonts import instances as inst

    original = inst.product_safe_range
    inst.product_safe_range = lambda f, a, p: {
        "min": 400.0, "max": 500.0, "evidence_level": "GEOMETRY_VERIFIED_SAFE"}
    try:
        with pytest.raises(AxisValueOutOfRange) as exc:
            validate_axes(VAR_FONT, {"wght": 700}, product="single_letter_earring")
        assert exc.value.detail["safe_max"] == 500.0
        assert validate_axes(VAR_FONT, {"wght": 450}, product="single_letter_earring")
    finally:
        inst.product_safe_range = original


# --- one instance for shaping AND outlines ---------------------------------

def test_shaping_and_outlines_use_the_same_instance():
    instance = get_instance(VAR_FONT, {"wght": 700})
    hb = hb_font_for(instance)
    glyphset, order = glyphset_for(instance)
    # Same instance object → same cache entry → same underlying bytes.
    assert hb_font_for(get_instance(VAR_FONT, {"wght": 700})) is hb
    assert glyphset_for(get_instance(VAR_FONT, {"wght": 700}))[1] is order
    assert hb.face.upem > 0 and len(order) > 0


def test_instance_key_distinguishes_coordinates():
    assert get_instance(VAR_FONT).key == VAR_FONT
    assert get_instance(VAR_FONT, {"wght": 700}).key == "reem-kufi[wght=700]"
    assert get_instance(VAR_FONT, {"wght": 400}).key != get_instance(VAR_FONT, {"wght": 700}).key


def test_axis_change_actually_thickens_the_built_geometry():
    """Proof the coordinates reach the OUTLINES, not just the shaper.

    Measured on a bare composition: a backing plate would dominate the area
    and hide whether the letterforms themselves got heavier."""
    source = ImmutableSourceText.create("نورة", confirmed=True)

    def bare(weight):
        recipe = _recipe(composition="bare", loops="none", stroke_delta_mm=0.0,
                         font_axes={"wght": weight})
        return build_candidate("d", source, recipe, DEFAULT_RULES)

    light, heavy = bare(400), bare(700)
    thin = measure_mm(_wkt.loads(light.geometry_wkt))
    thick = measure_mm(_wkt.loads(heavy.geometry_wkt))
    assert thick["area_mm2"] > thin["area_mm2"], "heavier weight produced no extra material"


# --- determinism and identity ----------------------------------------------

def test_same_axes_produce_byte_identical_geometry():
    a, _ = _build({"wght": 550})
    b, _ = _build({"wght": 550})
    assert a.geometry_wkt == b.geometry_wkt
    assert a.candidate_id == b.candidate_id


def test_axis_value_changes_the_candidate_identity():
    light, _ = _build({"wght": 400})
    heavy, _ = _build({"wght": 700})
    assert light.candidate_id != heavy.candidate_id
    assert light.geometry_wkt != heavy.geometry_wkt


def test_absent_axes_match_the_explicit_default_instance():
    """Golden Path stability: no axes must equal the font's own default."""
    implicit, _ = _build({})
    explicit, _ = _build({"wght": font_axis_specs(VAR_FONT)["wght"]["default"]})
    assert implicit.geometry_wkt == explicit.geometry_wkt


def test_empty_axes_do_not_change_pre_axis_candidate_ids():
    """The field was added without renumbering existing designs."""
    source = ImmutableSourceText.create("نورة", confirmed=True)
    with_field = build_candidate("d", source, _recipe(font_axes={}), DEFAULT_RULES)
    baseline = build_candidate("d", source, _recipe(), DEFAULT_RULES)
    assert with_field.candidate_id == baseline.candidate_id


# --- approved designs are immutable ----------------------------------------

def test_changing_axes_creates_a_new_version_never_mutates_approved(
    clean_tables, db_session
):
    from app.services import design_service as svc

    req = svc.create_request(db_session, "ميثة", "pendant")
    svc.confirm_request_text(db_session, req.id, "ميثة")
    result = svc.generate_and_persist_candidates(db_session, req.id)
    design, v1 = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    svc.approve_version(
        db_session, v1.id, confirmed_text=v1.immutable_source_text,
        source_text_sha256=v1.source_text_sha256, geometry_hash=v1.geometry_hash,
        approved_by="customer",
    )
    db_session.commit()
    approved_hash, approved_text = v1.geometry_hash, v1.immutable_source_text

    # Move to a variable font AND a weight in one edit: the result must be a
    # new version, with the approved one untouched.
    v2 = svc.edit_version(
        db_session, v1.id,
        {"font_id": "reem-kufi", "font_axes": {"wght": 550}}, None, "designer",
    )
    db_session.commit()
    assert v2.id != v1.id
    assert v2.version_number == v1.version_number + 1
    assert v2.recipe["font_axes"] == {"wght": 550.0}
    assert v2.geometry_hash != approved_hash
    # The approved version is unchanged in every respect that matters.
    assert v1.geometry_hash == approved_hash
    assert v1.immutable_source_text == approved_text == v2.immutable_source_text
    assert v1.recipe.get("font_axes", {}) == {}


def test_axis_edit_on_a_static_font_is_refused_with_a_structured_error(
    clean_tables, db_session
):
    """A weight on a font that has no axes must be refused cleanly, not
    crash inside the font library."""
    from app.services import design_service as svc

    req = svc.create_request(db_session, "ميثة", "pendant")
    svc.confirm_request_text(db_session, req.id, "ميثة")
    result = svc.generate_and_persist_candidates(db_session, req.id)
    _, v1 = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    db_session.commit()

    with pytest.raises(UnsupportedAxis) as exc:
        svc.edit_version(
            db_session, v1.id,
            {"font_id": "amiri-regular", "font_axes": {"wght": 550}}, None, "designer",
        )
    assert exc.value.detail["code"] == "UNSUPPORTED_AXIS"
    db_session.rollback()


# --- export traceability ----------------------------------------------------

def test_export_metadata_carries_axes_and_font_binary():
    candidate, source = _build({"wght": 625})
    svg = export_svg(candidate, source)
    meta = json.loads(re.search(r"<metadata>(.*?)</metadata>", svg).group(1).replace("&quot;", '"'))
    assert meta["font_axes"] == {"wght": 625.0}
    assert meta["font_id"] == VAR_FONT
    assert len(meta["font_binary_sha256"]) == 64
    assert meta["ot_feature_set"]
    assert meta["source_text_sha256"] == source.sha256


def test_default_instance_export_records_empty_axes():
    candidate, source = _build({})
    svg = export_svg(candidate, source)
    meta = json.loads(re.search(r"<metadata>(.*?)</metadata>", svg).group(1).replace("&quot;", '"'))
    assert meta["font_axes"] == {}


# --- real millimetres, not proxies -----------------------------------------

def test_measurements_are_labelled_real_mm():
    candidate, _ = _build({"wght": 400})
    mm = measure_mm(_wkt.loads(candidate.geometry_wkt))
    assert mm["basis"] == MEASUREMENT_BASIS == "REAL_MM_FROM_BUILT_GEOMETRY"
    assert mm["min_material_width_mm"] > 0
    assert mm["width_mm"] > 0 and mm["height_mm"] > 0


def test_manufacturing_gate_uses_mm_and_rejects_thin_material():
    thin = {"empty": False, "min_material_width_mm": DEFAULT_RULES.min_stroke_mm - 0.1,
            "min_gap_mm": 5.0, "counter_clearance_mm": 5.0, "small_islands": [],
            "width_mm": 10.0, "height_mm": 10.0}
    verdict = meets_workshop_rules(thin, DEFAULT_RULES)
    assert verdict["passed"] is False
    assert verdict["basis"] == MEASUREMENT_BASIS
    assert "min material" in verdict["failures"][0]


def test_closing_counters_are_caught_in_mm():
    closing = {"empty": False, "min_material_width_mm": 2.0,
               "min_gap_mm": 5.0, "counter_clearance_mm": DEFAULT_RULES.min_gap_mm - 0.1,
               "small_islands": [], "width_mm": 10.0, "height_mm": 10.0}
    verdict = meets_workshop_rules(closing, DEFAULT_RULES)
    assert verdict["passed"] is False
    assert "counter clearance" in verdict["failures"][0]


def test_relative_proxy_is_never_used_for_manufacturing():
    """The axes module's stroke figure is aesthetic/relative and must not
    appear in the manufacturing surface."""
    import inspect

    from app.engines import geometry_metrics

    source = inspect.getsource(geometry_metrics)
    assert "stroke_proxy" not in source
    from app.fonts.axes import measure_instance  # relative metric lives here
    assert "stroke_proxy_note" in inspect.getsource(measure_instance)


# --- UI bounds --------------------------------------------------------------

def test_designer_bounds_only_offer_geometry_verified_ranges():
    bounds = designer_axis_bounds(VAR_FONT, "necklace")
    wght = bounds["axes"]["wght"]
    if wght["available"]:
        assert wght["evidence_level"] == "GEOMETRY_VERIFIED_SAFE"
        assert wght["min"] >= wght["font_min"] and wght["max"] <= wght["font_max"]


def test_static_font_offers_no_slider():
    bounds = designer_axis_bounds(STATIC_FONT, "necklace")
    assert bounds["available"] is False
    assert bounds["reason"] == "STATIC_FONT_NO_AXES"


def test_customer_style_resolves_inside_the_verified_range_only():
    for label in ("ناعم", "فاخر", "جريء"):
        resolved = customer_axis_for_style(label, VAR_FONT, "necklace")
        if not resolved["font_axes"]:
            continue
        lo, hi = resolved["within_verified_range"]
        assert lo <= resolved["font_axes"]["wght"] <= hi
        # And the resolved value really is accepted by validation.
        validate_axes(VAR_FONT, resolved["font_axes"], product="necklace")


def test_customer_never_receives_numeric_axis_values():
    from app.fonts.curation import customer_style_options

    blob = repr(customer_style_options())
    assert "wght" not in blob
    assert "font_axes" not in blob


# --- boundaries that must not move -----------------------------------------

def test_true_diwani_status_unchanged_and_thuluth_only_via_rights_cleared_source():
    from app.fonts.capabilities import LICENSE_REQUIRED, REAL, script_capability_map
    from app.fonts.registry import get_registry

    caps = script_capability_map()
    for family in ("diwani", "diwani_jali"):
        assert caps[family]["status"] == LICENSE_REQUIRED
        assert caps[family]["fonts"] == []
    for family in ("thuluth", "thuluth_jali"):
        assert caps[family]["status"] == REAL
        assert caps[family]["fonts"] and all(
            get_registry().get(fid).rights_status.value == "VERIFIED_OPEN_SOURCE" for fid in caps[family]["fonts"]
        )
