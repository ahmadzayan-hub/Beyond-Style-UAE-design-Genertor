"""Design Jury, confidence engine, taste memory, lineage, product skills,
shadow evaluation. Real Claude calls SKIP honestly without credentials."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai import quality_layer as ql
from app.ai.llm import LLMUnavailable
from app.ai.product_skills import PRODUCT_SKILLS, load_skill
from app.db import models as m
from app.main import app
from app.services import design_service as svc
from tests.test_persistence_lifecycle import _full_flow


@pytest.fixture
def client(clean_tables):
    from app.security.sessions import GENERATE_LIMITER, UPLOAD_LIMITER

    UPLOAD_LIMITER.reset()
    GENERATE_LIMITER.reset()
    with TestClient(app) as c:
        yield c


def _new_session(client, text="ميثة"):
    r = client.post("/api/designs", json={"text": text})
    return r.json()["design_id"], {"X-Session-Token": r.json()["session_token"]}


def _selected_version(client, text="ميثة"):
    design_id, h = _new_session(client, text)
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": text})
    top = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()["top"]
    sel = client.post(f"/api/designs/{design_id}/select", headers=h,
                      json={"candidate_id": top[0]["candidate_id"]}).json()
    return design_id, h, sel


# --------------------------------------------------------------- Design Jury


def test_jury_skips_honestly_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(LLMUnavailable):
        ql.run_design_jury({"product_type": "pendant"})


def test_jury_endpoint_reports_skipped_not_fake_pass(client):
    design_id, h, sel = _selected_version(client)
    r = client.post(f"/api/visual/versions/{sel['version_id']}/jury", headers=h, json={})
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "SKIPPED_EXTERNAL_MODEL"  # never a fabricated PASS
    assert "reason" in body


def test_jury_verdict_overall_weighting():
    v = ql.DesignJuryVerdict(
        arabic_art=ql.JuryScore(score=1.0, explanation="x"),
        jewellery_aesthetic=ql.JuryScore(score=1.0, explanation="x"),
        manufacturing=ql.JuryScore(score=0.0, explanation="x"),
        customer_fit=ql.JuryScore(score=0.0, explanation="x"),
    )
    assert v.overall == pytest.approx(0.6)  # 0.3+0.3 arabic+aesthetic only


# ------------------------------------------------------------ confidence


def test_confidence_flags_human_review_on_low_dimension():
    ok = ql.compute_confidence(identity_verified=True, validation_passed=True)
    assert not ok.requires_human_review
    bad = ql.compute_confidence(identity_verified=False, validation_passed=True)
    assert bad.requires_human_review and bad.arabic_confidence == 0.0
    assert "Arabic identity not verified" in bad.reasons


def test_confidence_endpoint(client):
    design_id, h, sel = _selected_version(client)
    r = client.get(f"/api/visual/versions/{sel['version_id']}/confidence", headers=h)
    body = r.json()
    assert body["arabic_confidence"] == 1.0
    assert body["manufacturing_confidence"] == 1.0
    assert body["requires_human_review"] is False


# ------------------------------------------------------------ taste memory


def test_taste_signal_never_touches_source_text(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session, "ميثة")
    ql.record_taste_signal(db_session, "liked", req.id,
                           {"script_family": "diwani", "luxury_score": 0.9})
    ql.record_taste_signal(db_session, "more_traditional", req.id, {"script_family": "naskh"})
    db_session.commit()
    db_session.refresh(v1)
    assert v1.immutable_source_text == "ميثة"
    profile = ql.taste_profile(db_session, [req.id])
    assert profile["script_family_counts"]["diwani"] == 1
    assert profile["sample_size"] == 2


def test_taste_profile_scoped_to_own_requests(clean_tables, db_session):
    req_a = svc.create_request(db_session, "ميثة", "pendant")
    req_b = svc.create_request(db_session, "نورة", "pendant")
    ql.record_taste_signal(db_session, "liked", req_a.id, {"script_family": "kufi"})
    ql.record_taste_signal(db_session, "liked", req_b.id, {"script_family": "naskh"})
    db_session.commit()
    profile = ql.taste_profile(db_session, [req_a.id])
    assert profile["script_family_counts"] == {"kufi": 1}  # req_b excluded


# -------------------------------------------------------------- lineage


def test_lineage_traces_full_chain_no_orphans(client):
    design_id, h, sel = _selected_version(client)
    client.post(f"/api/versions/{sel['version_id']}/approve", headers=h, json={
        "confirmed_text": "ميثة", "source_text_sha256": sel["source_text_sha256"],
        "geometry_hash": sel["geometry_hash"], "approved_by": "c",
    })
    client.get(f"/api/versions/{sel['version_id']}/export/dxf", headers=h)
    r = client.get(f"/api/visual/designs/{design_id}/lineage", headers=h)
    body = r.json()
    assert body["source_text"] == "ميثة"
    assert len(body["versions"]) == 1 and body["versions"][0]["status"] == "APPROVED_LOCKED"
    assert len(body["approvals"]) == 1
    assert len(body["exports"]) == 1 and body["exports"][0]["format"] == "dxf"


def test_lineage_isolated_by_session(client):
    design_id, h, sel = _selected_version(client)
    _, other_h = _new_session(client, "غريب")
    assert client.get(f"/api/visual/designs/{design_id}/lineage", headers=other_h).status_code == 404


# --------------------------------------------------------- product skills


def test_product_skills_registry_and_endpoint(client):
    assert "pendant" in PRODUCT_SKILLS and "earring" in PRODUCT_SKILLS
    skill = load_skill("earring")
    assert skill.default_workshop_profile == "earring"
    with pytest.raises(KeyError):
        load_skill("spaceship")
    r = client.get("/api/visual/product-skills/pendant")
    assert r.status_code == 200 and r.json()["product"] == "pendant"
    assert client.get("/api/visual/product-skills/spaceship").status_code == 404


# -------------------------------------------------------------- shadow eval


def test_shadow_evaluation_requires_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        ql.run_shadow_evaluation({"product_type": "pendant"})
