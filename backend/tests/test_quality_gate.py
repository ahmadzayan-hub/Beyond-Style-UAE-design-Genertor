"""Design quality gate: perceptual dedup, proof fidelity, curated library,
golden visual regression."""
import hashlib
import json
import pathlib
import xml.etree.ElementTree as ET

import pytest
from shapely import wkt as shapely_wkt

from app.config import DEFAULT_RULES
from app.engines.generator import (
    diversity_score,
    expand_recipes,
    generate_candidates,
    load_recipe_library,
)
from app.engines.geometry_engine import compose
from app.engines.similarity import NEAR_DUP_IOU, hex_to_grid, iou
from app.engines.arabic_engine import shape_text
from app.exporters.svg_exporter import export_proof_svg, export_svg
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams

GOLDEN_FILE = pathlib.Path(__file__).parent / "golden" / "golden_visual.json"
GOLDEN_NAMES5 = ["ميثة", "نورة", "محمد", "Amal", "Basma"]
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def tops():
    result = {}
    for name in GOLDEN_NAMES5:
        src = ImmutableSourceText.create(name, confirmed=True)
        _, top = generate_candidates("d-quality", src, DEFAULT_RULES)
        result[name] = (src, top)
    return result


# ------------------------------------------------------ curated library


def test_curated_library_dna_complete():
    lib = load_recipe_library()
    recipes = lib["recipes"]
    assert 30 <= len(recipes) <= 40
    purposes = set()
    for r in recipes:
        dna = r["dna"]
        assert dna["family"] and dna["visual_purpose"] and dna["products"]
        assert len(dna["text_length_chars"]) == 2
        assert dna["manufacturing_constraints"]["min_target_height_mm"] > 0
        assert dna["rights"] == "BEYOND_STYLE_ORIGINAL_PARAMETRIC"
        purposes.add(dna["visual_purpose"])
    # Distinct visual purpose per archetype (no filler duplication).
    assert len(purposes) == len(recipes)
    assert len({r["recipe_id"] for r in recipes}) == len(recipes)


def test_expansion_covers_bases_without_filler_explosion():
    lib = load_recipe_library()
    expanded = expand_recipes(30)
    assert len(expanded) >= max(30, len(lib["recipes"]))
    assert len(expanded) <= len(lib["recipes"]) + 10


# ------------------------------------------------- dedup / diversity


@pytest.mark.parametrize("name", GOLDEN_NAMES5)
def test_no_near_duplicates_in_top10(tops, name):
    _, top = tops[name]
    assert len(top) == 10, f"{name}: only {len(top)}"
    grids = [hex_to_grid(c.features.occupancy_hex) for c in top]
    for i in range(len(grids)):
        for j in range(i + 1, len(grids)):
            v = iou(grids[i], grids[j])
            assert v < NEAR_DUP_IOU, (
                f"{name}: rank {top[i].diversity_rank} vs {top[j].diversity_rank}"
                f" perceptual IoU {v:.3f} >= {NEAR_DUP_IOU}"
            )


@pytest.mark.parametrize("name", GOLDEN_NAMES5)
def test_structural_diversity_spread(tops, name):
    _, top = tops[name]
    assert len({c.recipe.composition for c in top}) >= 4
    assert len({c.recipe.font_id for c in top}) >= 2
    assert len({c.recipe.dna["family"] for c in top if c.recipe.dna}) >= 5
    assert diversity_score(top) > 0.05


@pytest.mark.parametrize("name", GOLDEN_NAMES5)
def test_top10_all_pass_manufacturing_and_identity(tops, name):
    _, top = tops[name]
    for c in top:
        assert c.validation.passed
        assert c.identity_proof.verified
        assert c.quality_report["arabic_integrity"]["value"] == 1.0
        assert "HEURISTIC" in c.quality_report["label"]


# ------------------------------------------------- proof fidelity


