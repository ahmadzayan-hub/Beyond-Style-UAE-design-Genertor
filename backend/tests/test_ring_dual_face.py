"""Double-face ring engraving — outer phrase + inner names.

The inner text lives inside the SAME immutable source text as a second
line (outer\ninner), exactly like the two-name necklace pattern: one
confirmed text, one identity proof over every codepoint. Locks in: both
faces built and validated, the inner flat pattern mirrored for back-face
engraving, the version hash binding BOTH engrave layers, the DXF
ENGRAVE_INNER layer, and honest refusal of more than two faces.
"""
import io

import ezdxf
import pytest
from shapely import affinity
from shapely import wkt as shapely_wkt

from app.config import DEFAULT_RULES
from app.engines.generator import build_candidate
from app.engines.ring_band import ring_rules
from app.exporters.dxf_exporter import export_dxf
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams
from app.services import design_service as svc

RULES = ring_rules(DEFAULT_RULES)
DUAL = ImmutableSourceText.create("أنت القصة\nعائشة وحسن", confirmed=True)


def _ring_recipe(**ring_overrides) -> RecipeParams:
    ring = {"size_eu": 52, "band_height_mm": 7.5, "border": "double_line"}
    ring.update(ring_overrides)
    return RecipeParams(
        recipe_id="ring-dual-test",
        name="ring dual test",
        font_id="amiri-regular",
        composition="engraved_band",
        loops="none",
        dot_strategy="keep",
        ring=ring,
    )


def test_both_faces_build_and_identity_covers_the_full_text():
    c = build_candidate("d1", DUAL, _ring_recipe(), RULES)
    assert c.identity_proof.verified, c.identity_proof.detail
    assert c.text_geometry_wkt, "outer face engraving"
    assert c.inner_text_geometry_wkt, "inner face engraving"
    band = shapely_wkt.loads(c.geometry_wkt)
    inner = shapely_wkt.loads(c.inner_text_geometry_wkt)
    assert inner.within(band.buffer(-0.5)), "inner engraving inside margins"
    assert c.validation.passed, [v.detail for v in c.validation.violations]


def test_inner_flat_pattern_is_mirrored_for_back_face_engraving():
    """Mirroring the inner layer back about the strip centerline must give
    the geometry the un-mirrored build would produce — proven by comparing
    against a single-face build of the inner text alone."""
    c = build_candidate("d1", DUAL, _ring_recipe(), RULES)
    inner = shapely_wkt.loads(c.inner_text_geometry_wkt)
    band = shapely_wkt.loads(c.geometry_wkt)
    length = band.bounds[2] - band.bounds[0]

    alone = build_candidate(
        "d1", ImmutableSourceText.create("عائشة وحسن", confirmed=True),
        _ring_recipe(border="none"), RULES,
    )
    upright = shapely_wkt.loads(alone.text_geometry_wkt)
    remirrored = affinity.scale(inner, xfact=-1, yfact=1, origin=(length / 2, 0))
    # Same text, same face height budget → same area and same bounds.
    assert remirrored.area == pytest.approx(upright.area, rel=0.01)
    assert remirrored.bounds[0] == pytest.approx(upright.bounds[0], abs=0.05)


def test_single_face_ring_still_has_no_inner_layer():
    c = build_candidate(
        "d1", ImmutableSourceText.create("أنت القصة", confirmed=True), _ring_recipe(), RULES
    )
    assert c.inner_text_geometry_wkt == ""


def test_more_than_two_faces_is_refused_not_merged():
    with pytest.raises(ValueError):
        build_candidate(
            "d1", ImmutableSourceText.create("أ\nب\nج", confirmed=True), _ring_recipe(), RULES
        )


def test_dxf_gains_engrave_inner_layer_with_workshop_note():
    c = build_candidate("d1", DUAL, _ring_recipe(), RULES)
    doc = ezdxf.read(io.StringIO(export_dxf(c, DUAL)))
    layers = {layer.dxf.name for layer in doc.layers}
    assert {"CUT", "ENGRAVE", "ENGRAVE_INNER"} <= layers
    assert [e for e in doc.modelspace() if e.dxf.layer == "ENGRAVE_INNER"]
    assert any(k == "ENGRAVE_INNER_NOTE" for k, _ in doc.header.custom_vars)


def test_version_hash_binds_both_engrave_layers():
    """Every ring shares one CUT rectangle — the version hash must change
    when only the engraving differs, or approval could not distinguish two
    different engravings."""
    from app.services.design_service import _design_geometry_hash

    c = build_candidate("d1", DUAL, _ring_recipe(), RULES)
    recipe = c.recipe.model_dump()
    h1 = _design_geometry_hash(recipe, c.geometry_wkt, c.text_geometry_wkt, c.inner_text_geometry_wkt)
    h2 = _design_geometry_hash(recipe, c.geometry_wkt, c.text_geometry_wkt, "")
    h3 = _design_geometry_hash(recipe, c.geometry_wkt, c.text_geometry_wkt, c.inner_text_geometry_wkt)
    assert h1 != h2, "dropping the inner engraving must change the hash"
    assert h1 == h3, "deterministic"
    # Silhouette products keep the original CUT-only hash (no renumbering).
    import hashlib

    assert _design_geometry_hash({}, "WKT", "x", "y") == hashlib.sha256(b"WKT").hexdigest()


def test_dual_face_ring_flow_end_to_end(clean_tables, db_session):
    from app.services.intake_service import upsert_brief

    req = svc.create_request(db_session, "أنت القصة\nعائشة وحسن", "ring")
    svc.confirm_request_text(db_session, req.id, "أنت القصة\nعائشة وحسن")
    upsert_brief(db_session, req.id, product_type="ring", ring_size_eu=52)
    result = svc.generate_and_persist_candidates(db_session, req.id)
    assert len(result["top"]) == 10
    _, version = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    db_session.flush()
    assert version.inner_text_geometry_wkt, "inner layer persisted on the version"
    # Approval re-verification passes with the ring-aware hash.
    approval = svc.approve_version(
        db_session, version.id,
        confirmed_text="أنت القصة\nعائشة وحسن",
        source_text_sha256=version.source_text_sha256,
        geometry_hash=version.geometry_hash,
        approved_by="test-customer",
    )
    assert approval.status == "ACTIVE"
    # Both faces on the dimensioned agreement proof.
    svg = svc.agreement_proof_for_version(db_session, version)
    assert "الوجه الداخلي" in svg
    # 3D payload carries the inner face.
    from app.services.mesh3d import mesh3d_payload

    p = mesh3d_payload(version, "ring")
    assert p["inner_engrave_polygons"]
