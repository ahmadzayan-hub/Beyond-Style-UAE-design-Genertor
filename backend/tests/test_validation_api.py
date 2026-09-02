"""Public customer-validation API + admin confirm-text route.

Both exist so the owner can collect real evidence (customer reactions,
confirmed order text) without a developer in the loop — and must stay
honest: anonymous votes are rate-limited and bound to the live pack, and
OCR can never supply a golden case's source text.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import admin, validation
from app.db import models as m
from app.main import app
from app.security.sessions import RateLimiter
from app.services.golden_memory import seed_golden_cases

ARABIC_CASE = "BS-GPC-0001-arabic-letter-pearl-earrings"


@pytest.fixture
def client(clean_tables, monkeypatch):
    monkeypatch.setattr(validation, "VOTE_LIMITER", RateLimiter(60, 600))
    # The pack is deterministic; one build per test module keeps the run fast
    # while the TTL path itself is covered below.
    with TestClient(app) as c:
        yield c


def _vote(pack, item_id, token="respondent-token-1", **over):
    body = {
        "pack_id": pack["pack_id"], "item_id": item_id, "respondent_token": token,
        "would_buy": "YES", "premium_feel": 4, "readability": 5, "uniqueness": 4,
    }
    body.update(over)
    return body


def test_public_pack_strips_engineering_metadata(client):
    r = client.get("/api/validation/pack")
    assert r.status_code == 200
    pack = r.json()
    assert pack["size"] == len(pack["items"]) > 0
    for item in pack["items"]:
        assert "engineering" not in item and "ranking" not in item
        assert item["proof_path_d"] and item["proof_view"]
        assert item["width_mm"] > 0 and item["height_mm"] > 0


def test_vote_is_recorded_and_token_is_stored_hashed(client, db_session):
    pack = client.get("/api/validation/pack").json()
    item_id = pack["items"][0]["item_id"]
    r = client.post("/api/validation/response", json=_vote(pack, item_id))
    assert r.status_code == 201, r.text
    row = db_session.execute(select(m.CustomerValidationResponse)).scalar_one()
    assert row.item_id == item_id
    assert "respondent-token-1" not in (row.respondent_token or "")


def test_vote_outside_current_pack_and_honeypot_are_rejected(client):
    pack = client.get("/api/validation/pack").json()
    item_id = pack["items"][0]["item_id"]
    r = client.post("/api/validation/response", json=_vote(pack, "not-in-pack"))
    assert r.status_code == 422
    r = client.post("/api/validation/response", json=_vote(pack, item_id, website="http://spam"))
    assert r.status_code == 422
    r = client.post("/api/validation/response", json=_vote(pack, item_id, premium_feel=9))
    assert r.status_code == 422


def test_votes_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(validation, "VOTE_LIMITER", RateLimiter(2, 600))
    pack = client.get("/api/validation/pack").json()
    items = [i["item_id"] for i in pack["items"]]
    codes = [
        client.post("/api/validation/response",
                    json=_vote(pack, items[n % len(items)], token=f"tok-{n}-abcdef")).status_code
        for n in range(3)
    ]
    assert codes[:2] == [201, 201] and codes[2] == 429


def test_confirm_text_route_is_admin_only_and_rejects_ocr(client, db_session, monkeypatch):
    monkeypatch.setattr(admin, "ADMIN_API_TOKEN", "admin-secret")
    monkeypatch.setattr(admin, "REVIEWER_API_TOKEN", "reviewer-secret")
    db_session.execute(m.GoldenProductionCase.__table__.delete())
    seed_golden_cases(db_session)
    db_session.commit()
    url = f"/api/admin/golden-cases/{ARABIC_CASE}/confirm-text"
    body = {"text": "مي", "authority": "ORDER_RECORD", "order_reference": "INV-1042"}
    assert client.post(url, json=body).status_code == 403
    assert client.post(url, json=body, headers={"X-Admin-Token": "reviewer-secret"}).status_code == 403
    hdr = {"X-Admin-Token": "admin-secret"}
    assert client.post("/api/admin/golden-cases/nope/confirm-text", json=body, headers=hdr).status_code == 404
    assert client.post(url, json={**body, "authority": "OCR"}, headers=hdr).status_code == 422
    r = client.post(url, json=body, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["source_text_status"] == "CONFIRMED"
    assert r.json()["order_reference"] == "INV-1042"
    db_session.expire_all()
    case = db_session.execute(
        select(m.GoldenProductionCase).where(m.GoldenProductionCase.case_id == ARABIC_CASE)
    ).scalar_one()
    assert case.source_text_status == "CONFIRMED"


def test_pack_is_cached_per_process_and_votes_never_rebuild_it(client, monkeypatch):
    calls = {"n": 0}
    real = validation._build_pack

    def counting(session):
        calls["n"] += 1
        return real(session)

    monkeypatch.setattr(validation, "_build_pack", counting)
    validation.reset_pack_cache()
    pack = client.get("/api/validation/pack").json()
    client.get("/api/validation/pack")
    client.post("/api/validation/response", json=_vote(pack, pack["items"][0]["item_id"], token="cache-tok-1"))
    assert calls["n"] == 1
    monkeypatch.setattr(validation, "PACK_TTL_S", 0.0)
    client.get("/api/validation/pack")
    assert calls["n"] == 2
