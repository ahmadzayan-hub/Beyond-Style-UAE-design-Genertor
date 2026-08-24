"""Manufacturing validator tests with synthetic failing geometries."""
from shapely.geometry import MultiPolygon, Point, Polygon, box

from app.engines.geometry_engine import BuiltGeometry, bridge_components, fill_small_holes
from app.engines.validator import validate
from app.schemas.jewellery_design import TextIdentityProof, ViolationCode

OK_PROOF = TextIdentityProof(
    verified=True, covered_codepoint_indices=[0], uncovered_codepoint_indices=[],
    notdef_glyph_count=0,
)
BAD_PROOF = TextIdentityProof(
    verified=False, covered_codepoint_indices=[], uncovered_codepoint_indices=[0],
    notdef_glyph_count=1, detail="notdef",
)


def _built(geom, **kw):
    return BuiltGeometry(geometry=geom if isinstance(geom, MultiPolygon) else MultiPolygon([geom]), **kw)


def _codes(report):
    return {v.code for v in report.violations}


def test_solid_plate_passes(rules):
    plate = box(0, 0, 30, 15)
    report = validate(_built(plate), rules, OK_PROOF)
    assert report.passed and report.production_export_allowed


def test_floating_island_blocked(rules):
    plate = box(0, 0, 30, 15)
    dot = Point(40, 7).buffer(0.5)
    report = validate(MultiPolygonBuilt := _built(MultiPolygon([plate, dot])), rules, OK_PROOF)
    assert not report.passed
    assert ViolationCode.FLOATING_ISLAND in _codes(report)
    fix = [v for v in report.violations if v.code == ViolationCode.FLOATING_ISLAND][0].proposed_fix
    assert fix and fix.action == "add_bridge" and fix.params["width_mm"] == rules.min_bridge_mm


def test_disconnected_component_blocked(rules):
    a, b = box(0, 0, 15, 15), box(20, 0, 35, 15)
    report = validate(_built(MultiPolygon([a, b])), rules, OK_PROOF)
    assert not report.passed
    assert ViolationCode.DISCONNECTED_COMPONENT in _codes(report)


def test_thin_stroke_blocked(rules):
    thin = box(0, 0, 20, rules.min_stroke_mm * 0.4)  # far below minimum
    report = validate(_built(thin), rules, OK_PROOF)
    assert not report.passed
    assert ViolationCode.THIN_STROKE in _codes(report)


def test_weak_bridge_blocked(rules):
    # Two chunky pads joined by a neck far below min stroke.
    neck_h = rules.min_stroke_mm * 0.3
    geom = box(0, 0, 10, 10).union(box(14, 0, 24, 10)).union(box(10, 5, 14, 5 + neck_h))
    report = validate(_built(geom), rules, OK_PROOF)
    assert not report.passed
    assert ViolationCode.WEAK_BRIDGE in _codes(report)


def test_small_gap_blocked(rules):
    outer = box(0, 0, 20, 20)
    slot = box(5, 5, 5 + rules.min_gap_mm * 0.3, 15)  # too-narrow slot
    report = validate(_built(outer.difference(slot)), rules, OK_PROOF)
    assert not report.passed
    assert ViolationCode.GAP_TOO_SMALL in _codes(report)


def test_open_path_reported(rules):
    plate = box(0, 0, 30, 15)
    report = validate(
        _built(plate, outline_issues=["open path: trailing unclosed contour"]),
        rules,
        OK_PROOF,
    )
    assert not report.passed
    assert ViolationCode.OPEN_PATH in _codes(report)


def test_unsafe_loop_blocked(rules):
    # Loop hole smaller than required inner diameter.
    small_d = rules.loop_inner_diameter_mm * 0.5
    center = (35.0, 7.5)
    plate = box(0, 0, 30, 15)
    ring = Point(center).buffer(small_d / 2 + rules.loop_wall_mm).difference(
        Point(center).buffer(small_d / 2)
    )
    geom = plate.union(box(29, 6, 34, 9)).union(ring)
    report = validate(
        _built(geom, loop_centers_mm=[center]), rules, OK_PROOF, expected_loops=1
    )
    assert not report.passed
    assert ViolationCode.UNSAFE_LOOP in _codes(report)


def test_valid_loop_passes(rules):
    d = rules.loop_inner_diameter_mm
    center = (35.0, 7.5)
    plate = box(0, 0, 31, 15)
    ring = Point(center).buffer(d / 2 + rules.loop_wall_mm, quad_segs=32).difference(
        Point(center).buffer(d / 2, quad_segs=32)
    )
    geom = plate.union(ring.buffer(0)).buffer(0)
    report = validate(
        _built(geom if geom.geom_type != "Polygon" else MultiPolygon([geom]),
               loop_centers_mm=[center]),
        rules, OK_PROOF, expected_loops=1,
    )
    loop_violations = [v for v in report.violations if v.code == ViolationCode.UNSAFE_LOOP]
    assert not loop_violations


def test_identity_failure_blocks_production(rules):
    plate = box(0, 0, 30, 15)
    report = validate(_built(plate), rules, BAD_PROOF)
    assert not report.production_export_allowed
    assert ViolationCode.TEXT_IDENTITY_UNVERIFIED in _codes(report)


def test_font_rights_block(rules):
    plate = box(0, 0, 30, 15)
    report = validate(_built(plate), rules, OK_PROOF, font_production_allowed=False)
    assert not report.production_export_allowed
    assert ViolationCode.FONT_RIGHTS_BLOCK in _codes(report)


def test_oversize_blocked(rules):
    plate = box(0, 0, rules.max_width_mm + 10, 15)
    report = validate(_built(plate), rules, OK_PROOF)
    assert ViolationCode.OVERSIZE in _codes(report)


def test_bridge_components_is_deterministic_and_connects():
    a, b, dot = box(0, 0, 10, 10), box(20, 0, 30, 10), Point(15, 20).buffer(1)
    g1, n1 = bridge_components(MultiPolygon([a, b, dot]), 1.0)
    g2, n2 = bridge_components(MultiPolygon([a, b, dot]), 1.0)
    assert len(g1.geoms) == 1 and n1 == 2
    assert g1.equals(g2) and n1 == n2


def test_fill_small_holes_keeps_large_holes(rules):
    outer = box(0, 0, 30, 30)
    tiny = Point(5, 5).buffer(rules.effective_min_gap_mm * 0.3)
    big = Point(20, 20).buffer(4)
    geom = outer.difference(tiny).difference(big)
    filled = fill_small_holes(geom, rules.effective_min_gap_mm)
    holes = [len(p.interiors) for p in filled.geoms]
    assert sum(holes) == 1  # tiny hole filled, big hole kept
