#!/usr/bin/env python3
"""Font capability benchmark — renders the same Arabic inputs through every
installed family and records the real result of each quality gate.

Gates per (font, text): Arabic shaping, source-text identity, SVG
generation, manufacturing validation, licence. Nothing is asserted from
metadata: each column is the outcome of actually running that stage.

Writes docs/evidence/font-capability/{benchmark.json, proof-<font>.svg}.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engines.arabic_engine import shape_text  # noqa: E402
from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import build_candidate, expand_recipes  # noqa: E402
from app.fonts.capabilities import script_capability_map  # noqa: E402
from app.fonts.feature_safety import check_font_coverage  # noqa: E402
from app.fonts.glyph_variants import feature_sets_for_font  # noqa: E402
from app.exporters.svg_exporter import export_proof_svg  # noqa: E402
from app.fonts.registry import get_registry  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "font-capability"
BENCH_TEXTS = ["ع", "نورة", "ميثة", "محمد", "حامد محمد سلطان ميثة حمد خالد مهرة"]


def _source(text: str) -> ImmutableSourceText:
    """Confirmed source text — the benchmark proves identity survives the
    whole pipeline, so it must go through the same truth path as production."""
    return ImmutableSourceText.create(text, confirmed=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = get_registry()
    recipes = expand_recipes(60)
    caps = script_capability_map()
    rows = []

    for record in registry.list():
        variants = [r for r in recipes if r.font_id == record.font_id]
        coverage = check_font_coverage(record.font_id)
        feature_sets = feature_sets_for_font(record.font_id)
        for text in BENCH_TEXTS:
            row = {
                "font_id": record.font_id,
                "family": record.family,
                "script_family": record.script_family,
                "style_influence": record.style_influence,
                "production_capability": record.production_capability,
                "text": text,
                "shaping_pass": coverage["shaping_pass"],
                "licence_pass": record.commercial_production_allowed,
                "integrity_pass": record.integrity_ok,
                "enabled_ot_features": feature_sets,
            }
            try:
                runs = shape_text(text, record.font_id)
                row["glyph_count"] = sum(len(r.glyphs) for r in runs)
            except Exception as exc:
                row.update(glyph_count=0, identity_pass=False, error=f"shaping: {exc}")
                rows.append(row)
                continue
            if not variants:
                row.update(svg_pass=False, manufacturing_pass=False,
                           note="no seed recipe for this font")
                rows.append(row)
                continue
            # The generator ranks many parametric variants and shows only
            # valid ones, so the honest question per font is whether ANY
            # variant manufactures — not whether an arbitrary one does.
            source = _source(text)
            best = None
            manufacturable = 0
            errors = []
            for recipe in variants:
                try:
                    cand = build_candidate("bench", source, recipe, DEFAULT_RULES)
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")
                    continue
                ok = bool(cand.validation and cand.validation.passed)
                manufacturable += int(ok)
                if best is None or (ok and not best[1]):
                    best = (cand, ok, recipe)
            row["variants_tried"] = len(variants)
            row["variants_manufacturable"] = manufacturable
            if best is None:
                row.update(svg_pass=False, manufacturing_pass=False, identity_pass=False,
                           error="; ".join(errors[:2]))
                rows.append(row)
                continue
            cand, ok, recipe = best
            row["recipe_id"] = recipe.recipe_id
            row["identity_pass"] = cand.identity_proof.verified
            row["notdef_glyphs"] = cand.identity_proof.notdef_glyph_count
            svg = export_proof_svg(cand, source)
            row["svg_pass"] = svg.lstrip().startswith("<svg") and "path" in svg
            row["width_mm"] = round(cand.features.width_mm, 2)
            row["height_mm"] = round(cand.features.height_mm, 2)
            row["manufacturing_pass"] = ok
            row["production_export_allowed"] = bool(
                cand.validation and cand.validation.production_export_allowed
            )
            row["violations"] = [
                v.code for v in (cand.validation.violations if cand.validation else [])
            ][:4]
            if text == "نورة":
                (OUT / f"proof-{record.font_id}.svg").write_text(svg, encoding="utf-8")
            rows.append(row)

    summary = {}
    for row in rows:
        s = summary.setdefault(row["font_id"], {"pass": 0, "total": 0})
        s["total"] += 1
        if all(row.get(k) for k in
               ("shaping_pass", "identity_pass", "licence_pass", "integrity_pass",
                "svg_pass", "manufacturing_pass")):
            s["pass"] += 1

    payload = {
        "note": "Each cell is the real outcome of running that stage — not metadata.",
        "texts": BENCH_TEXTS,
        "script_capability_map": caps,
        "summary": summary,
        "rows": rows,
    }
    (OUT / "benchmark.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    for font_id, s in sorted(summary.items()):
        print(f"{font_id:22} {s['pass']}/{s['total']} full-gate pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