def _path_bbox(d: str):
    xs, ys = [], []
    for token in d.replace("M", " ").replace("L", " ").replace("Z", " ").split():
        x, y = token.split(",")
        xs.append(float(x))
        ys.append(float(y))
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("name", ["ميثة", "نورة"])
def test_relief_proofs_show_text_layer(tops, name):
    src, top = tops[name]
    relief = [c for c in top if c.recipe.composition in ("plate_oval", "plate_rect")]
    assert relief, f"{name}: no relief candidate in top 10 to verify"
    for c in relief:
        proof = export_proof_svg(c, src)
        root = ET.fromstring(proof)
        paths = root.findall(f"{SVG_NS}path")
        assert len(paths) == 2, "relief proof must have base + text layers"
        base_d, text_d = paths[0].attrib["d"], paths[1].attrib["d"]
        assert paths[1].attrib["fill"] != paths[0].attrib["fill"]
        # Text layer sits inside the base plate bounds.
        bb, tb = _path_bbox(base_d), _path_bbox(text_d)
        assert tb[0] >= bb[0] - 0.01 and tb[2] <= bb[2] + 0.01
        meta = json.loads(root.find(f"{SVG_NS}metadata").text)
        assert meta["relief_differentiated"] is True


def test_openwork_proof_matches_canonical_geometry(tops):
    src, top = tops["ميثة"]
    open_c = next(c for c in top if c.recipe.composition not in ("plate_oval", "plate_rect"))
    proof = export_proof_svg(open_c, src)
    root = ET.fromstring(proof)
    d = root.find(f"{SVG_NS}path").attrib["d"]
    geom = shapely_wkt.loads(open_c.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    bb = _path_bbox(d)
    # 1mm margin each side; proof bbox must equal canonical mm bounds.
    assert bb[2] - bb[0] == pytest.approx(maxx - minx, abs=0.02)
    assert bb[3] - bb[1] == pytest.approx(maxy - miny, abs=0.02)


def test_counters_and_holes_visible_in_proofs(tops):
    """Letter counters/negative space must survive into the proof path
    (subpaths beyond the exterior ring exist for designs with holes)."""
    src, top = tops["محمد"]  # م has a closed counter
    holed = [c for c in top if c.features.hole_count > 0]
    assert holed, "no candidate with holes in top10"
    for c in holed[:3]:
        proof = export_proof_svg(c, src)
        root = ET.fromstring(proof)
        d = root.find(f"{SVG_NS}path").attrib["d"]
        subpaths = d.count("M")
        geom = shapely_wkt.loads(c.geometry_wkt)
        expected = sum(1 + len(p.interiors) for p in geom.geoms)
        assert subpaths == expected, "holes lost between geometry and proof"
        assert 'fill-rule="evenodd"' in proof


def test_dots_preserved_through_construction():
    """نورة contains Nun (1 dot); the bare-text geometry must contain the
    dot as a separate component before bridging."""
    recipe = RecipeParams(
        recipe_id="t", name="t", font_id="cairo", composition="bare",
        dot_strategy="bridge", target_height_mm=12,
    )
    runs = shape_text("نورة", "cairo")
    from app.engines.geometry_engine import build_text_body

    body, _ = build_text_body(runs, recipe)
    from app.engines.geometry_engine import _as_multipolygon

    parts = _as_multipolygon(body)
    assert len(parts.geoms) >= 2, "dots merged/lost before deterministic bridging"
    # After full composition the design must be one connected piece.
    built = compose(runs, recipe, 2.5, 0.9, 0.8, 0.4)
    assert len(built.geometry.geoms) == 1


def test_production_svg_unchanged_single_silhouette(tops):
    """The proof renderer must not alter the canonical production export."""
    src, top = tops["ميثة"]
    c = top[0]
    prod = export_svg(c, src)
    root = ET.fromstring(prod)
    assert len(root.findall(f"{SVG_NS}path")) == 1


# ------------------------------------------------- golden regression


def test_golden_visual_regression(tops):
    """Abstract characteristics of Beyond Style-owned parametric outputs.
    Any engine/recipe change that shifts these must be a conscious decision
    (regenerate via e2e/generate_golden.py)."""
    assert GOLDEN_FILE.is_file(), "golden fixture missing"
    golden = json.loads(GOLDEN_FILE.read_text())
    for name in GOLDEN_NAMES5:
        _, top = tops[name]
        entry = golden[name]
        got_ids = [c.candidate_id for c in top]
        assert got_ids == entry["top_candidate_ids"], f"{name}: top-10 drifted"
        got_geo = hashlib.sha256("".join(c.geometry_wkt for c in top).encode()).hexdigest()
        assert got_geo == entry["combined_geometry_sha256"], f"{name}: geometry drifted"
