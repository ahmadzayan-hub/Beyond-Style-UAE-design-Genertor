#!/usr/bin/env python3
"""Manufacturing sweep → script recipes for registry fonts.

For every rights-cleared font without recipes, build the golden names over
a small parameter spread (composition × height), validate with the real
manufacturing validator, keep the best-passing configuration as that
font's recipe(s) in app/data/script_recipes.json, and record the pass rate
as its manufacturing score. No design is invented by hand; the numbers are
measured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import build_candidate  # noqa: E402
from app.fonts.registry import get_registry  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams  # noqa: E402

RECIPES = ROOT / "backend/app/data/script_recipes.json"
NAMES = ("ميثه", "نورة", "محمد", "حامد", "خالد")
SWEEP = [
    ("bare", 11.0, "top"), ("bare", 13.0, "top"),
    ("baseline_bar", 11.0, "left_right"), ("underline_bar", 12.0, "left_right"),
]


def sweep_font(font_id: str, script_family: str, tags: list[str]) -> tuple[list[dict], float]:
    srcs = [ImmutableSourceText.create(n, confirmed=True) for n in NAMES]
    results = []
    for comp, height, loops in SWEEP:
        recipe = RecipeParams(
            recipe_id=f"{font_id}-{comp}-{int(height)}", name=f"{font_id} {comp}", font_id=font_id,
            composition=comp, stroke_delta_mm=0.25, dot_strategy="bridge", connector_height_mm=1.2,
            loops=loops, frame_margin_mm=2.0, target_height_mm=height, kashida_count=0,
        )
        passed = 0
        for src in srcs:
            try:
                c = build_candidate("sweep", src, recipe, DEFAULT_RULES)
                passed += int(bool(c.validation and c.validation.passed))
            except Exception:  # noqa: BLE001
                pass
        results.append((passed / len(NAMES), comp, height, loops, recipe))
    results.sort(key=lambda r: (-r[0], r[1]))
    best_rate = results[0][0]
    keep = [r for r in results if r[0] >= max(0.6, best_rate - 0.2)][:2]
    recipes = []
    for rate, comp, height, loops, recipe in keep:
        d = recipe.model_dump()
        d["dna"] = {
            "family": f"{script_family}-{comp}", "visual_purpose": f"{recipe.name} ({', '.join(tags[:3])})",
            "products": ["pendant", "necklace", "bracelet"] if loops == "left_right" else ["pendant", "necklace", "earring", "keychain"],
            "text_length_chars": [1, 14],
            "manufacturing_constraints": {"min_target_height_mm": height - 2, "rules_profile": DEFAULT_RULES.profile_name},
            "rights": "BEYOND_STYLE_ORIGINAL_PARAMETRIC",
            "manufacturing_validated": f"sweep 2026-09-05: {int(rate * len(NAMES))}/{len(NAMES)} golden names pass",
            "manufacturing_score": rate,
        }
        recipes.append(d)
    return recipes, best_rate


def main() -> int:
    lib = json.loads(RECIPES.read_text(encoding="utf-8"))
    have = {r["font_id"] for r in lib["recipes"]}
    scores = lib.setdefault("manufacturing_scores", {})
    added = 0
    for rec in get_registry().list():
        if rec.font_id in have or not rec.commercial_production_allowed:
            continue
        recipes, rate = sweep_font(rec.font_id, rec.script_family, rec.style_tags)
        scores[rec.font_id] = rate
        lib["recipes"].extend(recipes)
        added += len(recipes)
        print(f"{rec.font_id:20s} best pass {rate:.2f} → {len(recipes)} recipe(s)")
    lib["library_version"] = "0.2.0"
    RECIPES.write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("added", added, "recipes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
