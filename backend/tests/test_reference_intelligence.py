"""Reference Intelligence: providers, DesignDNA, retrieval, memory,
preview guard, API. Mock analyzers appear ONLY here (unit tests) and are
injected explicitly — production code paths never fabricate AI output."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.ai import config as ai_config
from app.ai.design_dna import DesignDNA, fallback_dna, parse_vlm_dna
from app.ai.embeddings import ENCODER_VERSION, cosine, encode_dna, rank_by_similarity
from app.ai.preview_guard import check_preview
from app.ai.providers import ModelUnavailable, ai_status, get_image_editor, get_visual_analyzer
from app.ai.registry import MODEL_REGISTRY, get_model
from app.db import models as m
from app.main import app
from app.services import design_memory, reference_intelligence as ri
from app.services.design_service import _version_to_candidate  # noqa: F401
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


def _jpeg(w=800, h=400):
    img = Image.new("RGB", (w, h), (200, 180, 120))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


# --------------------------------------------------------- registry/providers


def test_registry_all_models_commercially_usable():
    for record in MODEL_REGISTRY.values():
        assert record.license == "Apache-2.0"
        assert record.commercial_use
        assert record.authoritative_for == []  # never truth for anything
    assert "flux-dev" not in MODEL_REGISTRY  # non-commercial models absent


def test_providers_honest_unavailable_no_fake_results():
    """AI_MODE=disabled and no torch installed → every provider raises
    ModelUnavailable; nothing returns fabricated output."""
    assert ai_config.AI_MODE == "disabled"
    with pytest.raises(ModelUnavailable):
        get_visual_analyzer().analyze(b"x", "analyze")
    with pytest.raises(ModelUnavailable):
        get_image_editor().edit(b"x", "edit")
    status = ai_status()
    for provider in status["providers"].values():
        assert "unavailable" in provider["status"]
        assert provider["license"] == "Apache-2.0"


# --------------------------------------------------------------- DesignDNA


def test_vlm_dna_strict_json_and_text_keys_dropped():
    raw = {
        "product_type": "pendant", "script_family": "diwani",
        "composition": "medallion", "construction": "openwork",
        "luxury_score": 0.9, "reference_confidence": 0.8,
        "detected_text": "نورة", "ocr_text": "نورة", "name": "leak",
    }
    dna = parse_vlm_dna(raw, "qwen3-vl@test")
    assert dna.source == "vlm" and dna.script_family == "diwani"
    dumped = dna.model_dump()
    assert "detected_text" not in dumped and "ocr_text" not in dumped
    assert "نورة" not in json.dumps(dumped, ensure_ascii=False)


def test_vlm_dna_invalid_schema_rejected():
    with pytest.raises(ValueError):
        parse_vlm_dna({"luxury_score": 7.5}, "qwen3-vl@test")  # out of range


def test_fallback_dna_labelled():
    dna = fallback_dna({"aspect_ratio": 2.0, "orientation": "horizontal"})
    assert dna.source == "deterministic_fallback"
    assert dna.analyzer_model == "none"
    assert dna.composition == "horizontal"


def test_dna_embedding_similarity_orders_style_families():
    medallion = DesignDNA(source="vlm", analyzer_model="t", script_family="diwani",
                          composition="medallion", construction="openwork")
    medallion2 = DesignDNA(source="vlm", analyzer_model="t", script_family="diwani",
                           composition="circular", construction="openwork")
    kufi_plate = DesignDNA(source="vlm", analyzer_model="t", script_family="square_kufi",
                           composition="horizontal", construction="plate")
    q = encode_dna(medallion)
    ranked = rank_by_similarity(q, [("m2", encode_dna(medallion2)), ("kp", encode_dna(kufi_plate))], 2)
    assert ranked[0][0] == "m2" and ranked[0][1] > ranked[1][1]
    assert cosine(q, q) == pytest.approx(1.0)


# ------------------------------------------------------ pipeline (fallback)


def test_reference_pipeline_end_to_end_fallback(client, db_session):
    """Full pipeline with AI disabled: upload → analyze (labelled fallback
    DNA) → brief hints → 10 validated diverse proofs. Deterministic path
    unaffected by AI outage (acceptance gate 7)."""
    design_id, h = _new_session(client, "نورة")
    up = client.post(
        f"/api/designs/{design_id}/references", headers=h,
        files={"file": ("ref.jpg", _jpeg(400, 900), "image/jpeg")},
        data={"provenance": "CUSTOMER_OWNED"},
    ).json()
    r = client.post(
        f"/api/designs/{design_id}/references/{up['reference_id']}/analyze", headers=h
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "deterministic_fallback"  # honest label, no GPU here
    assert body["copy_risk_status"] == "OK"
    # require_model=true refuses fallback honestly.
    r = client.post(
        f"/api/designs/{design_id}/references/{up['reference_id']}/analyze",
        headers=h, params={"require_model": "true"},
    )
    assert r.status_code == 503 and "MODEL_UNAVAILABLE" in r.text
    # Brief merges DNA hints with style strength.
    brief = client.put(
        f"/api/designs/{design_id}/brief", headers=h,
        json={"customer_message": "نفس الشكل بس غير الكتابة إلى نورة", "style_strength": 1.0},
    ).json()
    assert brief["generation_hints"]["source"] == "reference_dna"
    assert brief["generation_hints"]["bonus_scale"] == 1.5
    assert brief["request_type"] == "SAME_STRUCTURE_NEW_TEXT"
    # Golden path continues: confirm exact text → 10 proofs.
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "نورة"})
    gen = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()
    assert len(gen["top"]) == 10
    assert gen["ranking_config_version"] == "ref-0.1.0"  # reference weights used
    for c in gen["top"]:
        assert c["source_text_sha256"]  # target text immutable + traceable


def test_copy_risk_reference_forces_inspired_alternative(client, db_session):
    design_id, h = _new_session(client)
    up = client.post(
        f"/api/designs/{design_id}/references", headers=h,
        files={"file": ("brand.jpg", _jpeg(), "image/jpeg")},
        data={"customer_message": "نفس تصميم كارتير", "provenance": "UNKNOWN"},
    ).json()
    body = client.post(
        f"/api/designs/{design_id}/references/{up['reference_id']}/analyze", headers=h
    ).json()
    assert body["copy_risk_status"] == "INSPIRED_ALTERNATIVE_REQUIRED"


def test_retrieval_prefers_approved_designs(clean_tables, db_session):
    """Similar-reference retrieval only surfaces references whose designs
    reached APPROVED_LOCKED (memory quality gate)."""
    from app.services.intake_service import add_reference

    # Approved flow with a reference + DNA.
    req, design, v1 = _full_flow(db_session, "ميثة")
    a1 = add_reference(db_session, req.id, _jpeg(500, 500), "a.jpg", "image/jpeg", "CUSTOMER_OWNED")
    row1 = ri.analyze_reference(db_session, a1.id)
    from app.services import design_service as svc

    svc.approve_version(db_session, v1.id, v1.immutable_source_text,
                        v1.source_text_sha256, v1.geometry_hash, "c")
    # Unapproved flow with a similar reference.
    req2 = svc.create_request(db_session, "نورة", "pendant")
    a2 = add_reference(db_session, req2.id, _jpeg(500, 500), "b.jpg", "image/jpeg", "CUSTOMER_OWNED")
    row2 = ri.analyze_reference(db_session, a2.id)
    db_session.commit()
    similar = ri.retrieve_similar_approved(db_session, row2)
    ids = [i for i, _ in similar]
    assert str(row1.id) in ids  # approved reference retrieved
    # Query row itself and non-approved rows are not in the pool.
    assert str(row2.id) not in ids


# ------------------------------------------------------------ design memory


def test_design_memory_feedback_and_weights(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    for event, family in [("CUSTOMER_SELECTED", "naskh-openwork"),
                          ("CUSTOMER_APPROVED", "naskh-openwork"),
                          ("PRODUCED", "naskh-openwork"),
                          ("WORKSHOP_REJECTED", "kufi-bold")]:
        design_memory.record_feedback(
            db_session, event, request_id=req.id, version_id=v1.id,
            metadata={"recipe_family": family, "reason": "stroke too thin"},
        )
    db_session.commit()
    weights = design_memory.recipe_family_weights(db_session)
    assert weights["naskh-openwork"] == 0.5  # capped positive
    assert weights["kufi-bold"] == -0.3
    constraints = design_memory.workshop_failure_constraints(db_session)
    assert constraints and constraints[0]["reason"] == "stroke too thin"
    with pytest.raises(ValueError):
        design_memory.record_feedback(db_session, "NOT_AN_EVENT")


def test_lora_export_rights_gated(clean_tables, db_session):
    from app.services import design_service as svc
    from app.services.intake_service import add_reference

    req, design, v1 = _full_flow(db_session)
    # UNKNOWN provenance reference on approved design → excluded.
    a1 = add_reference(db_session, req.id, _jpeg(), "u.jpg", "image/jpeg", "UNKNOWN")
    ri.analyze_reference(db_session, a1.id)
    svc.approve_version(db_session, v1.id, v1.immutable_source_text,
                        v1.source_text_sha256, v1.geometry_hash, "c")
    db_session.commit()
    assert design_memory.export_lora_dataset(db_session) == []
    # CUSTOMER_OWNED reference → exported with DNA + approved recipe.
    a2 = add_reference(db_session, req.id, _jpeg(600, 300), "o.jpg", "image/jpeg", "CUSTOMER_OWNED")
    ri.analyze_reference(db_session, a2.id)
    db_session.commit()
    rows = design_memory.export_lora_dataset(db_session)
    assert len(rows) == 1 and rows[0]["outcome"] == "APPROVED_LOCKED"
    assert rows[0]["approved_recipe"]["recipe_id"]


# ------------------------------------------------------------ preview guard


def _silhouette_png(geometry_wkt: str, invert=False, blank=False):
    """Rasterize a geometry occupancy grid to a PNG (test stand-in for a
    generated preview — the guard itself is model-independent)."""
    from app.ai.preview_guard import GRID, geometry_occupancy

    cells = geometry_occupancy(geometry_wkt)
    img = Image.new("L", (GRID, GRID), 255)
    if not blank:
        img.putdata([(255 if c else 0) if invert else (0 if c else 255) for c in cells])
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_preview_guard_accepts_faithful_render(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    faithful = _silhouette_png(v1.geometry_wkt)
    result = check_preview(v1.geometry_wkt, faithful)
    assert result["accepted"] and result["divergence"] < 0.05


def test_preview_guard_rejects_altered_design(clean_tables, db_session):
    """A preview whose silhouette no longer matches the canonical geometry
    (e.g. AI redrew the lettering) must be rejected."""
    req, design, v1 = _full_flow(db_session)
    blank = _silhouette_png(v1.geometry_wkt, blank=True)
    result = check_preview(v1.geometry_wkt, blank)
    assert not result["accepted"]


def test_photoreal_preview_endpoint_model_unavailable(client):
    design_id, h = _new_session(client)
    client.post(f"/api/designs/{design_id}/confirm", headers=h, json={"confirmed_text": "ميثة"})
    top = client.post(f"/api/designs/{design_id}/candidates", headers=h).json()["top"]
    vid = client.post(
        f"/api/designs/{design_id}/select", headers=h,
        json={"candidate_id": top[0]["candidate_id"]},
    ).json()["version_id"]
    r = client.post(f"/api/ai/versions/{vid}/photoreal-preview", headers=h, json={})
    assert r.status_code == 503 and "MODEL_UNAVAILABLE" in r.text  # honest outage


def test_ai_status_endpoint(client):
    body = client.get("/api/ai/status").json()
    assert body["ai_mode"] == "disabled"
    assert body["allow_paid_providers"] is False
    assert set(body["registry"]) == {"qwen3-vl", "qwen-image-edit", "qwen-image", "flux-schnell"}
    assert "always available" in body["deterministic_golden_path"]


# ------------------------------------------------------------ ai jobs


def test_ai_job_worker_honest_model_unavailable(clean_tables, db_session):
    from app.ai.worker import run_once
    from app.services.intake_service import add_reference
    from app.services import design_service as svc

    req = svc.create_request(db_session, "ميثة", "pendant")
    asset = add_reference(db_session, req.id, _jpeg(), "r.jpg", "image/jpeg", "CUSTOMER_OWNED")
    # 'preview' jobs need a model → worker must mark MODEL_UNAVAILABLE.
    job = m.AIJob(kind="preview", payload={"storage_key": asset.storage_key, "prompt": "x"})
    db_session.add(job)
    db_session.commit()
    assert run_once() is True
    db_session.expire_all()
    refreshed = db_session.get(m.AIJob, job.id)
    assert refreshed.status == "MODEL_UNAVAILABLE"
    assert "MODEL_UNAVAILABLE" in (refreshed.error or "")
