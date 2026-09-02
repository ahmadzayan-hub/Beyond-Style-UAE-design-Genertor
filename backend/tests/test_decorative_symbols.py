"""♥ as an explicit decorative symbol — never a silent font substitution."""
from shapely import wkt as shapely_wkt

from app.config import DEFAULT_RULES
from app.engines.arabic_engine import DECORATIVE_GLYPH_ID, shape_text, verify_identity
from app.engines.generator import build_candidate
from app.engines.ring_band import ring_rules
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams

TEXT = "عائشة♥حسن"


def test_heart_is_shaped_as_a_labelled_decorative_glyph_with_exact_identity():
    runs = shape_text(TEXT, "amiri-regular")
    hearts = [g for r in runs for g in r.glyphs if g.glyph_id == DECORATIVE_GLYPH_ID]
    assert len(hearts) == 1
    assert hearts[0].glyph_name == "decorative.heart"
    assert hearts[0].source_codepoints == ["♥"]
    assert hearts[0].cluster_start == TEXT.index("♥")
    proof = verify_identity(TEXT, runs)
    assert proof.verified, proof.detail  # every codepoint covered, no notdef
    # Visual order for an RTL paragraph: حسن (left) … ♥ … عائشة (right).
    order = [g.cluster_start for r in runs for g in r.glyphs]
    assert order[0] > order[-1]


def test_heart_appears_in_pendant_geometry_and_manufactures():
    src = ImmutableSourceText.create(TEXT, confirmed=True)
    recipe = RecipeParams(recipe_id="t", name="t", font_id="amiri-regular", composition="baseline_bar",
                          loops="top", dot_strategy="bridge", target_height_mm=14.0)
    c = build_candidate("d", src, recipe, DEFAULT_RULES)
    assert c.identity_proof.verified
    plain = build_candidate("d", ImmutableSourceText.create("عائشة حسن", confirmed=True), recipe, DEFAULT_RULES)
    assert shapely_wkt.loads(c.geometry_wkt).area > shapely_wkt.loads(plain.geometry_wkt).area * 1.02


def test_heart_in_ring_inner_face():
    src = ImmutableSourceText.create("أنت القصة\nعائشة♥حسن", confirmed=True)
    recipe = RecipeParams(recipe_id="r", name="r", font_id="amiri-regular", composition="engraved_band",
                          loops="none", dot_strategy="keep",
                          ring={"size_eu": 54, "band_height_mm": 7.5, "border": "none"})
    c = build_candidate("d", src, recipe, ring_rules(DEFAULT_RULES))
    assert c.identity_proof.verified, c.identity_proof.detail
    assert c.inner_text_geometry_wkt
