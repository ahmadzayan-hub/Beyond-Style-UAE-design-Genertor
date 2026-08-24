"""Regenerate the golden visual regression fixture.

Run ONLY when an engine/recipe change intentionally shifts outputs; commit
the updated fixture with the change that caused it. The fixture stores
abstract characteristics of Beyond Style-owned parametric outputs — no
third-party artwork.
"""
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import generate_candidates  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText  # noqa: E402

NAMES = ["ميثة", "نورة", "محمد", "Amal", "Basma"]
OUT = pathlib.Path(__file__).resolve().parents[1] / "backend" / "tests" / "golden" / "golden_visual.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

golden = {}
for name in NAMES:
    src = ImmutableSourceText.create(name, confirmed=True)
    _, top = generate_candidates("d-quality", src, DEFAULT_RULES)
    golden[name] = {
        "top_candidate_ids": [c.candidate_id for c in top],
        "combined_geometry_sha256": hashlib.sha256(
            "".join(c.geometry_wkt for c in top).encode()
        ).hexdigest(),
        "families": sorted({c.recipe.dna["family"] for c in top if c.recipe.dna}),
        "compositions": sorted({c.recipe.composition for c in top}),
        "fonts": sorted({c.recipe.font_id for c in top}),
    }
    print(name, "families:", len(golden[name]["families"]), "compositions:", len(golden[name]["compositions"]))

OUT.write_text(json.dumps(golden, ensure_ascii=False, indent=1))
print("wrote", OUT)
