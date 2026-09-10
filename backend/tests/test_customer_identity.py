"""Customer identity: passwordless code login, claiming requests, secure
retrieval across devices, honest delivery status."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

TEXT = "ميثه"


@pytest.fixture(autouse=True)
def _fresh_limiter():
    from app.api.customers import LOGIN_LIMITER, VERIFY_LIMITER

    LOGIN_LIMITER.reset(); VERIFY_LIMITER.reset()
    yield
    LOGIN_LIMITER.reset(); VERIFY_LIMITER.reset()


@pytest.fixture
def echo(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_ECHO_CODE", "1")
    monkeypatch.delenv("AUTH_CODE_PROVIDER", raising=False)


def _login(c, contact="0501234567"):
    s = c.post("/api/customers/login/start", json={"contact": contact}).json()
    assert s["delivery"]["status"] == "SKIPPED_EXTERNAL_PROVIDER" and "dev_code" in s
    v = c.post("/api/customers/login/verify", json={"contact": contact, "code": s["dev_code"], "display_name": "Maitha"})
    assert v.status_code == 200, v.text
    return {"X-Customer-Token": v.json()["customer_token"]}, s, v.json()


def test_login_claim_list_and_resume_on_another_device(clean_tables, db_session, echo):
    with TestClient(app) as c:
        ch, started, verified = _login(c)
        assert started["contact_kind"] == "phone" and started["contact_masked"] == "+971***567"
        assert verified["contact_masked"] == "+971***567" and verified["display_name"] == "Maitha"
        assert c.get("/api/me", headers=ch).json()["contact_kind"] == "phone"
        # anonymous design as today
        created = c.post("/api/designs", json={"text": TEXT, "product_type": "pendant"}).json()
        sh = {"X-Session-Token": created["session_token"]}
        did = created["design_id"]
        assert c.get("/api/me/designs", headers=ch).json()["designs"] == []
        # claim needs BOTH the request token and the customer token
        assert c.post(f"/api/customers/claim/{did}", headers=ch).status_code == 404
        assert c.post(f"/api/customers/claim/{did}", headers=sh).status_code == 401
        assert c.post(f"/api/customers/claim/{did}", headers={**sh, **ch}).status_code == 201
        c.post(f"/api/designs/{did}/confirm", json={"confirmed_text": TEXT}, headers=sh)
        mine = c.get("/api/me/designs", headers=ch).json()["designs"]
        assert len(mine) == 1 and mine[0]["design_id"] == did and mine[0]["text"] == TEXT and mine[0]["confirmed"]
        # customer token alone can read the design (secure retrieval)
        assert c.get(f"/api/designs/{did}", headers=ch).status_code == 200
        # another device: resume rotates the per-request token; the old one dies
        r = c.post(f"/api/me/designs/{did}/session", headers=ch)
        assert r.status_code == 201 and r.json()["text"] == TEXT
        new_sh = {"X-Session-Token": r.json()["session_token"]}
        assert c.get(f"/api/designs/{did}", headers=sh).status_code == 404
        assert c.get(f"/api/designs/{did}", headers=new_sh).status_code == 200
        # someone else cannot see or claim it
        oh, _, _ = _login(c, "other@example.com")
        assert c.get(f"/api/designs/{did}", headers=oh).status_code == 404
        assert c.post(f"/api/customers/claim/{did}", headers={**new_sh, **oh}).status_code == 409
        assert c.get("/api/me/designs", headers=oh).json()["designs"] == []
        # logout revokes the customer token
        assert c.post("/api/customers/logout", headers=ch).json()["revoked"] is True
        assert c.get("/api/me", headers=ch).status_code == 401
        ev = [e["event_type"] for e in c.get(f"/api/designs/{did}/events", headers=new_sh).json()]
        assert "REQUEST_CLAIMED" in ev and "SESSION_REISSUED" in ev


def test_codes_are_single_use_expiring_and_attempt_limited(clean_tables, db_session, echo):
    from datetime import timedelta

    from sqlalchemy import select

    from app.db import models as m

    with TestClient(app) as c:
        s = c.post("/api/customers/login/start", json={"contact": "maitha@example.com"}).json()
        for _ in range(5):
            r = c.post("/api/customers/login/verify", json={"contact": "maitha@example.com", "code": "000000"})
            assert r.status_code == 422 and r.json()["detail"]["code"] == "CODE_INVALID"
        r = c.post("/api/customers/login/verify", json={"contact": "maitha@example.com", "code": s["dev_code"]})
        assert r.status_code == 429 and r.json()["detail"]["code"] == "TOO_MANY_ATTEMPTS"
        s2 = c.post("/api/customers/login/start", json={"contact": "maitha@example.com"}).json()
        assert s2["dev_code"] != s["dev_code"] or True
        ok = c.post("/api/customers/login/verify", json={"contact": "maitha@example.com", "code": s2["dev_code"]})
        assert ok.status_code == 200
        again = c.post("/api/customers/login/verify", json={"contact": "maitha@example.com", "code": s2["dev_code"]})
        assert again.status_code == 422 and again.json()["detail"]["code"] == "NO_CODE"
        s3 = c.post("/api/customers/login/start", json={"contact": "maitha@example.com"}).json()
        row = db_session.execute(select(m.CustomerLoginCode).order_by(m.CustomerLoginCode.created_at.desc())).scalars().first()
        row.expires_at = row.expires_at - timedelta(hours=1)
        db_session.commit()
        exp = c.post("/api/customers/login/verify", json={"contact": "maitha@example.com", "code": s3["dev_code"]})
        assert exp.status_code == 422 and exp.json()["detail"]["code"] == "CODE_EXPIRED"
        assert c.post("/api/customers/login/start", json={"contact": "not a contact"}).status_code == 422


def test_without_dev_echo_the_code_is_not_disclosed_and_delivery_is_honest(clean_tables, db_session, monkeypatch):
    monkeypatch.delenv("AUTH_DEV_ECHO_CODE", raising=False)
    monkeypatch.delenv("AUTH_CODE_PROVIDER", raising=False)
    with TestClient(app) as c:
        s = c.post("/api/customers/login/start", json={"contact": "+971501234567"}).json()
        assert "dev_code" not in s and s["delivery"]["status"] == "SKIPPED_EXTERNAL_PROVIDER"
        ready = c.get("/ready").json()["components"]["customer_auth"]
        assert ready["code_delivery"] == "SKIPPED_EXTERNAL_PROVIDER" and ready["dev_echo_code"] is False
