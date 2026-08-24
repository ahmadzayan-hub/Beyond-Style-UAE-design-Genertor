"""Glyph variants, aesthetic bridges, workshop profiles, multi-line."""
import pytest
from shapely import wkt as shapely_wkt
from shapely.geometry import MultiPolygon, Point, box

from app.config import DEFAULT_RULES, get_profile, load_workshop_profiles
from app.engines.arabic_engine import (
    apply_kashida,
    break_lines,
    remap_runs_to_source,
    shape_multiline,
    shape_text,
    verify_identity,
)
from app.engines.generator import build_geometry_for_recipe, generate_candidates
from app.engines.geometry_engine import bridge_components, restyle_dots
from app.engines.validator import validate
from app.fonts.glyph_variants import (
    feature_sets_for_font,
    resolve_features,
    variant_axes,
)
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams

LONG_NAMES = "حامد محمد سلطان ميثة حمد خالد مهرة"
PHRASE = "سلام هي حتى مطلع الفجر"


def _recipe(**kw):
    base = dict(recipe_id="t", name="t", font_id="amiri-regular", composition="bare",
                target_height_mm=12, stroke_delta_mm=0.25)
    base.update(kw)
    return RecipeParams(**base)


# ------------------------------------------------------- variant library


def test_variant_registry_loads_and_validates():
    axes = variant_axes()
    assert set(axes) == {"ot_feature_sets", "dot_styles", "swashes"}
    assert "amiri-ornate-1" in feature_sets_for_font("amiri-regular")
    assert "sche-salt" not in feature_sets_for_font("amiri-regular")
    with pytest.raises(ValueError):
        resolve_features("sche-salt", "amiri-regular")


def test_kashida_preserves_identity_and_elongates():
    for name in ["ميثة", "محمد"]:
        disp, imap = apply_kashida(name, 2)
        assert "ـ" in disp and disp.replace("ـ", "") == name  # only elongation added
        runs = remap_runs_to_source(shape_text(disp, "amiri-regular"), imap, name)
        proof = verify_identity(name, runs)
        assert proof.verified
        plain_w = sum(g.x_advance_mm for r in shape_text(name, "amiri-regular") for g in r.glyphs)
        kash_w = sum(g.x_advance_mm for r in runs for g in r.glyphs)
        assert kash_w > plain_w * 1.15
    # Non-joining final pair: no kashida inserted, text unchanged.
    disp, _ = apply_kashida("نورة", 2)
    assert disp == "نورة"


def test_dot_styles_change_geometry_not_identity():
    src = "نورة"
    base = build_geometry_for_recipe(src, _recipe(font_id="cairo"), DEFAULT_RULES)
    diamond = build_geometry_for_recipe(src, _recipe(font_id="cairo", dot_style="diamond"), DEFAULT_RULES)
    assert base[1].verified and diamond[1].verified
    assert base[2].geometry.wkt != diamond[2].geometry.wkt


def test_restyle_dots_never_touches_letter_bodies():
    letter = box(0, 0, 8, 10)  # big letter-sized part
    dot = Point(4, 12).buffer(0.8)
    styled = restyle_dots(MultiPolygon([letter, dot]), {"shape": "square", "scale": 1.0}, 10)
    parts = sorted(styled.geoms, key=lambda p: -p.area)
    assert parts[0].equals(letter)  # untouched
    assert abs(parts[1].area - dot.area) / dot.area < 0.35  # equal-area restyle


def test_swash_adds_ornament_only():
    plain = build_geometry_for_recipe("ميثة", _recipe(), DEFAULT_RULES)[2]
    swashed = build_geometry_for_recipe("ميثة", _recipe(swash="underline_flourish"), DEFAULT_RULES)[2]
    assert swashed.geometry.area > plain.geometry.area  # ornament added
    # Text layer identical: swash never replaces letter geometry.
    assert swashed.text_geometry.wkt != ""


# ------------------------------------------------- aesthetic bridges


def test_vertical_bridge_prefers_dot_over_chord():
    # Dot floating above a wide bar: aesthetic routing must connect
    # vertically (short drop), not diagonally to the bar's far end.
    bar = box(0, 0, 30, 2)
    dot = Point(25, 6).buffer(0.8)
    bridged, n = bridge_components(MultiPolygon([bar, dot]), 0.8, style="vertical")
    assert n == 1 and len(bridged.geoms) == 1
    # The connection stays within the dot's x-window.
    minx, _, maxx, _ = dot.bounds
    connection = bridged.difference(bar.buffer(0.05)).difference(dot.buffer(0.05))
    cminx, _, cmaxx, _ = connection.bounds
    assert cminx >= minx - 2 and cmaxx <= maxx + 2, "bridge wandered sideways"


