"""Vector Composition Engine — the spec's engineering case (§14, §28):

    حامد محمد سلطان ميثه حمد خالد مهرة
    multi-name artistic pendant, Thuluth (inspired — no licensed true cut),
    18K yellow gold, ~60×40 mm, 1.0 mm, ~10 g, two upper attachment points.
"""
from __future__ import annotations

import hashlib

from shapely import wkt

from app.config import DEFAULT_RULES
from app.engines import composition_engine as ce
from app.engines.generator import generate_candidates
from app.exporters.dxf_exporter import export_dxf
from app.exporters.svg_exporter import export_svg
from app.schemas.jewellery_design import ImmutableSourceText
from app.services.materials import load_materials, material, weight_report

NAMES = ("حامد", "محمد", "سلطان", "ميثه", "حمد", "خالد", "مهرة")
TEXT = "\n".join(NAMES)
SHA = hashlib.sha256(TEXT.encode()).hexdigest()


def test_multi_name_detection_and_splitting():
    assert ce.split_names(TEXT) == list(NAMES)
    assert ce.is_multi_name(TEXT) and ce.is_multi_name("حامد محمد سلطان")
    assert not ce.is_multi_name("ميثه") and not ce.is_multi_name("أنت القصة")


def test_every_layout_keeps_identity_and_is_one_piece_with_two_upper_rings():
    from app.schemas.jewellery_design import RecipeParams

    recipe = RecipeParams(recipe_id="mn", name="mn", font_id="katibeh", composition="multi_name",
                          stroke_delta_mm=0.25, dot_strategy="bridge", loops="upper_left_right", target_height_mm=11.0)
    for layout in ce.LAYOUTS:
        runs, proof, built, meta = ce.compose_multi_name(TEXT, recipe, DEFAULT_RULES, layout=layout, variant=0)
        assert proof.verified and proof.notdef_glyph_count == 0, layout
        assert len(built.geometry.geoms) == 1, layout                      # one piece of metal
        assert len(built.loop_centers_mm) == 2, layout
        (lx, ly), (rx, ry) = built.loop_centers_mm
        minx, miny, maxx, maxy = built.geometry.bounds
        assert lx < (minx + maxx) / 2 < rx and ly > miny + (maxy - miny) * 0.5 and ry > miny + (maxy - miny) * 0.5
        assert built.width_mm <= 60.5 and built.height_mm <= 40.5, (layout, built.width_mm, built.height_mm)
        assert meta["names"] == list(NAMES) and meta["bridge_width_mm"] >= 1.2


def test_engineering_case_seven_names_thuluth_pendant():
    src = ImmutableSourceText.create(TEXT, confirmed=True)
    all_c, top = generate_candidates("d", src, DEFAULT_RULES, hints={"script_family": "thuluth", "product_type": "pendant"})
    valid = [c for c in all_c if c.validation.passed]
    assert len(all_c) >= 18 and len(valid) >= 0.7 * len(all_c), (len(all_c), len(valid))
    assert len(top) == 10
    assert len({c.recipe.multi_name["layout"] for c in top}) >= 4          # genuinely different compositions
    assert not any(c.recipe.composition != "multi_name" for c in top)       # never ordinary stacked text
    hit_target = False
    for c in top:
        assert c.validation.passed and c.identity_proof.verified
        assert c.source_text_sha256 == SHA
        assert c.features.width_mm <= 60.5 and c.features.height_mm <= 40.5
        geom = wkt.loads(c.geometry_wkt)
        assert len(geom.geoms) == 1
        report = weight_report(geom, "gold-18k-yellow", 1.0, target_g=10.0)
        assert report["basis"] == "ACTUAL_AREA_X_THICKNESS_X_DENSITY"
        t_for_target = report["target"]["thickness_for_target_mm"]
        if t_for_target and 0.8 <= t_for_target <= 1.5:
            hit_target = True
    assert hit_target, "no variant reaches ~10 g within a 0.8–1.5 mm sheet"
    # exact text carried into the workshop files
    c = top[0]
    svg = export_svg(c, src)
    assert "ميثه" in svg and "ميثة" not in svg and SHA in svg
    assert SHA in export_dxf(c, src)


def test_material_system_and_weight_basis():
    mats = load_materials()
    for mid in ("gold-18k-yellow", "gold-18k-white", "gold-18k-rose", "silver-925", "silver-925-gold-plated",
                "silver-925-rose-plated", "stainless-steel", "brass", "wood", "acrylic", "enamel"):
        m = material(mid)
        for key in ("density_g_cm3", "thickness_mm", "min_bridge_mm", "min_stroke_mm", "method", "finishes",
                    "polishing_allowance_mm", "plating_allowance_mm"):
            assert key in m, (mid, key)
    assert material("enamel")["workshop_ready"] is False
    from shapely.geometry import Point, box

    plate = box(0, 0, 20, 10).difference(Point(10, 5).buffer(3))
    r = weight_report(plate, "gold-18k-yellow", 1.0, target_g=2.7)
    assert abs(r["metal_area_mm2"] - (200 - 3.14159 * 9)) < 0.5      # holes subtracted, not the bounding box
    assert abs(r["estimated_weight_g"] - r["metal_area_mm2"] * 15.5 / 1000) < 0.01  # reported to 0.01 g
    assert r["target"]["within_tolerance"] is True and r["target"]["thickness_for_target_mm"]
    assert "VISUAL_PREVIEW_ONLY" in {w["code"] for w in weight_report(plate, "enamel", 0.5)["warnings"]}
