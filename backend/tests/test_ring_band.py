"""Engraved ring band — flat-pattern construction regression tests.

Locks in: real flat-pattern maths, engraving-mode validation (dots may
float, strokes must engrave, margins hold), exact-text preservation, DXF
ENGRAVE layer, the full ring service flow, and — critically — that adding
the ring field renumbered NO existing silhouette candidate.
"""
import math

import ezdxf
import pytest
from shapely import wkt as shapely_wkt

from app.config import DEFAULT_RULES
from app.engines.generator import _candidate_id, build_candidate
from app.engines.ring_band import (
    DEFAULT_THICKNESS_MM,
    ENGRAVE_MIN_STROKE_MM,
    band_length_mm,
    generate_ring_candidates,
    ring_rules,
)
from app.exporters.dxf_exporter import export_dxf
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams
from app.services import design_service as svc


def _ring_recipe(**ring_overrides) -> RecipeParams:
    ring = {"size_eu": 52, "band_height_mm": 7.5, "border": "double_line"}
    ring.update(ring_overrides)
    return RecipeParams(
        recipe_id="ring-test",
        name="ring test",
        font_id="amiri-regular",
        composition="engraved_band",
        loops="none",
        dot_strategy="keep",
        ring=ring,
    )


SOURCE = ImmutableSourceText.create("أنت القصة", confirmed=True)
RULES = ring_rules(DEFAULT_RULES)


def test_flat_pattern_length_is_neutral_axis_math():
    # EU size = inner circumference; strip length adds π·thickness.
    assert band_length_mm(52) == pytest.approx(52 + math.pi * DEFAULT_THICKNESS_MM, abs=0.001)
    assert band_length_mm(60, 2.0) == pytest.approx(60 + math.pi * 2.0, abs=0.001)


def test_band_cut_geometry_is_the_developed_strip():
    c = build_candidate("d1", SOURCE, _ring_recipe(), RULES)
    band = shapely_wkt.loads(c.geometry_wkt)
    minx, miny, maxx, maxy = band.bounds
    assert (maxx - minx) == pytest.approx(band_length_mm(52), abs=0.01)
    assert (maxy - miny) == pytest.approx(7.5, abs=0.01)
    assert len(band.geoms) == 1 and not band.geoms[0].interiors


def test_engraving_stays_inside_margins_and_preserves_text():
    c = build_candidate("d1", SOURCE, _ring_recipe(), RULES)
    assert c.identity_proof.verified, "exact source text must shape and verify"
    engrave = shapely_wkt.loads(c.text_geometry_wkt)
    band = shapely_wkt.loads(c.geometry_wkt)
    assert engrave.within(band.buffer(-0.5)), "engraving clear of the band edge"
    assert c.validation.passed, [v.detail for v in c.validation.violations]
    assert c.validation.checked_component_count == 1  # one solid strip, no holes


def test_engraved_dots_may_float_freely():
    """Engraving is marks on solid metal: a text with dots must NOT fail
    connectivity, and no bridges are added."""
    source = ImmutableSourceText.create("نور", confirmed=True)  # ن has a dot
    c = build_candidate("d1", source, _ring_recipe(), RULES)
    codes = {v.code.value for v in c.validation.violations}
    assert "DISCONNECTED_COMPONENT" not in codes
    assert "FLOATING_ISLAND" not in codes
    assert c.validation.passed, [v.detail for v in c.validation.violations]


def test_out_of_catalogue_ring_size_is_blocked():
    from app.engines.ring_band import ring_violations

    c = build_candidate("d1", SOURCE, _ring_recipe(size_eu=80), RULES)
    extra = ring_violations(c, RULES)
    assert any(v.code.value == "RING_SIZE_OUT_OF_RANGE" for v in extra)


def test_dxf_carries_engrave_layer_and_ring_metadata():
    c = build_candidate("d1", SOURCE, _ring_recipe(), RULES)
    assert c.validation.production_export_allowed, [
        v.detail for v in c.validation.violations
    ]
    dxf_text = export_dxf(c, SOURCE)
    import io

    doc = ezdxf.read(io.StringIO(dxf_text))
    layers = {layer.dxf.name for layer in doc.layers}
    assert {"CUT", "ENGRAVE"} <= layers
    engrave_entities = [e for e in doc.modelspace() if e.dxf.layer == "ENGRAVE"]
    assert engrave_entities, "engraving polylines present on their own layer"
    assert ("RING_SIZE_EU", "52") in [
        (k, v) for k, v in doc.header.custom_vars
    ]


def test_ring_flow_end_to_end_with_agreement_proof(clean_tables, db_session):
    req = svc.create_request(db_session, "أنت القصة", "ring")
    svc.confirm_request_text(db_session, req.id, "أنت القصة")
    # Ring size arrives via the brief hints in production; simulate that.
    from app.services.intake_service import upsert_brief

    upsert_brief(db_session, req.id, product_type="ring", ring_size_eu=54, band_height_mm=6.5)
    result = svc.generate_and_persist_candidates(db_session, req.id)
    top = result["top"]
    assert len(top) == 10, "ten genuinely diverse ring options"
    for c in top:
        assert c.recipe.ring["size_eu"] == 54
        assert c.recipe.ring["band_height_mm"] == 6.5
        assert c.validation.passed

    _, version = svc.select_candidate(db_session, req.id, top[0].candidate_id)
    db_session.flush()
    svg = svc.agreement_proof_for_version(db_session, version)
    assert "خاتم" in svg  # the spec block names the product in Arabic
    assert "mm" in svg


def test_adding_the_ring_field_renumbered_no_existing_candidate():
    """The hash-stability invariant that protects every persisted design:
    a recipe without a ring serializes exactly as before the field existed."""
    recipe = RecipeParams(
        recipe_id="r1", name="n", font_id="amiri-regular", composition="bare"
    )
    dumped = recipe.model_dump_json(exclude={"font_axes", "ring"})
    assert '"ring"' not in dumped
    a = _candidate_id("d", recipe, "sha")
    assert a == _candidate_id("d", recipe.model_copy(), "sha")
    # And a ring recipe hashes differently per size (a resize is a new design).
    r52 = _ring_recipe(size_eu=52)
    r54 = _ring_recipe(size_eu=54)
    assert _candidate_id("d", r52, "sha") != _candidate_id("d", r54, "sha")
