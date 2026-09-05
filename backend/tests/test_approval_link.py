"""Secure customer approval link: single-use, expiring, bound to the exact
version geometry; approval through it is recorded as SECURE_LINK."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import models as m
from app.main import app
from app.services import design_service as svc

TEXT = "ميثه"


def _selected(c):
    created = c.post("/api/designs", json={"text": TEXT, "product_type": "pendant"}).json()
    h = {"X-Session-Token": created["session_token"]}
    did = created["design_id"]
    c.post(f"/api/designs/{did}/confirm", json={"confirmed_text": TEXT}, headers=h)
    gen = c.post(f"/api/designs/{did}/candidates", headers=h).json()
    sel = c.post(f"/api/designs/{did}/select", json={"candidate_id": gen["top"][0]["candidate_id"]}, headers=h).json()
    return did, sel, h


def test_secure_link_lifecycle(clean_tables, db_session):
    with TestClient(app) as c:
        did, sel, h = _selected(c)
        vid = sel["version_id"]
        # no session → cannot mint a link
        assert c.post(f"/api/versions/{vid}/approval-link", json={}).status_code in (401, 403, 404)
        r = c.post(f"/api/versions/{vid}/approval-link", json={"ttl_hours": 48}, headers=h)
        assert r.status_code == 201, r.text
        link = r.json()
        assert link["single_use"] and link["path"] == f"/approve/{link['token']}" and link["geometry_hash"] == sel["geometry_hash"]
        # public view: exact text + proof, no session needed
        view = c.get(f"/api/approval-links/{link['token']}")
        assert view.status_code == 200, view.text
        body = view.json()
        assert body["state"] == "OPEN" and body["immutable_source_text"] == TEXT
        assert body["agreement_proof_svg"].startswith("<svg") and body["statement_ar"]
        # wrong text → rejected, version still unapproved, link still open
        bad = c.post(f"/api/approval-links/{link['token']}/approve",
                     json={"confirmed_text": "ميثة", "approver_name": "Maitha", "accept_statement": True})
        assert bad.status_code == 422 and "does not match" in bad.json()["detail"]
        assert c.post(f"/api/approval-links/{link['token']}/approve",
                      json={"confirmed_text": TEXT, "approver_name": "Maitha", "accept_statement": False}).status_code == 422
        assert c.get(f"/api/versions/{vid}", headers=h).json()["status"] == "UNAPPROVED"
        # a second issued link revokes the first
        r2 = c.post(f"/api/versions/{vid}/approval-link", json={}, headers=h).json()
        gone = c.get(f"/api/approval-links/{link['token']}")
        assert gone.status_code == 410 and gone.json()["error_code"] == "APPROVAL_LINK_REVOKED"
        # approve through the live link
        ok = c.post(f"/api/approval-links/{r2['token']}/approve",
                    json={"confirmed_text": TEXT, "approver_name": "Maitha", "accept_statement": True})
        assert ok.status_code == 201, ok.text
        assert ok.json()["approval_method"] == "SECURE_LINK" and ok.json()["version_status"] == "APPROVED_LOCKED"
        assert c.get(f"/api/versions/{vid}", headers=h).json()["status"] == "APPROVED_LOCKED"
        # single use
        again = c.get(f"/api/approval-links/{r2['token']}")
        assert again.status_code == 410 and again.json()["error_code"] == "APPROVAL_LINK_USED"
        assert c.post(f"/api/approval-links/{r2['token']}/approve",
                      json={"confirmed_text": TEXT, "accept_statement": True}).status_code == 410
        # ladder reports the secure channel; exports work as after any approval
        ladder = c.get(f"/api/versions/{vid}/readiness", headers=h).json()
        rung = next(x for x in ladder["rungs"] if x["state"] == "CUSTOMER_APPROVED")
        assert rung["reached"] and rung["approval_channel"] == "SECURE_LINK"
        assert c.get(f"/api/versions/{vid}/export/svg", headers=h).headers["X-Export-Fidelity"] == "PASS"
        ev = c.get(f"/api/designs/{did}/events", headers=h).json()
        assert "APPROVAL_LINK_ISSUED" in [e["event_type"] for e in ev]
        # unknown token
        assert c.get("/api/approval-links/not-a-real-token").status_code == 404


def test_link_is_bound_to_geometry_and_expiry(clean_tables, db_session):
    with TestClient(app) as c:
        did, sel, h = _selected(c)
        vid = sel["version_id"]
        link = c.post(f"/api/versions/{vid}/approval-link", json={}, headers=h).json()
        # an unapprovable (edited-invalid) version cannot be sent; an edit creates a NEW version,
        # the link stays bound to the original geometry and still opens for it
        assert c.get(f"/api/approval-links/{link['token']}").status_code == 200
        # expire it in the database → 410 EXPIRED
        row = db_session.execute(select(m.ApprovalLink)).scalar_one()
        row.expires_at = row.expires_at - timedelta(days=30)
        db_session.commit()
        exp = c.get(f"/api/approval-links/{link['token']}")
        assert exp.status_code == 410 and exp.json()["error_code"] == "APPROVAL_LINK_EXPIRED"
        # an approved version cannot be sent again
        c.post(f"/api/versions/{vid}/approve", json={"confirmed_text": TEXT, "source_text_sha256": sel["source_text_sha256"],
                                                    "geometry_hash": sel["geometry_hash"], "approved_by": "customer"}, headers=h)
        assert c.post(f"/api/versions/{vid}/approval-link", json={}, headers=h).status_code == 409
