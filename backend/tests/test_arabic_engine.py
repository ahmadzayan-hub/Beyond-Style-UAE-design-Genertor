"""Arabic shaping regression tests: RTL, contextual forms, identity."""
import unicodedata

from app.engines.arabic_engine import (
    normalize,
    paragraph_direction,
    segment_runs,
    shape_text,
    verify_identity,
)
from tests.conftest import ARABIC_NAMES, GOLDEN_NAMES

FONTS = ["amiri-regular", "cairo", "scheherazade-new"]


def test_normalization_is_nfc():
    # Decomposed alef+madda must normalize to the composed form.
    decomposed = "آ"  # Alef + Maddah above
    assert normalize(decomposed) == "آ"  # Alef with Madda


def test_paragraph_direction():
    assert paragraph_direction("ميثة") == "rtl"
    assert paragraph_direction("Amal") == "ltr"
    assert paragraph_direction("ميم M") == "rtl"


def test_run_segmentation_mixed():
    runs = segment_runs(normalize("ميم M123"))
    assert len(runs) == 2
    assert runs[0].direction == "rtl" and runs[0].script == "arab"
    assert runs[1].direction == "ltr" and runs[1].script == "latn"
    # Full coverage without overlap.
    assert runs[0].start == 0 and runs[1].end == len("ميم M123")


def test_rtl_direction_for_arabic():
    for name in ARABIC_NAMES:
        for run in shape_text(name, "amiri-regular"):
            if run.script == "arab":
                assert run.direction == "rtl", name


def test_contextual_shaping_produces_positional_forms():
    """The same letter must map to different glyphs by position (contextual
    shaping working), e.g. Heh isolated vs joined."""
    runs_iso = shape_text("ه", "amiri-regular")
    runs_joined = shape_text("هه", "amiri-regular")
    gid_iso = runs_iso[0].glyphs[0].glyph_id
    joined_gids = {g.glyph_id for g in runs_joined[0].glyphs}
    assert gid_iso not in joined_gids, "isolated form reused in joined context"


def test_identity_verified_for_all_golden_names():
    for font in FONTS:
        for name in GOLDEN_NAMES:
            runs = shape_text(name, font)
            proof = verify_identity(name, runs)
            assert proof.verified, f"{font}/{name}: {proof.detail}"


def test_identity_map_traces_every_codepoint():
    name = "عبد الرحمن"
    runs = shape_text(name, "amiri-regular")
    n = len(normalize(name))
    covered = set()
    for run in runs:
        for g in run.glyphs:
            assert 0 <= g.cluster_start < g.cluster_end <= n
            # The glyph's recorded source characters match the text slice.
            assert "".join(g.source_codepoints) == normalize(name)[g.cluster_start:g.cluster_end]
            covered.update(range(g.cluster_start, g.cluster_end))
    assert covered == set(range(n))


def test_hamza_and_special_letters_preserved():
    """Shaping must consume Hamza-on-Waw, Alif Maqsura, Taa Marbuta —
    the identity map must show those exact codepoints, unchanged."""
    cases = {"لؤي": "ؤ", "رؤى": "ى", "ميثة": "ة", "يحيى": "ى"}
    for name, must_have in cases.items():
        runs = shape_text(name, "scheherazade-new")
        rendered_chars = [c for r in runs for g in r.glyphs for c in g.source_codepoints]
        assert must_have in rendered_chars, f"{must_have} lost in {name}"
        # No character substitution occurred anywhere.
        assert sorted(rendered_chars) == sorted(normalize(name))


def test_missing_glyph_fails_verification():
    # Cairo has no Harakat support in registry; a rare codepoint like
    # ARABIC LETTER DOTLESS QAF W/ unusual mark may produce .notdef. Use a
    # codepoint far outside coverage: OSMANYA letter.
    runs = shape_text("𐒀", "amiri-regular")
    proof = verify_identity("𐒀", runs)
    assert not proof.verified
    assert proof.notdef_glyph_count > 0


def test_shaping_is_deterministic():
    a = shape_text("ما شاء الله", "amiri-regular")
    b = shape_text("ما شاء الله", "amiri-regular")
    assert [g.glyph_id for r in a for g in r.glyphs] == [
        g.glyph_id for r in b for g in r.glyphs
    ]
    assert [g.x_advance_mm for r in a for g in r.glyphs] == [
        g.x_advance_mm for r in b for g in r.glyphs
    ]