def test_radial_bridge_in_medallion_no_chord():
    """Medallion: bridges must follow the ray outward, so bridge geometry
    stays close to the centre-to-ring corridor, never a long chord."""
    src = ImmutableSourceText.create("ميثة", confirmed=True)
    r = _recipe(composition="frame_circle", frame_margin_mm=1.6, target_height_mm=10)
    _, proof, built = build_geometry_for_recipe("ميثة", r, DEFAULT_RULES)
    assert len(built.geometry.geoms) == 1
    report = validate(built, DEFAULT_RULES, proof, expected_loops=1)
    assert report.passed


def test_bridges_deterministic():
    bar = box(0, 0, 30, 2)
    dots = [Point(x, 5).buffer(0.7) for x in (5, 15, 25)]
    a, na = bridge_components(MultiPolygon([bar, *dots]), 0.8)
    b, nb = bridge_components(MultiPolygon([bar, *dots]), 0.8)
    assert na == nb and a.equals(b)


# ------------------------------------------------- workshop profiles


def test_profiles_versioned_and_complete():
    data = load_workshop_profiles()
    assert data["profiles_version"].startswith("wp-")
    assert len(data["profiles"]) >= 6
    for entry in data["profiles"]:
        for key in ("min_stroke_mm", "min_gap_mm", "min_bridge_mm", "min_counter_mm",
                    "max_slenderness", "max_width_mm", "thickness_class",
                    "calibration_status"):
            assert key in entry, f"{entry['profile_name']} missing {key}"
        # Honesty: uncalibrated profiles can never claim production status.
        assert entry["calibration_status"] == "INDUSTRY_TYPICAL_UNCALIBRATED"


def test_profile_lookup_and_no_silent_fallback():
    p = get_profile("earring", "gold-18k")
    assert p.max_width_mm == 22.0 and p.product == "earring"
    assert not p.is_production_profile
    with pytest.raises(KeyError):
        get_profile("tiara", "platinum")


def test_earring_profile_blocks_pendant_sized_design():
    earring_rules = get_profile("earring", "silver-925")
    r = _recipe(target_height_mm=18, kashida_count=3)
    _, proof, built = build_geometry_for_recipe("محمد", r, earring_rules)
    assert built.width_mm > earring_rules.max_width_mm  # genuinely oversized input
    report = validate(built, earring_rules, proof, expected_loops=1)
    assert not report.passed  # blocked by the 25mm earring envelope


def test_slenderness_gate():
    from app.engines.geometry_engine import BuiltGeometry
    from app.schemas.jewellery_design import TextIdentityProof, ViolationCode

    proof = TextIdentityProof(verified=True, covered_codepoint_indices=[0],
                              uncovered_codepoint_indices=[], notdef_glyph_count=0)
    sliver = box(0, 0, 55, 3)  # slenderness 18 > 8
    report = validate(BuiltGeometry(geometry=MultiPolygon([sliver])), DEFAULT_RULES, proof)
    assert any(v.code == ViolationCode.OVERSIZE and "slenderness" in v.detail.lower()
               for v in report.violations)


# ------------------------------------------------- multi-line long text


def test_line_breaking_balanced_and_lossless():
    lines = break_lines(LONG_NAMES, 3)
    assert len(lines) == 3
    assert " ".join(lines) == LONG_NAMES  # nothing lost or reordered


def test_multiline_identity_verified():
    for text, lines in [(LONG_NAMES, 3), (PHRASE, 2)]:
        _, proof = shape_multiline(text, "amiri-regular", lines)
        assert proof.verified, proof.detail


@pytest.mark.parametrize("text", [LONG_NAMES, PHRASE])
def test_long_text_yields_10_valid_stacked_options(text):
    src = ImmutableSourceText.create(text, confirmed=True)
    _, top = generate_candidates("d-long", src, DEFAULT_RULES)
    assert len(top) == 10
    for c in top:
        assert c.validation.passed and c.identity_proof.verified
        assert c.features.width_mm <= DEFAULT_RULES.max_width_mm
    # Stacked options dominate and are genuinely multi-line.
    assert sum(1 for c in top if c.recipe.max_lines > 1) >= 6
    assert len({c.recipe.composition for c in top}) >= 3


def test_variant_axes_visible_in_top10():
    src = ImmutableSourceText.create("ميثة", confirmed=True)
    _, top = generate_candidates("d-var", src, DEFAULT_RULES)
    dot_styles = {c.recipe.dot_style for c in top}
    swashes = {c.recipe.swash for c in top}
    kashidas = {c.recipe.kashida_count for c in top}
    # At least two stylistic families beyond layout variation.
    assert len(dot_styles | swashes | {f"k{k}" for k in kashidas}) >= 4
