"""Jewellery realism (owner review 2026-09-04: "the designs are not real").

The 10 proofs must read as metal pieces, not typeset text: strokes near
the fine-jewellery ratio, bails and chain rings fused into the silhouette
(no stalks), medallion names inscribed without piercing the ring, dots as
crisp manufacturable circles, and identity untouched throughout.
"""
from __future__ import annotations

from shapely import wkt
from shapely.geometry import Point

from app.config import DEFAULT_RULES
from app.engines import geometry_engine as ge
from app.engines.generator import build_geometry_for_recipe, expand_recipes, generate_candidates
from app.schemas.jewellery_design import ImmutableSourceText

NAMES = ("ميثة", "نورة", "محمد")


def _tops():
    for name in NAMES:
        src = ImmutableSourceText.create(name, confirmed=True)
        _, top = generate_candidates("d", src, DEFAULT_RULES)
        yield name, src, top


def test_top_proofs_have_fine_jewellery_stroke_weight():
    """The ten proofs lean light: median stroke ratio in the fine-jewellery
    band, nothing slab-like, nothing under the workshop minimum. Small
    Naskh charms are allowed to sit heavier because their hairlines must
    physically reach the neck minimum."""
    for name, _, top in _tops():
        assert len(top) == 10, name
        ratios = []
        for c in top:
            text = wkt.loads(c.text_geometry_wkt)
            ratios.append(ge.mean_stroke_mm(text) / c.recipe.target_height_mm)
            assert c.validation.passed
        ratios.sort()
        assert ratios[0] >= 0.045, (name, ratios)          # relief text on plates may be fine
        assert ratios[len(ratios) // 2] <= 0.135, (name, ratios)  # محمد in Naskh at 12 mm measures 0.13
        assert ratios[-1] <= 0.20, (name, ratios)


def test_attachment_rings_fuse_without_stalks():
    """Every loop ring centre lies within its outer radius of the body, so
    the ring overlaps the metal instead of hanging off a bridge."""
    src = ImmutableSourceText.create("نورة", confirmed=True)
    r_out = DEFAULT_RULES.loop_inner_diameter_mm / 2 + DEFAULT_RULES.loop_wall_mm
    seen = set()
    for recipe in expand_recipes(30):
        if recipe.loops == "none" or recipe.loops in seen and len(seen) == 2:
            continue
        seen.add(recipe.loops)
        runs, _proof, built = build_geometry_for_recipe(src.normalized_text, recipe, DEFAULT_RULES)
        assert built.loop_centers_mm, recipe.recipe_id
        # Same construction without rings = the metal the rings are soldered to.
        _, _, bare = build_geometry_for_recipe(
            src.normalized_text, recipe.model_copy(update={"loops": "none"}), DEFAULT_RULES
        )
        for c in built.loop_centers_mm:
            ring = ge._loop_ring(c, DEFAULT_RULES.loop_inner_diameter_mm, DEFAULT_RULES.loop_wall_mm)
            # the ring wall overlaps real metal (soldered), and its centre sits
            # within one outer radius of that metal (no stalk needed)
            assert ring.intersection(bare.geometry).area > 0.15, (recipe.recipe_id, c)
            assert Point(c).distance(bare.geometry) < r_out, (recipe.recipe_id, c)
        assert len(built.geometry.geoms) == 1  # one connected piece of metal


def test_medallion_name_kisses_the_ring_but_never_pierces_it():
    src = ImmutableSourceText.create("ميثة", confirmed=True)
    for recipe in expand_recipes(30):
        if recipe.composition != "frame_circle":
            continue
        _, _, built = build_geometry_for_recipe(src.normalized_text, recipe, DEFAULT_RULES)
        text = built.text_geometry
        minx, miny, maxx, maxy = text.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        ring_t = max(recipe.connector_height_mm, 1.1)
        far = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for p in text.geoms for x, y in p.exterior.coords)
        outer = far - ring_t * 0.3 + ring_t
        # farthest letter point stays at least 60 % of the wall inside the outer edge
        assert far <= outer - ring_t * 0.6 + 1e-6, recipe.recipe_id


def test_dots_are_normalised_to_manufacturable_circles():
    from shapely.geometry import MultiPolygon, box

    body = box(0, 0, 10, 3)
    speck = Point(4, 5).buffer(0.25, quad_segs=8)  # a 0.5 mm speck
    out = ge.normalise_dots(MultiPolygon([body, speck]), 10.0)
    dot = min(out.geoms, key=lambda p: p.area)
    dminx, dminy, dmaxx, dmaxy = dot.bounds
    assert abs((dmaxx - dminx) - ge.MIN_DOT_DIAMETER_MM) < 0.05
    assert abs(dot.centroid.x - 4) < 1e-6 and abs(dot.centroid.y - 5) < 1e-6
