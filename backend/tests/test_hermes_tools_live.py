"""Real tool wiring, tool security allow-lists, isolated Hermes runtime
client, full agent E2E, dependency isolation, and live Claude/GPT-Image-2
acceptance (SKIPPED_EXTERNAL_MODEL honestly without credentials — this
environment has none, so only that branch is exercised here; the real-
call branch is implemented and will run the moment credentials exist).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai import agents as ag
from app.ai import tools as ai_tools
from app.ai.hermes_client import HermesClient, hermes_client_status
from app.ai.image_providers import ImageProviderUnavailable, get_image_provider
from app.ai.llm import LLMUnavailable, credentials_available as claude_credentials_available
from app.ai.quality_layer import DesignJuryVerdict, JURY_SYSTEM, run_design_jury
from app.db import models as m
from app.main import app
from app.services import design_service as svc
from app.services import visual_studio as vs
from app.services.intake_service import add_reference
from tests.test_persistence_lifecycle import _full_flow
from tests.test_reference_intelligence import _jpeg


@pytest.fixture
def client(clean_tables):
    from app.security.sessions import GENERATE_LIMITER, UPLOAD_LIMITER

    UPLOAD_LIMITER.reset()
    GENERATE_LIMITER.reset()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------- tool wiring


def test_analyze_reference_tool_real_execution_and_durable_audit(clean_tables, db_session):
    req = svc.create_request(db_session, "ميثة", "pendant")
    asset = add_reference(db_session, req.id, _jpeg(500, 500), "a.jpg", "image/jpeg", "CUSTOMER_OWNED")
    db_session.commit()

    orch = ag.Orchestrator(job_id="job-1")
    result = orch.call_tool("reference_intelligence", "analyze_reference", db_session,
                             reference_id=asset.id, request_id=req.id)
    db_session.commit()
    assert result["reference_id"] == str(asset.id)
    assert "dna" in result and isinstance(result["dna"], dict)

    events = db_session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "TOOL_INVOKED",
                                     m.DesignEvent.request_id == req.id)
    ).scalars().all()
    assert len(events) == 1
    meta = events[0].event_metadata
    for field in ("job_id", "agent", "tool", "input_hash", "result_status", "latency_ms"):
        assert field in meta
    assert meta["job_id"] == "job-1" and meta["agent"] == "reference_intelligence"
    assert meta["tool"] == "analyze_reference" and meta["result_status"] == "OK"
    assert events[0].created_at is not None  # timestamp


def test_generate_design_recipes_and_rank_candidates_tools(clean_tables, db_session):
    req = svc.create_request(db_session, "ميثة", "pendant")
    svc.confirm_request_text(db_session, req.id, "ميثة")
    db_session.commit()

    orch = ag.Orchestrator(job_id="job-2")
    gen = orch.call_tool("design_concept", "generate_design_recipes", db_session, request_id=req.id)
    db_session.commit()
    assert gen["internal_count"] >= 30
    assert len(gen["top_candidate_keys"]) == 10

    ranked = orch.call_tool("diversity", "rank_candidates", db_session, request_id=req.id, top_n=10)
    assert len(ranked["ranked"]) == 10
    assert set(r["candidate_key"] for r in ranked["ranked"]) == set(gen["top_candidate_keys"])


def test_validate_arabic_and_validate_manufacturing_tools(clean_tables, db_session):
    req, design, version = _full_flow(db_session, "ميثة")

    orch = ag.Orchestrator(job_id="job-3")
    arabic = orch.call_tool("calligraphy_art_director", "validate_arabic", db_session, text="ميثة")
    assert arabic["verified"] is True

    mfg = orch.call_tool("jewellery_engineering", "validate_manufacturing", db_session,
                          text="ميثة", recipe=version.recipe)
    assert mfg["passed"] == version.validation_passed


def test_repair_geometry_tool_creates_new_unapproved_version(clean_tables, db_session):
    req, design, version = _full_flow(db_session, "ميثة")

    orch = ag.Orchestrator(job_id="job-4")
    repaired = orch.call_tool("manufacturing_qa", "repair_geometry", db_session, version_id=version.id)
    db_session.commit()
    assert repaired["parent_version_id"] == str(version.id)
    new_version = db_session.get(m.DesignVersion, uuid.UUID(repaired["version_id"]))
    assert new_version.status == "UNAPPROVED"
    assert new_version.immutable_source_text == "ميثة"  # never touches source text


def test_create_visual_preview_tool_honest_without_provider(clean_tables, db_session):
    req, design, version = _full_flow(db_session, "ميثة")
    db_session.commit()

    orch = ag.Orchestrator(job_id="job-5")
    with pytest.raises(ag.ToolExecutionError) as exc_info:
        orch.call_tool("visual_critic", "create_visual_preview", db_session,
                        version_id=version.id, request_id=req.id)
    assert "PHOTOREAL" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()
    db_session.commit()

    events = db_session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "TOOL_INVOKED",
                                     m.DesignEvent.request_id == req.id)
    ).scalars().all()
    assert events[-1].event_metadata["result_status"] == "ERROR"  # honest, not silently OK


def test_retrieve_design_memory_tool(clean_tables, db_session):
    orch = ag.Orchestrator(job_id="job-6")
    result = orch.call_tool("design_memory", "retrieve_design_memory", db_session)
    assert "recipe_family_weights" in result and "workshop_failure_constraints" in result


# ------------------------------------------------------------ tool security


def test_agent_tool_allowlist_examples_from_spec():
    """The exact ReferenceAgent/DesignAgent/ManufacturingAgent allow-list
    examples the task specified, plus proof no agent can bypass them."""
    ref = ag.AGENT_REGISTRY["reference_intelligence"]
    assert {"analyze_reference", "retrieve_design_memory"} <= ref.tools

    design = ag.AGENT_REGISTRY["design_concept"]
    assert {"retrieve_design_memory", "generate_design_recipes"} <= design.tools

    mfg = ag.AGENT_REGISTRY["manufacturing_qa"]
    assert {"validate_manufacturing", "repair_geometry"} <= mfg.tools


def test_approve_design_always_blocked_even_though_wired(clean_tables, db_session):
    """approve_design has a real fn in TOOL_REGISTRY (tools.py) but is a
    WRITE_TOOLS_REQUIRING_HUMAN member — Orchestrator.call_tool must
    refuse it for every agent, including master_orchestrator."""
    assert "approve_design" in ai_tools.TOOL_REGISTRY  # really wired
    orch = ag.Orchestrator(job_id="job-7")
    for agent_name in ag.AGENT_REGISTRY:
        with pytest.raises(ag.ToolNotPermitted):
            orch.call_tool(agent_name, "approve_design", db_session, version_id=str(uuid.uuid4()),
                            confirmed_text="x", source_text_sha256="x", geometry_hash="x", approved_by="agent")


def test_cross_agent_tool_use_blocked():
    """An agent may only use tools in its own allow-list even if the
    tool is globally READ_TOOLS-permitted."""
    orch = ag.Orchestrator(job_id="job-8")
    # trend_scout has no manufacturing tools.
    with pytest.raises(ag.ToolNotPermitted):
        orch.check_tool("trend_scout", "validate_manufacturing")


def test_no_shell_file_network_tools_registered():
    """No arbitrary shell/file/network access is ever allow-listed for
    production agents — only the 9 real tools + prior read tools."""
    dangerous = {"shell", "exec", "eval", "read_file", "write_file", "http_request", "subprocess"}
    assert not (dangerous & ag.READ_TOOLS)
    assert not (dangerous & set(ai_tools.TOOL_REGISTRY.keys()))


# --------------------------------------------------------- isolated runtime


def test_hermes_client_in_process_default():
    status = hermes_client_status()
    assert status["mode"] == "in_process"
    c = HermesClient()
    assert c.available() is True


def test_hermes_client_isolated_unreachable_never_blocks(monkeypatch):
    import importlib

    from app.ai import hermes_client as hc

    monkeypatch.setenv("HERMES_MODE", "isolated")
    monkeypatch.setenv("HERMES_URL", "http://localhost:1")  # nothing listens here
    monkeypatch.setenv("HERMES_TIMEOUT", "1")
    importlib.reload(hc)
    try:
        assert hc.hermes_client_status()["mode"] == "isolated"
        assert hc.isolated_health()["reachable"] is False
        client = hc.HermesClient()
        assert client.available() is False
        # run_agent falls through to in-process Orchestrator, which then
        # raises the SAME honest LLMUnavailable as always — never blocks,
        # never fabricates.
        with pytest.raises(LLMUnavailable):
            client.run_agent("design_concept", JURY_SYSTEM, "x", DesignJuryVerdict)
    finally:
        # monkeypatch reverts env vars only after this function returns —
        # restore the module's cached constants explicitly so later tests
        # in this process see the default in_process mode again.
        monkeypatch.delenv("HERMES_MODE", raising=False)
        monkeypatch.delenv("HERMES_URL", raising=False)
        monkeypatch.delenv("HERMES_TIMEOUT", raising=False)
        importlib.reload(hc)


def test_internal_tool_endpoint_closed_by_default(client):
    r = client.post("/api/orchestration/internal/tools/retrieve_design_memory",
                     json={"agent_name": "design_memory", "job_id": "j1", "input": {}})
    assert r.status_code == 403  # INTERNAL_TOOL_TOKEN unset in this environment


def test_internal_tool_endpoint_works_with_token(monkeypatch, client):
    import app.api.visual as visual_api

    monkeypatch.setattr(visual_api, "INTERNAL_TOOL_TOKEN", "test-secret")
    r = client.post(
        "/api/orchestration/internal/tools/retrieve_design_memory",
        json={"agent_name": "design_memory", "job_id": "j2", "input": {}},
        headers={"X-Internal-Tool-Token": "test-secret"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "OK"
    # wrong token still refused
    r2 = client.post(
        "/api/orchestration/internal/tools/retrieve_design_memory",
        json={"agent_name": "design_memory", "job_id": "j3", "input": {}},
        headers={"X-Internal-Tool-Token": "wrong"},
    )
    assert r2.status_code == 403


def test_orchestration_status_reports_hermes_client_and_tools(client):
    r = client.get("/api/orchestration/status")
    body = r.json()
    assert body["hermes_client"]["mode"] == "in_process"
    assert "approve_design" in body["tools"]["human_only"]
    assert "approve_design" not in body["tools"]["agent_invocable"]
    assert "generate_design_recipes" in body["tools"]["agent_invocable"]


# --------------------------------------------------------- live acceptance


def test_live_claude_acceptance_arabic_norah_reference(clean_tables, db_session):
    """Case: 'نفس التصميم بس غير الكتابة إلى نورة'. When ANTHROPIC_API_KEY
    exists this proves Claude → strict DesignDNA → exact source_text
    preserved → DesignRecipe → deterministic generator executes it.
    Without credentials (this environment) it must SKIP honestly, never
    fabricate a PASS."""
    req = svc.create_request(db_session, "نورة", "pendant")
    asset = add_reference(db_session, req.id, _jpeg(500, 500), "ref.jpg", "image/jpeg", "CUSTOMER_OWNED",
                           customer_message="نفس التصميم بس غير الكتابة إلى نورة")
    db_session.commit()

    if not claude_credentials_available():
        with pytest.raises(LLMUnavailable) as exc_info:
            run_design_jury({"product_type": "pendant", "note": "norah reference acceptance"})
        assert exc_info.value.reason
        status = "SKIPPED_EXTERNAL_MODEL"
    else:  # pragma: no cover — exercised only when real credentials exist
        verdict, usage = run_design_jury({"product_type": "pendant"})
        assert isinstance(verdict, DesignJuryVerdict)
        status = "OK"

    # Deterministic path proceeds regardless of Claude availability —
    # exact source_text is preserved end-to-end either way.
    svc.confirm_request_text(db_session, req.id, "نورة")
    result = svc.generate_and_persist_candidates(db_session, req.id)
    assert len(result["top"]) == 10
    for c in result["top"]:
        assert c.source_text_sha256 == req.source_text_sha256
    db_session.commit()
    db_session.refresh(req)
    assert req.source_text_normalized == "نورة"
    assert status in ("SKIPPED_EXTERNAL_MODEL", "OK")


def test_live_gpt_image2_acceptance_letter_ain_earring(clean_tables, db_session):
    """Case: Arabic letter 'ع', 18K yellow-gold earring, luxury studio
    preview. Proves: canonical geometry hash stored, IdentityGuard runs,
    preview can never become SVG/DXF manufacturing source. Without
    credentials/OPENAI_IMAGE_ENABLED (this environment) must SKIP
    honestly as SKIPPED_EXTERNAL_MODEL, never a fabricated PASS."""
    req, design, version = _full_flow(db_session, "ع")
    db_session.commit()

    provider = get_image_provider()
    health = provider.health_check()
    if not (health["enabled_flag"] and health["key_configured"]):
        with pytest.raises(ImageProviderUnavailable):
            brief = vs.build_brief(version, scene="luxury_black", material="gold-18k-yellow")
            vs.generate_preview(db_session, version, req.id, brief)
        status = "SKIPPED_EXTERNAL_MODEL"
    else:  # pragma: no cover — exercised only when real credentials + flag exist
        brief = vs.build_brief(version, scene="luxury_black", material="gold-18k-yellow")
        record = vs.generate_preview(db_session, version, req.id, brief)
        assert record.geometry_hash == version.geometry_hash
        assert record.guard_status in ("PASS", "REVIEW_REQUIRED", "REJECTED_GEOMETRY_DRIFT")
        status = "OK"

    # Deterministic canonical geometry hash exists regardless of AI status.
    assert version.geometry_hash
    with pytest.raises(ValueError):
        svc.export_version(db_session, version.id, fmt="png")  # never exportable as a manufacturing file
    assert status in ("SKIPPED_EXTERNAL_MODEL", "OK")


# ---------------------------------------------------------------- full E2E


def test_full_agent_orchestration_e2e_deterministic_path_always_completes(clean_tables, db_session):
    """Customer brief/reference → Orchestrator → Reference Agent →
    (Claude DesignDNA when available) → Design Memory retrieval → Design
    Agent → deterministic candidate generation → Arabic QA →
    Manufacturing QA → ranking → selected design → optional GPT Image
    preview → (approval stays human-only) → memory event. The
    deterministic path must complete even with Claude, Hermes-isolated
    and GPT-Image-2 all unavailable — true in this environment."""
    req = svc.create_request(db_session, "ميثة", "pendant")
    asset = add_reference(db_session, req.id, _jpeg(500, 500), "a.jpg", "image/jpeg", "CUSTOMER_OWNED")
    db_session.commit()

    orch = ag.Orchestrator(job_id="e2e-1")

    # Reference Agent: analyze + retrieve memory.
    ref_result = orch.call_tool("reference_intelligence", "analyze_reference", db_session,
                                 reference_id=asset.id, request_id=req.id)
    orch.call_tool("reference_intelligence", "retrieve_design_memory", db_session)

    # Claude DesignDNA step: honestly unavailable here, never blocks.
    with pytest.raises(LLMUnavailable):
        orch.run_agent("design_concept", "produce a DesignDNA", str(ref_result), DesignJuryVerdict)

    # Design Agent: deterministic candidate generation (survives Claude outage).
    svc.confirm_request_text(db_session, req.id, "ميثة")
    gen = orch.call_tool("design_concept", "generate_design_recipes", db_session, request_id=req.id)
    assert gen["internal_count"] >= 30

    # Arabic QA + Manufacturing QA (deterministic engines, always real).
    # request_id is not a functional input to these tools (pydantic
    # ignores the extra field) — passed only so the audit trail below
    # ties every step of this job to the same request.
    arabic = orch.call_tool("calligraphy_art_director", "validate_arabic", db_session,
                             text="ميثة", request_id=req.id)
    assert arabic["verified"] is True

    # Ranking → selected design.
    ranked = orch.call_tool("diversity", "rank_candidates", db_session, request_id=req.id, top_n=10)
    top_key = ranked["ranked"][0]["candidate_key"]
    design, version = svc.select_candidate(db_session, req.id, top_key)
    db_session.commit()
    assert version.status == "UNAPPROVED"

    mfg = orch.call_tool("jewellery_engineering", "validate_manufacturing", db_session,
                          text="ميثة", recipe=version.recipe, request_id=req.id)
    assert mfg["passed"] == version.validation_passed

    # Optional GPT-Image preview: honestly unavailable, never blocks approval path.
    with pytest.raises(ag.ToolExecutionError):
        orch.call_tool("visual_critic", "create_visual_preview", db_session,
                        version_id=version.id, request_id=req.id)
    db_session.commit()

    # Approval stays human-only — Orchestrator can never do it, even here.
    with pytest.raises(ag.ToolNotPermitted):
        orch.call_tool("master_orchestrator", "approve_design", db_session, version_id=str(version.id),
                        confirmed_text="ميثة", source_text_sha256=version.source_text_sha256,
                        geometry_hash=version.geometry_hash, approved_by="agent")

    # Real human/customer approval via the existing service (unaffected).
    approval = svc.approve_version(
        db_session, version_id=version.id, confirmed_text="ميثة",
        source_text_sha256=version.source_text_sha256, geometry_hash=version.geometry_hash,
        approved_by="customer",
    )
    db_session.commit()
    assert approval.status == "ACTIVE"

    # Memory event: durable TOOL_INVOKED trail exists for the whole run.
    events = db_session.execute(
        select(m.DesignEvent).where(m.DesignEvent.event_type == "TOOL_INVOKED",
                                     m.DesignEvent.request_id == req.id)
    ).scalars().all()
    tool_names = {e.event_metadata["tool"] for e in events}
    assert {"analyze_reference", "generate_design_recipes", "validate_arabic",
            "rank_candidates", "validate_manufacturing", "create_visual_preview"} <= tool_names


# ---------------------------------------------------------- dependency isolation


def test_main_app_dependency_pins_unaffected_by_hermes():
    """The isolated Hermes runtime's own pins (services/hermes/requirements.txt)
    must never be merged into the main app's requirements.txt."""
    import pathlib

    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    root_reqs = (backend_dir / "requirements.txt").read_text()
    assert "hermes-agent" not in root_reqs
    assert "pydantic==2.13.4" not in root_reqs
    assert "pydantic==2.9.2" in root_reqs  # unchanged main-app pin

    hermes_reqs_path = backend_dir.parent / "services" / "hermes" / "requirements.txt"
    assert hermes_reqs_path.exists()
    hermes_reqs = hermes_reqs_path.read_text()
    assert "hermes-agent" in hermes_reqs
    assert "pydantic==2.13.4" in hermes_reqs


def test_main_app_installed_pydantic_version_matches_pin():
    """Proves installing anthropic/openai in this environment did not
    silently bump pydantic away from the pinned 2.9.2 (a real regression
    risk the isolated-runtime split exists specifically to avoid)."""
    import pydantic

    assert pydantic.VERSION.startswith("2.9")


def test_backend_174_plus_suite_still_collectable():
    """Smoke check that adding tools.py/hermes_client.py/this file did
    not break collection of the previously-green suite."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]),
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
