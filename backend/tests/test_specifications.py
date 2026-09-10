"""Jewellery specification knowledge — honest evidence levels, product
briefs, and the copilot tool that serves them."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai.tools import execute_tool
from app.main import app
from app.services.specifications import (
    PRODUCT_SECTIONS, expert_brief, load_specifications, sections_for_product, size_envelope,
)

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


def test_every_section_declares_an_evidence_level_and_sources():
    spec = load_specifications()
    assert spec["research_status"]["result"] == "SKIPPED_NETWORK_BLOCKED"
    for name, section in spec["sections"].items():
        assert section["evidence_level"], name
        assert section["verify_at"], name
        assert section.get("rules") or section.get("table") or section.get("requests"), name
    # in-repo references must exist
    for section in spec["sections"].values():
        for ref in section["verify_at"]:
            if not ref.startswith("http"):
                path = ref.split("#")[0]
                assert (ROOT / "backend" / path).exists() or (ROOT / path).exists(), ref


def test_trade_values_agree_with_enforced_materials_limits():
    """The knowledge base may not promise anything softer than what the
    manufacturing gate enforces."""
    materials = json.loads((ROOT / "backend" / "app" / "data" / "materials.json").read_text())["materials"]
    silver = materials["silver-925"]
    rules = " ".join(load_specifications()["sections"]["sheet_thickness_and_cut_out_limits"]["rules"])
    assert f"min stroke {silver['min_stroke_mm']} mm" in rules and f"min bridge {silver['min_bridge_mm']} mm" in rules
    fineness = load_specifications()["sections"]["metals_fineness_and_marking"]["fineness"]
    assert fineness["18K"] == 750 and fineness["sterling_silver"] == 925


def test_product_sections_and_envelopes():
    for product in PRODUCT_SECTIONS:
        assert sections_for_product(product)
    assert "ring_sizing" in sections_for_product("ring")
    assert "chains" in sections_for_product("bracelet")
    assert size_envelope("necklace")["width"] == [30, 45]
    assert size_envelope("necklace", "kids")["width"] == [20, 30]
    assert size_envelope("cufflink")["width"] == [15, 18]
    assert size_envelope("unknown_product") is None


def test_expert_brief_is_labelled_and_never_overrides_the_gate():
    brief = expert_brief("necklace", audience="kids", material="silver-925", text_length=10)
    assert brief["research_status"] == "SKIPPED_NETWORK_BLOCKED"
    assert "override" in brief["authority"]
    assert all(r["evidence_level"] for r in brief["rules"])
    assert any("Kids audience" in n for n in brief["notes"]) and any("long" in n for n in brief["notes"])
    assert brief["proven_lessons"] and all(l["evidence_tier"] for l in brief["proven_lessons"])
    assert all(l["evidence_tier"] != "EXTERNAL_INSPIRATION" for l in brief["proven_lessons"])


def test_retrieve_design_memory_tool_carries_the_brief(db_session):
    plain = execute_tool("retrieve_design_memory", db_session)
    assert plain["expert_brief"] is None and "recipe_family_weights" in plain
    focused = execute_tool("retrieve_design_memory", db_session, product="cufflink", material="silver-925")
    assert focused["expert_brief"]["product"] == "cufflink"
    assert focused["expert_brief"]["size_envelope_mm"]["width"] == [15, 18]


def test_specifications_endpoint():
    whole = client.get("/api/products/specifications").json()
    assert whole["research_status"]["result"] == "SKIPPED_NETWORK_BLOCKED" and len(whole["sections"]) >= 10
    brief = client.get("/api/products/specifications", params={"product": "ring", "material": "silver-925"}).json()
    assert any(r["section"] == "ring_sizing" for r in brief["rules"])
