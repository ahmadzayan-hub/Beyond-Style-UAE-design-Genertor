"""Hermes orchestration + Claude routing + GPT-Image-2 visual studio.

Fake providers appear ONLY in this file and are injected explicitly.
Production code paths never fabricate AI output: with no credentials the
real providers raise and the deterministic Golden Path continues.
"""
import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import select

from app.ai import agents as ag
from app.ai import llm
from app.ai.image_providers import (
    COST_PER_IMAGE_USD,
    ImageProviderUnavailable,
    OpenAIImage2Provider,
    image_provider_status,
)
from app.ai.visual_brief import VisualBrief, VisualPromptBuilder
from app.db import models as m
from app.main import app
from app.services import visual_studio as vs
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
    sel = client.post(
        f"/api/designs/{design_id}/select", headers=h, json={"candidate_id": top[0]["candidate_id"]}
    ).json()
    return design_id, h, sel


# ------------------------------------------------------- Claude routing


def test_model_routing_tiers_and_pricing():
    assert llm.TIER_MODELS["fast"] == "claude-haiku-4-5"
    assert llm.TIER_MODELS["primary"] == "claude-sonnet-5"
    assert llm.TIER_MODELS["escalate"] == "claude-opus-5"
    # Cost estimate is monotonic in tier.
    cost = {t: llm.estimate_cost_usd(mdl, 10_000, 2_000) for t, mdl in llm.TIER_MODELS.items()}
    assert cost["fast"] < cost["primary"] < cost["escalate"]


def test_llm_unavailable_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    class Schema(BaseModel):
        x: int

    with pytest.raises(llm.LLMUnavailable):
        llm.get_provider("primary").structured("sys", "user", Schema)
    status = llm.llm_status()
    assert status["credentials_configured"] is False
    for tier in status["tiers"].values():
        assert "unavailable" in tier["status"]


def test_agent_registry_and_tool_policy():
    orch = ag.Orchestrator()
    # Read tool allowed for the owning agent.
    orch.check_tool("reference_intelligence", "retrieve_reference_dna")
    # Same tool not allowed for an agent that does not declare it.
    with pytest.raises(ag.ToolNotPermitted):
        orch.check_tool("diversity", "retrieve_reference_dna")
    # Production/write actions are never agent-invocable.
    for tool in ag.WRITE_TOOLS_REQUIRING_HUMAN:
        with pytest.raises(ag.ToolNotPermitted):
            orch.check_tool("master_orchestrator", tool)
    assert len(ag.AGENT_REGISTRY) >= 13
    assert orch.audit_log()[0]["agent"] == "reference_intelligence"


def test_budget_caps_depth_calls_and_cost():
    budget = ag.JobBudget(max_cost_usd=0.01, max_agent_calls=2, max_tool_calls=1, max_depth=2)
    budget.count_agent_call(depth=1)
    budget.count_agent_call(depth=2)
    with pytest.raises(ag.BudgetExceeded):
        budget.count_agent_call(depth=2)  # 3rd call
    with pytest.raises(ag.AgentDepthExceeded):
        ag.JobBudget(max_depth=2).count_agent_call(depth=3)
    budget2 = ag.JobBudget(max_cost_usd=0.01)
    budget2.charge(0.009)
    with pytest.raises(ag.BudgetExceeded):
        budget2.charge(0.005)


