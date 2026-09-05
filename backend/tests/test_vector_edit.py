"""Vector edit operations: deterministic, fail-safe, text-protected,
versioned. Engine tests need no database; the service/API tests do."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, Point, box

from app.config import DEFAULT_RULES
from app.engines.geometry_engine import BuiltGeometry
from app.engines.validator import validate
from app.engines.vector_edit import VectorEditRejected, apply_op, apply_ops
from app.main import app
from app.schemas.jewellery_design import TextIdentityProof
from app.services import design_service as svc

TEXT = "ميثه"
PROOF = TextIdentityProof(verified=True, covered_codepoint_indices=[0, 1, 2, 3], uncovered_codepoint_indices=[], notdef_glyph_count=0)


def _plate_with_text():
    plate = box(0, 0, 20, 10)
    text = box(4, 3, 16, 7)   # a "letter block" inside the plate
    return BuiltGeometry(geometry=MultiPolygon([plate]), text_geometry=MultiPolygon([text]))


def test_rigid_transforms_keep_area_and_text_and_move_rings():
    b = _plate_with_text()
    b.loop_centers_mm = [(10.0, 10.0)]
    out, log = apply_ops(b, [{"op": "translate", "params": {"dx_mm": 5, "dy_mm": -2}},
                            {"op": "rotate", "params": {"angle_deg": 90}},
                            {"op": "scale", "params": {"factor": 1.5}}], DEFAULT_RULES)
    assert abs(out.geometry.area - 200 * 1.5 ** 2) < 1e-6
    assert abs(out.text_geometry.area - 48 * 1.5 ** 2) < 1e-6
    assert out.text_geometry.difference(out.geometry).area < 1e-9      # letters still inside the plate
    assert len(out.loop_centers_mm) == 1 and out.loop_centers_mm[0] != (10.0, 10.0)
    assert [e["op"] for e in log] == ["translate", "rotate", "scale"] and all("bounds_mm" in e for e in log)


def test_mirror_and_unbuilt_tools_are_refused_with_reasons():
    b = _plate_with_text()
    for op in ("mirror", "flip", "node_edit", "pen"):
        with pytest.raises(VectorEditRejected):
            apply_op(b, {"op": op, "params": {}}, DEFAULT_RULES)
    with pytest.raises(VectorEditRejected, match="Unknown op"):
        apply_op(b, {"op": "explode", "params": {}}, DEFAULT_RULES)


def test_cut_is_text_protected_but_allowed_outside_letters():
    b = _plate_with_text()
    with pytest.raises(VectorEditRejected, match="protected"):
        apply_op(b, {"op": "cut_shape", "params": {"shape": "circle", "center": [10, 5], "diameter_mm": 3}}, DEFAULT_RULES)
    out, log = apply_op(b, {"op": "cut_shape", "params": {"shape": "circle", "center": [2, 8.5], "diameter_mm": 1.5}}, DEFAULT_RULES)
    assert out.geometry.area < b.geometry.area and out.text_geometry.equals(b.text_geometry)
    with pytest.raises(VectorEditRejected, match="whole design"):
        apply_op(BuiltGeometry(geometry=MultiPolygon([box(0, 0, 2, 2)])),
                 {"op": "cut_shape", "params": {"shape": "rect", "origin": [-1, -1], "width_mm": 5, "height_mm": 5}}, DEFAULT_RULES)


def test_bridge_and_ring_honour_workshop_minimums_and_must_touch():
    b = _plate_with_text()
    r = DEFAULT_RULES
    with pytest.raises(VectorEditRejected, match="below the workshop minimum"):
        apply_op(b, {"op": "add_bridge", "params": {"from": [20, 5], "to": [25, 5], "width_mm": r.min_bridge_mm / 2}}, r)
    with pytest.raises(VectorEditRejected, match="floating"):
        apply_op(b, {"op": "add_bridge", "params": {"from": [30, 5], "to": [35, 5]}}, r)
    with pytest.raises(VectorEditRejected, match="does not touch"):
        apply_op(b, {"op": "add_ring", "params": {"center": [40, 40]}}, r)
    with pytest.raises(VectorEditRejected, match="minimum"):
        apply_op(b, {"op": "add_ring", "params": {"position": "top_center", "wall_mm": 0.3}}, r)
    out, log = apply_op(b, {"op": "add_ring", "params": {"position": "top_center"}}, r)
    assert len(out.loop_centers_mm) == 1 and out.geometry.geom_type == "MultiPolygon"
    holes = sum(len(p.interiors) for p in out.geometry.geoms)
    assert holes == 1
    rep = validate(out, r, PROOF, expected_loops=1)
    assert not [v for v in rep.violations if v.code.value == "UNSAFE_LOOP"], rep.violations
    # a ring whose hole would eat letters is refused
    with pytest.raises(VectorEditRejected, match="letters"):
        apply_op(b, {"op": "add_ring", "params": {"center": [10, 5]}}, r)


def test_real_repair_connects_floating_part_from_validator_fix():
    """Validator proposes a bridge (from/to); the fix becomes a real op and
    the repaired geometry passes."""
    main, island = box(0, 0, 10, 10), box(12, 4, 14, 6)
    b = BuiltGeometry(geometry=MultiPolygon([main, island]))
    before = validate(b, DEFAULT_RULES, PROOF)
    fixes = svc.fix_ops_from_report(before, DEFAULT_RULES)
    assert "connect_floating_parts" in fixes and fixes["connect_floating_parts"][0]["op"] == "add_bridge"
    out, _ = apply_ops(b, fixes["connect_floating_parts"], DEFAULT_RULES)
    assert len(out.geometry.geoms) == 1 and out.bridges_added == 1
    after = validate(out, DEFAULT_RULES, PROOF)
    assert after.passed, after.violations


def test_all_or_nothing_replay_reports_failing_index():
    b = _plate_with_text()
    with pytest.raises(VectorEditRejected, match=r"op 2 \(cut_shape\)"):
        apply_ops(b, [{"op": "translate", "params": {"dx_mm": 1, "dy_mm": 0}},
                      {"op": "cut_shape", "params": {"shape": "circle", "center": [11, 5], "diameter_mm": 2}}], DEFAULT_RULES)


# ---------------------------------------------------------------- DB / API


def _selected(c, text=TEXT):
    created = c.post("/api/designs", json={"text": text, "product_type": "pendant"}).json()
    h = {"X-Session-Token": created["session_token"]}
    did = created["design_id"]
    c.post(f"/api/designs/{did}/confirm", json={"confirmed_text": text}, headers=h)
    gen = c.post(f"/api/designs/{did}/candidates", headers=h).json()
    sel = c.post(f"/api/designs/{did}/select", json={"candidate_id": gen["top"][0]["candidate_id"]}, headers=h).json()
    return did, sel, h


def test_vector_edit_versions_replays_and_protects(clean_tables, db_session):
    with TestClient(app) as c:
        did, sel, h = _selected(c)
        vid = sel["version_id"]
        cat = c.get(f"/api/versions/{vid}/vector-ops", headers=h).json()
        assert cat["editable"] and {t["op"] for t in cat["tools"]} >= {"translate", "add_bridge", "add_ring", "cut_shape"}
        assert {r["op"] for r in cat["refused"]} == {"mirror", "node_edit", "pen"} and cat["bounds_mm"]
        # preview: nothing persisted
        pv = c.post(f"/api/versions/{vid}/vector-edit/preview", json={"ops": [{"op": "translate", "params": {"dx_mm": 3, "dy_mm": 0}}]}, headers=h)
        assert pv.status_code == 200 and pv.json()["svg"].startswith("<svg")
        assert c.get(f"/api/versions/{vid}", headers=h).json()["version_number"] == 1
        # refused op → 422, no version
        bad = c.post(f"/api/versions/{vid}/vector-edit", json={"ops": [{"op": "mirror", "params": {}}]}, headers=h)
        assert bad.status_code == 422 and "reading direction" in bad.json()["detail"]
        # a real edit → v2, parent untouched, text byte-identical, hash differs
        r = c.post(f"/api/versions/{vid}/vector-edit", json={"ops": [{"op": "add_ring", "params": {"position": "top_right"}}], "note": "extra ring"}, headers=h)
        assert r.status_code == 201, r.text
        v2 = r.json()
        assert v2["version_number"] == 2 and v2["total_ops"] == 1 and v2["op_log"][0]["op"] == "add_ring"
        assert v2["source_text_sha256"] == sel["source_text_sha256"] and v2["geometry_hash"] != sel["geometry_hash"]
        parent = c.get(f"/api/versions/{vid}", headers=h).json()
        assert parent["geometry_hash"] == sel["geometry_hash"] and parent["status"] == "UNAPPROVED"
        full2 = c.get(f"/api/versions/{v2['version_id']}", headers=h).json()
        assert full2["immutable_source_text"] == TEXT and full2["edit_metadata"]["vector_ops"][0]["op"] == "add_ring"
        # recipe edit on top replays the ring → lineage keeps the manual edit
        e = c.post(f"/api/versions/{v2['version_id']}/edit", json={"recipe_overrides": {"letter_spacing_mm": 0.2}, "note": "spacing"}, headers=h)
        assert e.status_code == 201, e.text
        v3 = c.get(f"/api/versions/{e.json()['version_id']}", headers=h).json()
        assert v3["edit_metadata"]["vector_ops"] == full2["edit_metadata"]["vector_ops"]
        assert v3["edit_metadata"]["vector_op_log"][0]["op"] == "add_ring"
        # text change drops mm-anchored ops (recorded), never carries them onto other letters
        t = c.post(f"/api/versions/{v3['version_id']}/change-text", json={"new_text": "مهرة", "confirmed": True}, headers=h)
        assert t.status_code == 201
        v4 = c.get(f"/api/versions/{t.json()['version_id']}", headers=h).json()
        assert v4["edit_metadata"]["vector_ops_dropped"] == 1 and v4["immutable_source_text"] == "مهرة"
        # events carry the vector edit
        ev = c.get(f"/api/designs/{did}/events", headers=h).json()
        kinds = [x for x in ev if x["event_type"] == "DESIGN_EDITED"]
        assert any((x.get("metadata") or {}).get("kind") == "vector" for x in kinds)


def test_repair_options_are_dry_run_and_apply_by_id(clean_tables, db_session):
    with TestClient(app) as c:
        did, sel, h = _selected(c)
        vid = sel["version_id"]
        opts = c.get(f"/api/versions/{vid}/repair-options", headers=h).json()["options"]
        assert all({"repair_id", "kind", "available", "label_ar", "label_en"} <= set(o) for o in opts)
        assert c.post(f"/api/versions/{vid}/repair", json={"repair_id": "nonexistent"}, headers=h).status_code == 422
        avail = [o for o in opts if o["available"]]
        if avail:
            r = c.post(f"/api/versions/{vid}/repair", json={"repair_id": avail[0]["repair_id"]}, headers=h)
            assert r.status_code == 201 and r.json()["repair_id"] == avail[0]["repair_id"]
            assert r.json()["before_svg_url"].endswith(f"{vid}/svg")
