"""Jewelry Manufacturing Gate: PDF export, Export Fidelity Gate, JEWELRY
QA report, readiness ladder (facts, not declarations)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from shapely import affinity, wkt

from app.exporters import fidelity as fid
from app.exporters.dxf_exporter import export_dxf
from app.exporters.pdf_exporter import export_pdf
from app.exporters.svg_exporter import export_svg
from app.main import app
from app.services import design_service as svc

TEXT = "ميثه"


def _approved_version(session, text=TEXT):
    req = svc.create_request(session, text, "pendant")
    svc.confirm_request_text(session, req.id, text)
    result = svc.generate_and_persist_candidates(session, req.id)
    _, v = svc.select_candidate(session, req.id, result["top"][0].candidate_id)
    session.flush()
    return req, v


def test_pdf_export_is_true_scale_vector_and_reimports(clean_tables, db_session):
    _, v = _approved_version(db_session)
    candidate, source = svc._version_to_candidate(v)
    pdf = export_pdf(candidate, source, version_id=str(v.id), geometry_hash=v.geometry_hash)
    assert pdf.startswith(b"%PDF") and source.sha256.encode() in pdf
    master = wkt.loads(v.geometry_wkt)
    for fmt, geom in (("svg", fid.reimport_svg(export_svg(candidate, source))),
                      ("dxf", fid.reimport_dxf(export_dxf(candidate, source))),
                      ("pdf", fid.reimport_pdf(pdf))):
        verdict = fid.compare(master, geom)
        assert verdict["status"] == "PASS", (fmt, verdict)
    # a scaled re-import must fail the gate
    tampered = affinity.scale(master, 1.01, 1.01, origin=(0, 0))
    bad = fid.compare(master, tampered)
    assert bad["status"] == "FAIL" and any(c["check"] == "dimensions_mm" and c["status"] == "FAIL" for c in bad["checks"])


def test_export_records_carry_fidelity_and_manifest_and_ladder_reaches_workshop_ready(clean_tables, db_session):
    from app.services.readiness_ladder import ladder

    req, v = _approved_version(db_session)
    before = ladder(db_session, v)
    assert before["current_state"] == "CUSTOMER_READY"
    assert [r["state"] for r in before["rungs"]][:2] == ["DRAFT", "TEXT_VERIFIED"]
    assert before["rungs"][1]["text_integrity"] == "TEXT INTEGRITY: PASS"
    assert not before["rungs"][5]["reached"]
    svc.approve_version(db_session, v.id, confirmed_text=TEXT, source_text_sha256=v.source_text_sha256,
                        geometry_hash=v.geometry_hash, approved_by="customer")
    db_session.flush()
    mid = ladder(db_session, v)
    assert mid["current_state"] == "CUSTOMER_APPROVED" and mid["rungs"][5]["approval_channel"] == "INTERNAL_UI"
    for fmt in ("svg", "dxf", "pdf"):
        content, record = svc.export_version(db_session, v.id, fmt, idempotency_key=f"t-{fmt}-{v.id}")
        assert record.fidelity["status"] == "PASS", (fmt, record.fidelity)
        assert record.manifest["source_text"] == TEXT and record.manifest["source_text_sha256"] == v.source_text_sha256
        assert record.manifest["codepoints"] == ["U+0645", "U+064A", "U+062B", "U+0647"]
    after = ladder(db_session, v)
    assert after["current_state"] == "WORKSHOP_READY"
    assert after["rungs"][6]["exports"] == {"svg": "PASS", "dxf": "PASS", "pdf": "PASS"}


def test_jewelry_qa_report_speaks_plain_language(clean_tables, db_session):
    from app.services.jewelry_qa import jewelry_qa_report

    _, v = _approved_version(db_session)
    r = jewelry_qa_report(v, material_id="gold-18k-yellow", thickness_mm=1.0, target_weight_g=3.0)
    assert r["label"] in ("JEWELRY QA: PASS", "JEWELRY QA: FAIL")
    assert r["status"] == "PASS" and r["weight"]["basis"] == "ACTUAL_AREA_X_THICKNESS_X_DENSITY"
    assert r["attachment"]["real_geometry"] is True and r["attachment"]["expected_rings"] >= 1
    assert r["summary_ar"] and r["summary_en"]
    fake = type("V", (), {})()
    fake.validation = {"violations": [{"code": "WEAK_BRIDGE", "severity": "ERROR", "detail": "x"}], "rules_profile": "p"}
    fake.validation_passed = False; fake.identity_verified = True; fake.geometry_wkt = v.geometry_wkt; fake.recipe = v.recipe
    bad = jewelry_qa_report(fake)
    assert bad["status"] == "FAIL" and "break" in bad["errors"][0]["explanation_en"] and bad["errors"][0]["explanation_ar"]


def test_gate_endpoints(clean_tables, db_session):
    with TestClient(app) as c:
        created = c.post("/api/designs", json={"text": TEXT, "product_type": "pendant"}).json()
        h = {"X-Session-Token": created["session_token"]}
        did = created["design_id"]
        c.post(f"/api/designs/{did}/confirm", json={"confirmed_text": TEXT}, headers=h)
        gen = c.post(f"/api/designs/{did}/candidates", headers=h).json()
        sel = c.post(f"/api/designs/{did}/select", json={"candidate_id": gen["top"][0]["candidate_id"]}, headers=h).json()
        vid = sel["version_id"]
        qa = c.get(f"/api/versions/{vid}/jewelry-qa", params={"material": "gold-18k-yellow"}, headers=h)
        assert qa.status_code == 200 and qa.json()["label"].startswith("JEWELRY QA:")
        integ = c.get(f"/api/versions/{vid}/integrity", headers=h).json()
        assert integ["label"] == "TEXT INTEGRITY: PASS"
        assert c.get(f"/api/versions/{vid}/export/pdf", headers=h).status_code == 423   # not approved yet
        c.post(f"/api/versions/{vid}/approve", json={"confirmed_text": TEXT, "source_text_sha256": sel["source_text_sha256"],
                                                    "geometry_hash": sel["geometry_hash"], "approved_by": "customer"}, headers=h)
        r = c.get(f"/api/versions/{vid}/export/pdf", headers=h)
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.headers["X-Export-Fidelity"] == "PASS"
        for fmt in ("svg", "dxf"):
            assert c.get(f"/api/versions/{vid}/export/{fmt}", headers=h).headers["X-Export-Fidelity"] == "PASS"
        ex = c.get(f"/api/versions/{vid}/exports", headers=h).json()["exports"]
        assert {e["format"] for e in ex} == {"svg", "dxf", "pdf"} and all(e["fidelity"]["status"] == "PASS" for e in ex)
        ready = c.get(f"/api/versions/{vid}/readiness", headers=h).json()
        assert ready["current_state"] == "WORKSHOP_READY"
