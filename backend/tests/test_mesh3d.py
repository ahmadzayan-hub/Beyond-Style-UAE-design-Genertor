"""3D payload — visualization only, canonical 2D stays the truth.

Locks in: real-mm dimensions and thickness, deterministic weight math
(area × thickness × density, no AI), ring bend radius from the EU size,
engrave layer passthrough, and the owner-session gate.
"""
import math

import pytest
from shapely import wkt as shapely_wkt

from app.config import DEFAULT_RULES
from app.services import design_service as svc
from app.services.mesh3d import MATERIAL_DENSITY_G_CM3, mesh3d_payload


@pytest.fixture
def client(clean_tables):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _pendant_version(session):
    req = svc.create_request(session, "ميثة", "pendant")
    svc.confirm_request_text(session, req.id, "ميثة")
    result = svc.generate_and_persist_candidates(session, req.id)
    _, v = svc.select_candidate(session, req.id, result["top"][0].candidate_id)
    session.flush()
    return v


def _ring_version(session):
    from app.services.intake_service import upsert_brief

    req = svc.create_request(session, "أنت القصة", "ring")
    svc.confirm_request_text(session, req.id, "أنت القصة")
    upsert_brief(session, req.id, product_type="ring", ring_size_eu=54, band_height_mm=6.5)
    result = svc.generate_and_persist_candidates(session, req.id)
    _, v = svc.select_candidate(session, req.id, result["top"][0].candidate_id)
    session.flush()
    return v


def test_pendant_payload_matches_real_geometry(clean_tables, db_session):
    v = _pendant_version(db_session)
    p = mesh3d_payload(v, "pendant")
    geom = shapely_wkt.loads(v.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    assert p["units"] == "mm"
    assert p["width_mm"] == pytest.approx(maxx - minx, abs=0.001)
    assert p["height_mm"] == pytest.approx(maxy - miny, abs=0.001)
    assert p["thickness_mm"] > 0
    assert p["ring"] is None
    # Weight is plain deterministic rules math, per material.
    vol = geom.area * p["thickness_mm"]
    for mat, density in MATERIAL_DENSITY_G_CM3.items():
        assert p["weight_estimate_g"][mat] == pytest.approx(vol * density / 1000, abs=0.01)
    # Polygon payload reproduces the canonical area (holes preserved).
    from shapely.geometry import Polygon

    rebuilt = sum(
        Polygon(poly["exterior"], holes=poly["holes"]).area for poly in p["polygons"]
    )
    assert rebuilt == pytest.approx(geom.area, rel=0.001)


def test_ring_payload_carries_bend_radius_and_engraving(clean_tables, db_session):
    v = _ring_version(db_session)
    p = mesh3d_payload(v, "ring")
    assert p["ring"]["size_eu"] == 54
    assert p["ring"]["inner_radius_mm"] == pytest.approx(54 / (2 * math.pi), abs=0.001)
    assert p["engrave_polygons"], "ring 3D view must include the engraving layer"
    assert p["thickness_mm"] == pytest.approx(1.5, abs=0.001)
    assert "manufacturing truth" in p["disclaimer"]


def test_mesh3d_endpoint_is_owner_gated(client, db_session):
    v = _pendant_version(db_session)
    r = client.get(f"/api/versions/{v.id}/mesh3d")
    assert r.status_code == 404  # anti-enumeration contract, same as /svg