def test_orchestrator_agent_call_unavailable_is_honest(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class Schema(BaseModel):
        ok: bool

    orch = ag.Orchestrator()
    with pytest.raises(llm.LLMUnavailable):
        orch.run_agent("design_concept", "sys", "task", Schema)
    assert orch.audit_log()[-1]["action"] == "unavailable"  # audited, not faked


def test_hermes_runtime_status_is_honest():
    st = ag.HermesRuntimeAdapter.status()
    assert st["package"].startswith("hermes-agent")
    assert st["installed_in_this_process"] is (ag.HermesRuntimeAdapter.available() and st["runtime_enabled"])
    assert st["execution_mode"] in ("hermes", "in_process_orchestrator")


def test_orchestration_status_endpoint_leaks_no_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET-VALUE")
    body = client.get("/api/orchestration/status").json()
    text = str(body)
    assert "sk-test-SECRET-VALUE" not in text  # key never reaches a client
    assert body["claude"]["routing"]["primary"] == "claude-sonnet-5"
    assert body["source_of_truth_hierarchy"][0] == "confirmed customer source_text"
    assert "production_export" in body["write_actions_requiring_human"]
    assert body["image_provider"]["health"]["key_configured"] is True  # boolean only


# ----------------------------------------------------------- prompt builder


def test_prompt_builder_always_carries_preservation_rules():
    brief = VisualBrief(source_text_hash="a" * 64, design_version_id="v", geometry_hash="b" * 64,
                        material="gold-18k-yellow", scene="luxury_black", stones=["diamond"])
    prompt = VisualPromptBuilder.build(brief)
    assert "18K yellow gold" in prompt and "black velvet" in prompt
    assert "Do not rewrite, reinterpret, translate" in prompt
    assert "NEGATIVE CONSTRAINTS" in prompt and "no watermark" in prompt
    # Reference DNA contributes mood only.
    with_dna = VisualPromptBuilder.build(brief, {"composition": "medallion", "detected_text": "نورة"})
    assert "medallion" in with_dna and "نورة" not in with_dna


def test_visual_brief_cache_key_stable_and_material_sensitive():
    base = dict(source_text_hash="a" * 64, design_version_id="v", geometry_hash="b" * 64)
    k1 = VisualBrief(**base).cache_key()
    k2 = VisualBrief(**base).cache_key()
    k3 = VisualBrief(**base, material="gold-18k-rose").cache_key()
    assert k1 == k2 and k1 != k3


# ------------------------------------------------------- image provider


def test_image_provider_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIImage2Provider()
    with pytest.raises(ImageProviderUnavailable):
        provider.generate(
            VisualBrief(source_text_hash="a" * 64, design_version_id="v", geometry_hash="b" * 64),
            "prompt",
        )
    health = provider.health_check()
    assert "unavailable" in health["status"]
    assert health["model"] == "gpt-image-2"
    assert set(health) & {"key_configured"} and isinstance(health["key_configured"], bool)
    assert "api_key" not in str(image_provider_status()).lower()


def test_canonical_render_matches_geometry(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    png = vs.render_canonical_png(v1.geometry_wkt, size_px=256)
    img = Image.open(io.BytesIO(png))
    assert img.mode == "RGBA" and img.size == (256, 256)
    from app.ai.preview_guard import identity_divergence

    # The deterministic render must itself pass the identity guard.
    assert identity_divergence(v1.geometry_wkt, png) < vs.PASS_MAX


# --------------------------------------------------- visual studio flow


class _FakeProvider:
    """Test double injected explicitly — mirrors the canonical render so
    the guard passes, or distorts it to prove rejection."""

    name = "fake-provider"
    model = "fake-image-model"

    def __init__(self, mode="faithful"):
        self.mode = mode
        self.calls = 0

    def _guard(self):
        return None

    def estimate_cost(self, brief, images=1):
        return COST_PER_IMAGE_USD.get(brief.quality, 0.07) * images

    def _render(self, canonical_png):
        self.calls += 1
        if self.mode == "faithful":
            return canonical_png
        blank = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
        out = io.BytesIO()
        blank.save(out, format="PNG")
        return out.getvalue()

    def create_product_preview(self, canonical_png, brief):
        return self._render(canonical_png)

    def create_reference_inspired_preview(self, canonical_png, brief, dna):
        return self._render(canonical_png)


def _prep(db_session, monkeypatch, mode="faithful"):
    req, design, v1 = _full_flow(db_session)
    fake = _FakeProvider(mode)
    monkeypatch.setattr(vs, "get_image_provider", lambda: fake)
    brief = vs.build_brief(v1, scene="studio_white", material="silver-925", quality="DRAFT")
    return req, v1, brief, fake


def test_preview_passes_guard_stores_hashes_and_costs(clean_tables, db_session, monkeypatch):
    req, v1, brief, fake = _prep(db_session, monkeypatch)
    rec = vs.generate_preview(db_session, v1, req.id, brief)
    db_session.commit()
    assert rec.guard_status == "PASS" and rec.attempts == 1
    assert rec.geometry_hash == v1.geometry_hash          # geometry hash stored
    assert rec.source_text_sha256 == v1.source_text_sha256
    assert rec.kind == "ai_preview" and rec.cost_usd > 0
    assert "Do not rewrite" in rec.prompt


def test_preview_retries_bounded_then_rejected(clean_tables, db_session, monkeypatch):
    req, v1, brief, fake = _prep(db_session, monkeypatch, mode="distorted")
    with pytest.raises(vs.PreviewRejected) as exc:
        vs.generate_preview(db_session, v1, req.id, brief)
    assert exc.value.status == "REJECTED_GEOMETRY_DRIFT"
    assert fake.calls == vs.MAX_PREVIEW_RETRIES + 1  # bounded, no infinite loop
    db_session.rollback()


def test_cache_prevents_duplicate_paid_calls(clean_tables, db_session, monkeypatch):
    req, v1, brief, fake = _prep(db_session, monkeypatch)
    first = vs.generate_preview(db_session, v1, req.id, brief)
    db_session.commit()
    second = vs.generate_preview(db_session, v1, req.id, brief)
    db_session.commit()
    assert second.id == first.id and fake.calls == 1  # no second paid call
    events = [e.event_type for e in db_session.execute(select(m.DesignEvent)).scalars()]
    assert "AI_PREVIEW_CACHE_HIT" in events


def test_material_variant_does_not_change_source_text(clean_tables, db_session, monkeypatch):
    req, v1, brief, fake = _prep(db_session, monkeypatch)
    vs.generate_preview(db_session, v1, req.id, brief)
    gold = vs.build_brief(v1, scene="studio_white", material="gold-18k-yellow", quality="DRAFT")
    rec2 = vs.generate_preview(db_session, v1, req.id, gold)
    db_session.commit()
    db_session.refresh(v1)
    assert rec2.visual_brief["material"] == "gold-18k-yellow"
    assert rec2.source_text_sha256 == v1.source_text_sha256
    assert v1.immutable_source_text == "ميثة"  # untouched by any preview
    assert fake.calls == 2  # different brief ⇒ new generation, not a cache hit


def test_session_cost_budget_enforced(clean_tables, db_session, monkeypatch):
    req, v1, brief, fake = _prep(db_session, monkeypatch)
    with pytest.raises(vs.PreviewRejected) as exc:
        vs.generate_preview(db_session, v1, req.id, brief, max_session_cost_usd=0.0)
    assert exc.value.status == "BUDGET_COST_EXCEEDED"
    assert fake.calls == 0  # refused before any spend
    db_session.rollback()


def test_ai_raster_can_never_be_exported(clean_tables, db_session, monkeypatch):
    """Manufacturing export accepts only deterministic vector formats."""
    from app.services import design_service as svc

    req, v1, brief, fake = _prep(db_session, monkeypatch)
    rec = vs.generate_preview(db_session, v1, req.id, brief)
    svc.approve_version(db_session, v1.id, v1.immutable_source_text,
                        v1.source_text_sha256, v1.geometry_hash, "customer")
    db_session.commit()
    for fmt in ("ai_preview", "jpeg"):
        with pytest.raises(ValueError):
            svc.export_version(db_session, v1.id, fmt)
    # The legitimate DXF export never contains the AI raster.
    dxf, record = svc.export_version(db_session, v1.id, "dxf")
    assert record.content_sha256 != rec.content_sha256
    assert "LWPOLYLINE" in dxf
    # A PNG export exists, but it is a raster OF THE MASTER VECTOR (kind
    # "preview", raster fidelity against the geometry) — never the AI image.
    png, prec = svc.export_version(db_session, v1.id, "png")
    assert prec.kind == "preview" and prec.content_sha256 != rec.content_sha256
    assert prec.fidelity["status"] == "PASS" and "not manufacturing truth" in prec.fidelity["note"]


def test_preview_endpoint_unavailable_keeps_deterministic_path(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_IMAGE_ENABLED", "false")
    design_id, h, sel = _selected_version(client)
    r = client.post(f"/api/visual/versions/{sel['version_id']}/preview", headers=h, json={})
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["code"] == "PHOTOREAL_PREVIEW_UNAVAILABLE"
    assert detail["deterministic_design_unaffected"] is True
    # Deterministic SVG preview still works — the designer is unblocked.
    assert client.get(detail["fallback"], headers=h).status_code == 200


def test_preview_requires_validated_version_and_known_options(client):
    design_id, h, sel = _selected_version(client)
    bad = client.post(f"/api/visual/versions/{sel['version_id']}/preview", headers=h,
                      json={"material": "unobtainium"})
    assert bad.status_code == 422
    opts = client.get("/api/visual/options").json()
    assert "gold-18k-rose" in opts["materials"] and "on_body_neck" in opts["scenes"]
    assert opts["quality_modes"] == ["DRAFT", "FINAL", "STANDARD"]


def test_reference_workflow_keeps_source_text_immutable(client, monkeypatch):
    """SAME_STRUCTURE_NEW_TEXT: reference DNA guides style; نورة stays exact
    through generation, selection and preview brief."""
    design_id, h = _new_session(client, "نورة")
    img = Image.new("RGB", (600, 900), (210, 190, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    up = client.post(
        f"/api/designs/{design_id}/references", headers=h,
        files={"file": ("ref.jpg", buf.getvalue(), "image/jpeg")},
        data={"customer_message": "نفس التصميم بس غير الاسم إلى نورة"},
    ).json()
    client.post(f"/api/designs/{design_id}/references/{up['reference_id']}/analyze", headers=h)
    client.put(f"/api/designs/{design_id}/brief", headers=h,
               json={"customer_message": "نفس التصميم بس غير الاسم إلى نورة"})
    brief = client.get(f"/api/designs/{design_id}/brief", headers=h).json()
    assert brief["confirmed_text"] is None  # never taken from the reference
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "نورة"})
    top = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()["top"]
    sel = client.post(f"/api/designs/{design_id}/select", headers=h,
                      json={"candidate_id": top[0]["candidate_id"]}).json()
    version = client.get(f"/api/versions/{sel['version_id']}", headers=h).json()
    assert version["immutable_source_text"] == "نورة"
    assert version["source_text_sha256"] == sel["source_text_sha256"]
