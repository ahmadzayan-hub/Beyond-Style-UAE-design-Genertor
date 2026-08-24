"""End-to-end API golden path: create → confirm → generate → SVG/DXF."""
import io
import xml.etree.ElementTree as ET

import ezdxf
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_golden_path_arabic():
    # 1. Create with exact Arabic text.
    r = client.post("/api/designs", json={"text": "ميثة"})
    assert r.status_code == 201
    design_id = r.json()["design_id"]
    assert r.json()["requires_confirmation"] is True

    # 2. Generation before confirmation is refused.
    r = client.post(f"/api/designs/{design_id}/candidates")
    assert r.status_code == 409

    # 3. Wrong confirmation text is rejected (source text immutable).
    r = client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "ميثه"})
    assert r.status_code == 422

    # 4. Exact confirmation accepted.
    r = client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "ميثة"})
    assert r.status_code == 200

    # 5. Generate: ≥30 internal, top 10 diverse.
    r = client.post(f"/api/designs/{design_id}/candidates")
    assert r.status_code == 200
    body = r.json()
    assert body["internal_candidate_count"] >= 30
    assert len(body["top"]) == 10
    assert body["diversity_min_pairwise"] > 0
    for c in body["top"]:
        assert c["source_text_sha256"]  # traceability on every option

    # 6. SVG export of top candidate.
    cid = body["top"][0]["candidate_id"]
    r = client.get(f"/api/designs/{design_id}/candidates/{cid}/svg")
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    assert root.attrib["width"].endswith("mm")

    # 7. DXF export: valid, mm, closed polylines.
    r = client.get(f"/api/designs/{design_id}/candidates/{cid}/dxf")
    assert r.status_code == 200
    doc = ezdxf.read(io.StringIO(r.text))
    assert doc.header["$INSUNITS"] == 4
    assert all(pl.closed for pl in doc.modelspace().query("LWPOLYLINE"))

    # 8. Design state reflects immutable source text.
    r = client.get(f"/api/designs/{design_id}")
    data = r.json()
    assert data["source_text"]["normalized_text"] == "ميثة"
    assert data["source_text"]["confirmed"] is True


def test_dxf_blocked_for_invalid_candidate():
    r = client.post("/api/designs", json={"text": "مريم"})
    design_id = r.json()["design_id"]
    client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "مريم"})
    client.post(f"/api/designs/{design_id}/candidates")
    # Find a blocked internal candidate via validation endpoint.
    r = client.get(f"/api/designs/{design_id}")
    # use internal candidates: query validations of top first; fetch full design store
    from app.api.designs import _DESIGNS

    failed = [
        c for c in _DESIGNS[design_id].candidates
        if c.validation and not c.validation.passed
    ]
    assert failed
    r = client.get(f"/api/designs/{design_id}/candidates/{failed[0].candidate_id}/dxf")
    assert r.status_code == 423  # BLOCK_PRODUCTION_EXPORT


def test_font_registry_endpoint():
    r = client.get("/api/fonts")
    assert r.status_code == 200
    fonts = r.json()
    assert len(fonts) >= 3
    for f in fonts:
        assert f["rights_status"] == "VERIFIED_OPEN_SOURCE"
        assert f["commercial_production_allowed"] is True


def test_english_golden_path():
    r = client.post("/api/designs", json={"text": "Amal"})
    design_id = r.json()["design_id"]
    client.post(f"/api/designs/{design_id}/confirm", json={"confirmed_text": "Amal"})
    r = client.post(f"/api/designs/{design_id}/candidates")
    assert len(r.json()["top"]) == 10
