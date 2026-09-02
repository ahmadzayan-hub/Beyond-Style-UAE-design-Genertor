"""Workshop OS: state machine, delivery completion, production pack."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import models as m
from app.services import design_service as svc
from app.services import workshop_service as ws


def _approved_version(session, text="ميثة", product="pendant"):
    req = svc.create_request(session, text, product)
    svc.confirm_request_text(session, req.id, text)
    result = svc.generate_and_persist_candidates(session, req.id)
    _, v = svc.select_candidate(session, req.id, result["top"][0].candidate_id)
    session.flush()
    svc.approve_version(session, v.id, confirmed_text=text, source_text_sha256=v.source_text_sha256,
                        geometry_hash=v.geometry_hash, approved_by="customer")
    session.flush()
    return v


def test_unapproved_version_cannot_enter_the_workshop(clean_tables, db_session):
    req = svc.create_request(db_session, "ميثة", "pendant")
    svc.confirm_request_text(db_session, req.id, "ميثة")
    result = svc.generate_and_persist_candidates(db_session, req.id)
    _, v = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    db_session.flush()
    with pytest.raises(ws.WorkshopError):
        ws.create_order(db_session, v.id, material="silver-925", actor="admin")


def test_state_machine_never_skips_and_rework_loops(clean_tables, db_session):
    v = _approved_version(db_session)
    order = ws.create_order(db_session, v.id, material="silver-925", actor="admin")
    assert order.state == "NEW"
    with pytest.raises(ws.WorkshopError):
        ws.transition(db_session, order, "MANUFACTURING", actor="s")  # skip attempt
    for s in ("DESIGN_REVIEW", "TECHNICAL_CHECK", "APPROVED", "MANUFACTURING", "QC"):
        ws.transition(db_session, order, s, actor="s")
    ws.transition(db_session, order, "REWORK", actor="qc", note="scratch on face")
    assert order.rework_count == 1
    with pytest.raises(ws.WorkshopError):
        ws.transition(db_session, order, "READY", actor="s")  # rework must go back to manufacturing
    ws.transition(db_session, order, "MANUFACTURING", actor="s")
    ws.transition(db_session, order, "QC", actor="s")
    ws.transition(db_session, order, "READY", actor="s")
    assert [h["state"] for h in order.history][:3] == ["NEW", "DESIGN_REVIEW", "TECHNICAL_CHECK"]


def test_delivery_requires_receiver_staff_and_date(clean_tables, db_session):
    v = _approved_version(db_session)
    order = ws.create_order(db_session, v.id, material="silver-925", actor="admin")
    for s in ("DESIGN_REVIEW", "TECHNICAL_CHECK", "APPROVED", "MANUFACTURING", "QC", "READY"):
        ws.transition(db_session, order, s, actor="s")
    with pytest.raises(ws.WorkshopError):
        ws.transition(db_session, order, "DELIVERED", actor="s", receiver_name="Aisha")
    ws.transition(db_session, order, "DELIVERED", actor="s", receiver_name="Aisha",
                  staff_number="BS-017", actual_received_date=date(2026, 9, 1))
    assert order.state == "DELIVERED" and order.delivered_at is not None
    assert order.actual_received_date == date(2026, 9, 1)
    events = [e for e in db_session.query(m.DesignEvent).all() if e.event_type == "WORKSHOP_STATE_CHANGED"]
    assert any(e.event_metadata.get("to") == "DELIVERED" for e in events)


def test_production_pack_is_bound_to_the_approved_hash(clean_tables, db_session):
    v = _approved_version(db_session)
    order = ws.create_order(db_session, v.id, material="silver-925", actor="admin")
    pack = ws.production_pack(db_session, order)
    approval = db_session.query(m.CustomerApproval).filter_by(design_version_id=v.id).one()
    assert pack["approval_hash"] == approval.approval_hash
    assert pack["exact_text"] == "ميثة"
    assert pack["geometry_hash"] == v.geometry_hash
    assert pack["artifacts"]["svg"]["sha256"] and pack["artifacts"]["dxf"]["sha256"]
    assert "<svg" in pack["artifacts"]["svg"]["content"]
    assert pack["tolerances"]["kerf_mm"] is not None
    assert pack["bom"][0]["estimated_metal_weight_g"] is not None
    assert "laser_cut_sheet" in pack["process"]


def test_ring_pack_lists_engraving_process(clean_tables, db_session):
    from app.services.intake_service import upsert_brief

    req = svc.create_request(db_session, "أنت القصة\nعائشة وحسن", "ring")
    svc.confirm_request_text(db_session, req.id, "أنت القصة\nعائشة وحسن")
    upsert_brief(db_session, req.id, product_type="ring", ring_size_eu=52)
    result = svc.generate_and_persist_candidates(db_session, req.id)
    _, v = svc.select_candidate(db_session, req.id, result["top"][0].candidate_id)
    db_session.flush()
    svc.approve_version(db_session, v.id, confirmed_text="أنت القصة\nعائشة وحسن",
                        source_text_sha256=v.source_text_sha256, geometry_hash=v.geometry_hash,
                        approved_by="customer")
    order = ws.create_order(db_session, v.id, material="gold-18k-yellow", actor="admin")
    pack = ws.production_pack(db_session, order)
    assert "engrave_inner_face_mirrored" in pack["process"]
    assert pack["dimensions_mm"]["ring"]["size_eu"] == 52
    assert "ENGRAVE_INNER" in pack["artifacts"]["dxf"]["content"]


def test_workshop_api_is_admin_only(clean_tables, db_session, monkeypatch):
    from app.api import admin
    from app.main import app

    monkeypatch.setattr(admin, "ADMIN_API_TOKEN", "admin-secret")
    monkeypatch.setattr(admin, "REVIEWER_API_TOKEN", "reviewer-secret")
    with TestClient(app) as c:
        assert c.get("/api/workshop/states").status_code == 403
        assert c.get("/api/workshop/states", headers={"X-Admin-Token": "reviewer-secret"}).status_code == 403
        r = c.get("/api/workshop/states", headers={"X-Admin-Token": "admin-secret"})
        assert r.status_code == 200 and r.json()["states"][0] == "NEW"
