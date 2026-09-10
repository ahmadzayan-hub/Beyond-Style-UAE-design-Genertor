"""Reference-study slice (arabicdesign.ai, 2026-09): customers pick the
script first and judge a finished-looking piece. We adopt both without
giving up vector truth: a deterministic metal render of the SAME path, and
a script picker that resolves honestly (no silent substitution)."""
from __future__ import annotations

import re
import xml.dom.minidom

import pytest

from app.config import DEFAULT_RULES
from app.engines.generator import generate_candidates
from app.exporters.svg_exporter import MATERIAL_RENDER, export_material_proof_svg, export_proof_svg
from app.schemas.jewellery_design import ImmutableSourceText
from app.services import design_service as svc
from app.services.intake_service import upsert_brief


def _top(text="ميثة"):
    src = ImmutableSourceText.create(text, confirmed=True)
    _, top = generate_candidates("d", src, DEFAULT_RULES)
    return src, top


def test_material_render_keeps_the_exact_geometry_path():
    src, top = _top()
    flat = export_proof_svg(top[0], src)
    flat_d = re.search(r'<path d="([^"]+)"', flat).group(1)
    for material in MATERIAL_RENDER:
        svg = export_material_proof_svg(top[0], src, material)
        xml.dom.minidom.parseString(svg)  # well-formed
        paths = re.findall(r'<path d="([^"]+)"', svg)
        assert paths[0] == flat_d and paths[1] == flat_d  # shadow + metal layers: same path
        assert "<image" not in svg and "data:image" not in svg  # vector only, no raster
        assert 'width="' in svg and "mm" in svg.split("viewBox")[0]  # real mm frame kept
        assert "linearGradient" in svg and "feSpecularLighting" in svg
        assert f'"material_render": "{material}"' in svg


def test_unknown_material_is_refused():
    src, top = _top()
    with pytest.raises(ValueError):
        export_material_proof_svg(top[0], src, "adamantium")


def test_script_choice_adds_script_recipes_and_surfaces_that_face():
    src = ImmutableSourceText.create("ميثة", confirmed=True)
    hints = {"source": "deterministic_intake", "script_family": "ruqaa",
             "preferred_fonts": ["aref-ruqaa"], "product_type": "pendant"}
    all_c, top = generate_candidates("d", src, DEFAULT_RULES, hints=hints)
    assert any(c.recipe.recipe_id == "ruqaa-compact-bar" for c in all_c)  # script recipe joined the pool
    assert any(c.recipe.font_id == "aref-ruqaa" for c in top)  # and reaches the diverse top 10
    bonus = [c for c in all_c if c.recipe.font_id == "aref-ruqaa" and c.score_breakdown]
    assert bonus and all(c.score_breakdown.get("intake_hint_bonus", 0) >= 4.0 for c in bonus)
    assert all(c.source_text_sha256 == src.sha256 for c in all_c)  # text truth untouched


def test_brief_resolves_script_honestly(clean_tables, db_session):
    req = svc.create_request(db_session, "ميثة", "pendant")
    brief = upsert_brief(db_session, req.id, product_type="pendant", script_family="thuluth")
    res = brief.generation_hints["script_resolution"]
    assert brief.generation_hints["script_family"] == "thuluth"
    assert res["outcome"] == "AVAILABLE"  # OFL AMoshref Thulth (2026-09-10)
    assert res["font_id"] == "amoshref-thulth"
    assert "amoshref-thulth" in brief.generation_hints["preferred_fonts"]

    brief = upsert_brief(db_session, req.id, product_type="pendant", script_family="diwani")
    res = brief.generation_hints["script_resolution"]
    assert res["outcome"] == "STYLE_NOT_AVAILABLE"  # no rights-cleared true Diwani
    assert res["recommended_font_id"] == "lemonada" and brief.generation_hints["preferred_fonts"] == ["lemonada"]
    assert "not" in res["message"].lower() or "closest" in res["message"].lower()

    brief = upsert_brief(db_session, req.id, product_type="pendant", script_family="kufi")
    assert brief.generation_hints["script_resolution"]["outcome"] == "AVAILABLE"
    assert "reem-kufi" in brief.generation_hints["preferred_fonts"]  # every licensed Kufi face
