"""End-to-end API golden path against PostgreSQL:
create → confirm → generate → select → approve/lock → production export."""
import io
import xml.etree.ElementTree as ET

import ezdxf
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(clean_tables):
    with TestClient(app) as c:
        yield c


def test_full_golden_path_arabic(client):
    # 1. Create with exact Arabic text; anonymous session token issued.
    r = client.post("/api/designs", json={"text": "ميثة"})
    assert r.status_code == 201
    design_id = r.json()["design_id"]
    client.headers.update({"X-Session-Token": r.json()["session_token"]})
    assert r.json()["requires_confirmation"] is True

    # 2. Generation before confirmation is refused.
    assert client.post(f"/api/designs/{design_id}/candidates").status_code == 409

    # 3. Wrong confirmation text rejected (source text immutable).
    r = client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "ميثه"})
    assert r.status_code == 422

    # 4. Exact confirmation accepted.
    assert client.post(
        f"/api/designs/{design_id}/confirm", json={"confirmed_text": "ميثة"}
    ).status_code == 200

    # 5. Generate: ≥30 internal, top 10 diverse, spec ranking config.
    r = client.post(f"/api/designs/{design_id}/candidates")
    body = r.json()
    assert body["internal_candidate_count"] >= 30
    assert len(body["top"]) == 10
    assert body["diversity_min_pairwise"] > 0
    assert body["ranking_config_version"] == "0.1.0"
    top = body["top"][0]
    assert top["score_breakdown"]["dimensions"]["manufacturability"]["weight"] == 25.0

    # 6. Candidate preview SVG.
    cid = top["candidate_id"]
    r = client.get(f"/api/designs/{design_id}/candidates/{cid}/svg")
    assert r.status_code == 200
    assert ET.fromstring(r.text).attrib["width"].endswith("mm")

    # 7. Select → Design + version 1.
    r = client.post(f"/api/designs/{design_id}/select", json={"candidate_id": cid})
    assert r.status_code == 201
    sel = r.json()
    version_id = sel["version_id"]
    assert sel["version_number"] == 1 and sel["status"] == "UNAPPROVED"

    # 8. Production export before approval is blocked.
    assert client.get(f"/api/versions/{version_id}/export/dxf").status_code == 423

    # 9. Approve with exact text + hashes → immutable lock.
    r = client.post(
        f"/api/versions/{version_id}/approve",
        json={
            "confirmed_text": "ميثة",
            "source_text_sha256": sel["source_text_sha256"],
            "geometry_hash": sel["geometry_hash"],
            "approved_by": "customer-e2e",
        },
    )
    assert r.status_code == 201
    approval = r.json()
    assert approval["version_status"] == "APPROVED_LOCKED"
    assert len(approval["approval_hash"]) == 64

    # 10. Approved version exports SVG + DXF (mm, closed polylines).
    r = client.get(f"/api/versions/{version_id}/export/svg")
    assert r.status_code == 200 and "X-Content-Sha256" in r.headers
    r = client.get(f"/api/versions/{version_id}/export/dxf")
    assert r.status_code == 200
    doc = ezdxf.read(io.StringIO(r.text))
    assert doc.header["$INSUNITS"] == 4
    assert all(pl.closed for pl in doc.modelspace().query("LWPOLYLINE"))

    # 11. Idempotent export replay.
    h = {"Idempotency-Key": "e2e-1"}
    first = client.get(f"/api/versions/{version_id}/export/dxf", headers=h)
    replay = client.get(f"/api/versions/{version_id}/export/dxf", headers=h)
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["content_sha256"] == first.headers["X-Content-Sha256"]

    # 12. Edit after lock → new unapproved version; old lock intact.
    r = client.post(
        f"/api/versions/{version_id}/edit",
        json={"recipe_overrides": {"stroke_delta_mm": 0.4}, "note": "bolder"},
    )
    assert r.status_code == 201
    v2 = r.json()
    assert v2["version_number"] == 2 and v2["status"] == "UNAPPROVED"
    assert client.get(f"/api/versions/{v2['version_id']}/export/dxf").status_code == 423
    assert client.get(f"/api/versions/{version_id}").json()["status"] == "APPROVED_LOCKED"

    # 13. Audit trail covers the lifecycle.
    events = [e["event_type"] for e in client.get(f"/api/designs/{design_id}/events").json()]
    for expected in [
        "REQUEST_CREATED", "TEXT_CONFIRMED", "CANDIDATES_GENERATED",
        "DESIGN_SELECTED", "VERSION_CREATED", "CUSTOMER_APPROVED",
        "VERSION_LOCKED", "PRODUCTION_EXPORT_CREATED", "DESIGN_EDITED",
    ]:
        assert expected in events, f"missing {expected}"


def test_invalid_candidate_cannot_be_selected(client):
    r = client.post("/api/designs", json={"text": "مريم"})
    design_id = r.json()["design_id"]
    client.headers.update({"X-Session-Token": r.json()["session_token"]})
    client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "مريم"})
    client.post(f"/api/designs/{design_id}/candidates")
    rows = client.get(
        f"/api/designs/{design_id}/candidates", params={"include_invalid": True}
    ).json()
    failed = [r_ for r_ in rows if not r_["validation_passed"]]
    assert failed, "expected blocked candidates in pool"
    r = client.post(
        f"/api/designs/{design_id}/select", json={"candidate_id": failed[0]["candidate_id"]}
    )
    assert r.status_code == 409


def test_font_registry_endpoint(client):
    fonts = client.get("/api/fonts").json()
    assert len(fonts) >= 3
    for f in fonts:
        assert f["rights_status"] == "VERIFIED_OPEN_SOURCE"
        assert f["commercial_production_allowed"] is True


def test_english_golden_path(client):
    r = client.post("/api/designs", json={"text": "Amal"})
    design_id = r.json()["design_id"]
    client.headers.update({"X-Session-Token": r.json()["session_token"]})
    client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "Amal"})
    r = client.post(f"/api/designs/{design_id}/candidates")
    assert len(r.json()["top"]) == 10
