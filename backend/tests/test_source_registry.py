"""Arabic Calligraphy Source Registry: styles are never artificially locked
and never faked — availability is derived from the rights-cleared registry."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.fonts import styles
from app.fonts.registry import get_registry
from app.main import app


def test_registry_holds_the_vendored_open_fonts_with_verified_hashes():
    fonts = get_registry().list()
    assert len(fonts) >= 37
    for f in fonts:
        assert f.commercial_production_allowed and f.integrity_ok, f.font_id
        assert f.license_file and f.file_sha256


def test_style_catalogue_is_honest_about_availability():
    cards = {c["id"]: c for c in styles.style_catalogue()}
    assert cards["naskh"]["status"] == "AVAILABLE" and len(cards["naskh"]["fonts"]) >= 6
    assert cards["ruqaa"]["status"] == "AVAILABLE" and cards["kufi_modern"]["status"] == "AVAILABLE"
    assert cards["nastaliq_persian"]["status"] == "AVAILABLE" and cards["decorative"]["status"] == "AVAILABLE"
    assert cards["bold"]["status"] == "AVAILABLE" and cards["geometric"]["status"] == "AVAILABLE"
    # Thuluth: TRUE via the OFL AMoshref Thulth; Diwani: no rights-cleared source → inspired only.
    assert cards["thuluth"]["status"] == "AVAILABLE" and cards["thuluth"]["fonts"][0]["font_id"] == "amoshref-thulth"
    assert cards["diwani"]["status"] == "INFLUENCED_ONLY" and "upload" in cards["diwani"]["action_en"].lower()
    assert cards["kufi_square"]["status"] == "PARAMETRIC_NOT_BUILT"
    assert cards["fatimid_foliated"]["status"] == "UPLOAD_REQUIRED"
    assert cards["experimental_composition"]["status"] == "ENGINE"
    for c in cards.values():
        assert c["status"] in styles.ACTION_LABEL and c["action_ar"]


def test_registry_view_has_every_spec_column():
    rows = styles.registry_view()
    required = {"name", "script_family", "source", "version", "license", "commercial_use", "web_use",
                "server_use", "production_use", "hash_sha256", "imported_date", "owner_source",
                "glyph_count", "shaping_status"}
    assert required <= set(rows[0].keys())
    assert all(r["glyph_count"] and r["shaping_status"] == "VERIFIED" for r in rows)


def test_style_and_registry_and_preview_endpoints():
    with TestClient(app) as c:
        r = c.get("/api/fonts/styles")
        assert r.status_code == 200 and len(r.json()["styles"]) >= 20
        naskh = next(s for s in r.json()["styles"] if s["id"] == "naskh")
        assert naskh["manufacturing_score"] is not None and naskh["fonts"]
        r = c.get("/api/fonts/registry")
        assert r.status_code == 200 and r.json()["count"] >= 37
        r = c.get("/api/fonts/preview/gulzar", params={"text": "ميثه"})
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
        import hashlib
        assert hashlib.sha256("ميثه".encode()).hexdigest() in r.text and "<path" in r.text
        r = c.get("/api/fonts/preview/gulzar", params={"text": "مي‍ثه"})
        assert r.status_code == 422  # hidden character never silently dropped
        assert c.get("/api/fonts/preview/nope").status_code == 404


def test_every_new_font_has_measured_recipes_and_joins_script_selection():
    from app.fonts.capabilities import _script_recipe_library, recipes_for_script

    lib = _script_recipe_library()
    scored = set(lib["manufacturing_scores"])
    assert {"gulzar", "rakkas", "qahiri", "blaka", "noto-kufi-arabic"} <= scored
    for r in lib["recipes"]:
        assert r["dna"]["manufacturing_validated"].startswith("sweep") or "golden" in r["dna"]["manufacturing_validated"]
    fonts_for_naskh = {r["font_id"] for r in recipes_for_script("naskh")}
    assert {"lateef", "harmattan", "noto-naskh-arabic"} <= fonts_for_naskh
    assert {r["font_id"] for r in recipes_for_script("nastaliq")} >= {"gulzar", "mirza"}


def test_requested_true_script_dominates_the_shown_ten():
    """A customer who chooses Thuluth (TRUE source) sees Thuluth: the
    archetype spread is cloned onto the true font and 8 of the 10 slots are
    reserved for it (valid + diverse). Diwani (inspired-only) gets no such
    dressing-up."""
    from collections import Counter

    from app.config import DEFAULT_RULES
    from app.engines.generator import SCRIPT_PRIORITY_SLOTS, generate_candidates
    from app.schemas.jewellery_design import ImmutableSourceText

    src = ImmutableSourceText.create("ميثه", confirmed=True)
    trace: dict = {}
    all_c, top = generate_candidates("d-th", src, DEFAULT_RULES, hints={"script_family": "thuluth"}, trace=trace)
    by_font = Counter(c.recipe.font_id for c in top)
    assert len(top) == 10 and all(c.validation.passed and c.identity_proof.verified for c in top)
    assert by_font["amoshref-thulth"] >= min(SCRIPT_PRIORITY_SLOTS, 6), by_font
    assert len({c.recipe.composition for c in top if c.recipe.font_id == "amoshref-thulth"}) >= 3
    assert trace["script_priority"]["fonts"] == ["amoshref-thulth"]
    assert any(r.recipe.recipe_id.endswith("@amoshref-thulth") for r in all_c)

    all_d, top_d = generate_candidates("d-dw", src, DEFAULT_RULES, hints={"script_family": "diwani"})
    assert all(c.recipe.font_id != "amoshref-thulth" for c in top_d)
    assert not any("@" in c.recipe.recipe_id for c in all_d)   # no cloning onto a bridge font
