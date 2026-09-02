"""Archetype catalogue (≥150 structured constructions) + DNA retrieval.

Guards: the catalogue is large, de-duplicated and honestly labelled; the
hint-less candidate pool (and so every golden fixture) is byte-for-byte
unchanged; retrieval prefers what the brief asks for and never sends the
whole library; derived archetypes really build geometry.
"""
from __future__ import annotations

from app.config import DEFAULT_RULES
from app.engines import archetype_library as al
from app.engines.generator import COMPOSITION_CLASSES, build_candidate, expand_recipes, generate_candidates
from app.fonts.glyph_variants import variant_axes
from app.fonts.registry import get_registry
from app.schemas.jewellery_design import ImmutableSourceText, WorkshopRules


def _source(text="ميثة"):
    return ImmutableSourceText.create(text, confirmed=True)


def test_catalogue_is_large_unique_and_labelled():
    cat = al.build_catalogue()
    summary = al.catalogue_summary()
    assert summary["total"] >= 150
    assert summary["curated"] == 46 and summary["uncurated_parametric"] >= 100
    assert len({r.recipe_id for r in cat}) == len(cat)
    curated_sigs = {al.signature(r) for r in cat if (r.dna or {})["curation"] == al.CURATED}
    derived_sigs = [al.signature(r) for r in cat if (r.dna or {})["curation"] == al.UNCURATED]
    assert len(set(derived_sigs)) == len(derived_sigs)  # no derived near-duplicates
    assert not (set(derived_sigs) & curated_sigs)  # never re-derives a curated look
    axes = variant_axes()
    registry = get_registry()
    for r in cat:
        dna = r.dna or {}
        assert dna["curation"] in (al.CURATED, al.UNCURATED)
        assert dna["rights"] == al.RIGHTS
        assert r.composition in COMPOSITION_CLASSES
        assert r.dot_style in axes["dot_styles"] and r.swash in axes["swashes"]
        assert registry.get(r.font_id) is not None
        if dna["curation"] == al.UNCURATED:
            assert dna["derived_from"] and dna["products"] and dna["family"]


def test_curated_bases_come_first_and_unchanged():
    cat = al.build_catalogue()
    lib = al._load(al.DESIGN_RECIPES)["recipes"]
    assert [r.recipe_id for r in cat[: len(lib)]] == [r["recipe_id"] for r in lib]
    for raw, r in zip(lib, cat):
        for key in ("font_id", "composition", "stroke_delta_mm", "target_height_mm", "loops"):
            assert getattr(r, key) == raw[key]


def test_hintless_pool_is_unchanged_by_the_catalogue():
    """The golden fixtures pin candidate ids of the hint-less pool."""
    ids = [r.recipe_id for r in expand_recipes(30)]
    assert not any(i.startswith("arch.") for i in ids)
    src = _source()
    all_c, top = generate_candidates("d", src, DEFAULT_RULES, hints=None)
    assert not any(c.recipe.recipe_id.startswith("arch.") for c in all_c)
    all_h, _ = generate_candidates("d", src, DEFAULT_RULES, hints={"source": "deterministic_intake"})
    assert [c.candidate_id for c in all_h] == [c.candidate_id for c in all_c]


def test_retrieval_prefers_the_briefs_visual_grammar_and_filters_by_product():
    got, prov = al.retrieve_archetypes(
        {"preferred_compositions": ["frame_circle"], "style_intent": "luxury"},
        product_type="earring", text_length=4, k=6,
    )
    assert prov["basis"] == "DNA_COSINE" and len(got) == 6
    assert prov["considered"] < prov["catalogue_size"]  # metadata filter applied
    assert got[0].composition == "frame_circle"
    assert all("earring" in (r.dna or {})["products"] for r in got)
    assert prov["similarities"] == sorted(prov["similarities"], reverse=True)
    assert set(prov["curation"].values()) <= {al.CURATED, al.UNCURATED}


def test_reference_dna_fields_drive_retrieval():
    got, _ = al.retrieve_archetypes(
        {"dna_fields": {"script_family": "kufi", "dot_style": "square", "construction": "openwork"}},
        product_type="pendant", text_length=4, k=4,
    )
    assert got and got[0].dot_style == "square"
    for r in got:  # kufi script, or a kufi-influenced modern face
        rec = get_registry().get(r.font_id)
        assert "kufi" in (rec.script_family, getattr(rec, "style_influence", None))


def test_no_signal_means_no_retrieval():
    got, prov = al.retrieve_archetypes({"source": "deterministic_intake", "product_type": "pendant"})
    assert got == [] and prov["basis"] == "NO_QUERY_SIGNAL"


def test_hints_grow_the_pool_with_retrieved_archetypes_and_trace_it():
    src = _source()
    trace: dict = {}
    hints = {"source": "deterministic_intake", "style_intent": "modern", "product_type": "pendant"}
    all_c, top = generate_candidates("d", src, DEFAULT_RULES, hints=hints, trace=trace)
    retrieved = trace["retrieval"]["returned"]
    assert len(retrieved) == 8 and trace["retrieval"]["basis"] == "DNA_COSINE"
    pool_ids = {c.recipe.recipe_id for c in all_c}
    assert set(retrieved) <= pool_ids
    assert len(top) == 10
    for c in all_c:  # text truth is never touched by retrieval
        assert c.source_text_sha256 == src.sha256


def test_every_derived_font_base_builds_real_geometry():
    src = _source()
    seen: set[str] = set()
    for r in al.build_catalogue():
        if (r.dna or {}).get("curation") != al.UNCURATED or r.font_id in seen:
            continue
        seen.add(r.font_id)
        c = build_candidate("d", src, r, DEFAULT_RULES)
        assert c.geometry_wkt and c.validation is not None
    assert len(seen) == len(al.catalogue_summary()["fonts"])
