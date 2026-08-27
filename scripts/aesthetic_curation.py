#!/usr/bin/env python3
"""Aesthetic curation + combination/axis safety run.

Produces docs/evidence/aesthetic-curation/ and app/data/curation.json.
Everything written is either measured from real geometry/shaping, or
explicitly marked NOT_ASSESSED pending human review. Nothing is guessed.

Usage: python3 scripts/aesthetic_curation.py [--write]
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import build_candidate  # noqa: E402
from app.exporters.svg_exporter import export_proof_svg  # noqa: E402
from app.fonts.axes import classify_grid, safe_range, sweep_axis  # noqa: E402
from app.fonts.combinations import (  # noqa: E402
    check_combination, curated_combinations, production_safe_combinations,
)
from app.fonts.curation import PRODUCTS, CurationState  # noqa: E402
from app.fonts.glyph_variants import load_variants  # noqa: E402
from app.fonts.ot_discovery import discover  # noqa: E402
from app.fonts.registry import get_registry  # noqa: E402
from app.fonts.suitability import best_font_per_product, suitability_matrix  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText, RecipeParams  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "aesthetic-curation"
CURATION_FILE = ROOT / "backend" / "app" / "data" / "curation.json"

REVIEW_TEXTS = ["ع", "نورة", "ميثة", "محمد", "فاطمة", "حامد", "سلطان", "خالد", "مهرة"]
PHRASE = "كن ما تبحث عنه في عيون الآخرين"
SEVEN_NAMES = "حامد محمد سلطان ميثة حمد خالد مهرة"

#: The two feature sets a human has already reviewed and signed off — the
#: pre-existing curated sets from before OT discovery. Everything the
#: discovery run found is EXPERIMENTAL until Beyond Style reviews it.
HUMAN_REVIEWED = {"default"}


def curate_features() -> dict:
    lib = load_variants()
    features = {}
    for set_id, spec in lib["ot_feature_sets"].items():
        if not spec.get("safe_for_production", True):
            state, why = CurationState.HIDDEN, "failed the shaping regression"
        elif set_id in HUMAN_REVIEWED:
            state, why = CurationState.PRODUCTION_RECOMMENDED, "standard forms, in production use"
        elif spec.get("provenance") == "CURATED_VERIFIED_AGAINST_FONT_TABLES":
            state, why = CurationState.PRODUCTION_ALLOWED, (
                "hand-curated before OT discovery and verified against the font tables"
            )
        else:
            state, why = CurationState.EXPERIMENTAL, (
                "discovered by inspection; shaping-safe but not yet visually reviewed"
            )
        features[set_id] = {
            "state": state.value,
            "reason": why,
            "fonts": spec["fonts"],
            "provenance": spec.get("provenance", ""),
            "customer_visible": state.value in (
                CurationState.PRODUCTION_RECOMMENDED.value,
                CurationState.PRODUCTION_ALLOWED.value,
            ),
        }
    return features


def axis_report() -> dict:
    registry = get_registry()
    report = {}
    for record in registry.list():
        cap = discover(record.font_id, record.path)
        if not cap.variation_axes:
            continue
        entry = {"axes": [], "default": {}, "products": {}}
        for axis in cap.variation_axes:
            sweep = sweep_axis(record.path, axis)
            normal = classify_grid(sweep, small_size=False)
            entry["axes"].append({"axis": axis, "grid": normal})
            entry["default"][axis["tag"]] = safe_range(normal)
            for name, profile in PRODUCTS.items():
                cls = classify_grid(sweep, small_size=profile.small_size)
                entry["products"].setdefault(name, {})[axis["tag"]] = safe_range(cls)
        entry["generator_support"] = "NOT_YET_REACHABLE_BY_GENERATOR"
        entry["generator_note"] = (
            "arabic_engine/outline_extractor load each font at its default instance; "
            "these ranges are measured but cannot yet be rendered."
        )
        report[record.font_id] = entry
    return report


def seven_name_resolution() -> dict:
    """§9 — resolve the seven names WITHOUT weakening any constraint.

    Runs the REAL production path (`generate_candidates`, which applies the
    deterministic long-text adaptation: stacking, multi-line, larger
    envelope) rather than hand-built recipes, then reports which layout
    strategies actually survived the unmodified validator."""
    from app.engines.generator import generate_candidates

    source = ImmutableSourceText.create(SEVEN_NAMES, confirmed=True)
    everything, top = generate_candidates("seven", source, DEFAULT_RULES)
    valid = [c for c in everything if c.validation and c.validation.passed]

    def describe(c):
        return {
            "recipe_id": c.recipe.recipe_id,
            "font_id": c.recipe.font_id,
            "composition": c.recipe.composition,
            "max_lines": c.recipe.max_lines,
            "strategy": ("stacked_multi_line" if c.recipe.max_lines > 1 else "single_line"),
            "width_mm": round(c.features.width_mm, 2) if c.features else None,
            "height_mm": round(c.features.height_mm, 2) if c.features else None,
            "source_text_unchanged": c.identity_proof.verified,
        }

    strategies = sorted({describe(c)["strategy"] for c in valid})
    blocked = [
        {"recipe_id": c.recipe.recipe_id,
         "violations": [v.code for v in c.validation.violations][:3]}
        for c in everything if not (c.validation and c.validation.passed)
    ]
    return {
        "source_text": SEVEN_NAMES,
        "path": "production generate_candidates (deterministic long-text adaptation)",
        "constraints_weakened": False,
        "internal_candidates": len(everything),
        "valid_candidates": len(valid),
        "shown_top_n": len(top),
        "successful_strategies": strategies,
        "all_source_text_unchanged": all(c.identity_proof.verified for c in everything),
        "solutions": [describe(c) for c in top[:5]],
        "blocked_examples": blocked[:5],
        "outcome": "RESOLVED" if valid else "BLOCK_PRODUCTION_EXPORT",
    }


def golden_influence() -> dict:
    """§7 — what the two real manufactured cases contribute, and to what.
    Evidence priority is stated explicitly and no geometry is copied."""
    from app.data.golden_production_cases import GOLDEN_PRODUCTION_CASES

    influences = []
    for case in GOLDEN_PRODUCTION_CASES:
        influences.append({
            "case_id": case["case_id"],
            "evidence_tier": case["evidence_tier"],
            "product_type": case["product_type"],
            "influences": case["construction"],
            "lessons": case["lessons_learned"],
            "geometry_copied": False,
            "applies_to_products": (
                ["single_letter_earring", "drop_earring"]
                if "EARRING" in case["product_type"] else
                ["necklace", "pendant", "multi_name"]
            ),
        })
    return {
        "evidence_priority": [
            "MANUFACTURED_CUSTOMER_APPROVED", "WORKSHOP_APPROVED",
            "DESIGNER_APPROVED", "AI_AESTHETIC_OPINION",
        ],
        "note": "AI aesthetic opinion ranks last and is advisory only.",
        "cases": influences,
    }


def _sheet(title: str, rows: list[dict]) -> str:
    """One SVG review sheet: proofs laid out with their real metadata."""
    cell_w, cell_h, cols = 300, 200, 3
    n = len(rows)
    rows_n = (n + cols - 1) // cols or 1
    w, h = cols * cell_w, rows_n * cell_h + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="16" y="32" font-family="sans-serif" font-size="20" fill="#111">{title}</text>',
    ]
    for i, row in enumerate(rows):
        x, y = (i % cols) * cell_w, 50 + (i // cols) * cell_h
        parts.append(f'<g transform="translate({x},{y})">')
        parts.append(f'<rect width="{cell_w-8}" height="{cell_h-8}" fill="none" stroke="#ddd"/>')
        if row.get("path"):
            parts.append(
                f'<g transform="translate(12,24) scale({row["scale"]:.3f})">'
                f'<path d="{row["path"]}" fill="#111" fill-rule="evenodd"/></g>'
            )
        label = row["label"].replace("&", "&amp;").replace("<", "&lt;")
        parts.append(
            f'<text x="10" y="{cell_h-30}" font-family="monospace" font-size="10" fill="#444">{label}</text>'
        )
        status = row.get("status", "")
        colour = "#0a0" if row.get("ok") else "#b00"
        parts.append(
            f'<text x="10" y="{cell_h-16}" font-family="monospace" font-size="10" fill="{colour}">{status}</text>'
        )
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def _proof_rows(font_ids, texts, height=14.0, composition="baseline_bar"):
    from app.exporters.svg_exporter import geometry_to_path_d
    from shapely import wkt as _wkt

    rows = []
    for font_id in font_ids:
        for text in texts:
            source = ImmutableSourceText.create(text, confirmed=True)
            recipe = RecipeParams(
                recipe_id=f"sheet-{font_id}", name="sheet", font_id=font_id,
                composition=composition, target_height_mm=height,
                stroke_delta_mm=0.35, dot_strategy="merge",
                max_lines=3 if len(text.split()) > 2 else 1,
            )
            try:
                cand = build_candidate("sheet", source, recipe, DEFAULT_RULES)
                geom = _wkt.loads(cand.geometry_wkt)
                minx, miny, maxx, maxy = geom.bounds
                span = max(maxx - minx, maxy - miny, 1e-6)
                ok = bool(cand.validation and cand.validation.passed)
                rows.append({
                    "path": geometry_to_path_d(geom, maxy),
                    "scale": min(260 / span, 120 / max(maxy - miny, 1e-6)),
                    "label": f"{font_id} · {text[:18]} · {cand.features.width_mm:.0f}×{cand.features.height_mm:.0f}mm",
                    "status": ("MFG PASS" if ok else "MFG BLOCKED: " + ",".join(
                        v.code for v in cand.validation.violations[:2])) + " · EXPERIMENTAL",
                    "ok": ok,
                })
            except Exception as exc:
                rows.append({"path": "", "scale": 1, "label": f"{font_id} · {text[:18]}",
                             "status": f"ERROR {type(exc).__name__}", "ok": False})
    return rows


def main(write: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = get_registry()
    font_ids = [r.font_id for r in registry.list()]

    print("· product suitability matrix …")
    matrix = suitability_matrix(font_ids)
    best = best_font_per_product(matrix)

    print("· feature combinations …")
    combos = [check_combination(c) for c in curated_combinations()]
    safe = production_safe_combinations(combos)

    print("· variable-axis sweep …")
    axes = axis_report()

    print("· seven-name resolution …")
    seven = seven_name_resolution()

    print("· proof sheets …")
    for font_id in font_ids:
        sheet = _sheet(f"{font_id} — review sheet (EXPERIMENTAL, human review required)",
                       _proof_rows([font_id], REVIEW_TEXTS))
        (OUT / f"family-{font_id}.svg").write_text(sheet, encoding="utf-8")
    (OUT / "product-sheet.svg").write_text(
        _sheet("Product proofs — ع earring · نورة pendant · ميثة necklace · محمد cufflink",
               _proof_rows(["amiri-regular", "reem-kufi", "aref-ruqaa"],
                           ["ع", "نورة", "ميثة", "محمد"])), encoding="utf-8")
    (OUT / "long-text-sheet.svg").write_text(
        _sheet("Phrase + seven names",
               _proof_rows(["amiri-regular", "scheherazade-new"], [PHRASE, SEVEN_NAMES], 24, "plate_rect")),
        encoding="utf-8")

    curation = {
        "note": ("Curation states. Discovered OT features stay EXPERIMENTAL until a human at "
                 "Beyond Style reviews the proof sheets — no aesthetic judgement is automated."),
        "features": curate_features(),
        "axis_ranges": {
            fid: {"default": entry["default"], "products": entry["products"],
                  "generator_support": entry["generator_support"]}
            for fid, entry in axes.items()
        },
        "safe_combinations": [
            {"font_id": c["font_id"], "tags": c["tags"], "kind": c["kind"]} for c in safe
        ],
    }
    scores = {
        "note": ("10 of 13 dimensions are measured from real geometry; 3 are genuine aesthetic "
                 "judgements returned as NOT_ASSESSED pending human review."),
        "dimensions_measured": sorted(
            k for k, v in matrix[0]["dimensions"].items() if v["status"] == "MEASURED"
        ) if matrix else [],
        "dimensions_awaiting_human_review": sorted(
            k for k, v in matrix[0]["dimensions"].items() if v["status"] == "NOT_ASSESSED"
        ) if matrix else [],
        "best_font_per_product": best,
        "matrix": matrix,
    }

    if write:
        # Axis ranges are produced by scripts/axis_plumbing.py from real
        # geometry; preserve them rather than dropping them on regeneration.
        if CURATION_FILE.is_file():
            existing = json.loads(CURATION_FILE.read_text())
            if "product_axis_ranges" in existing:
                curation["product_axis_ranges"] = existing["product_axis_ranges"]
        (OUT / "scores.json").write_text(json.dumps(scores, indent=1, ensure_ascii=False) + "\n")
        (OUT / "curation.json").write_text(json.dumps(curation, indent=1, ensure_ascii=False) + "\n")
        (OUT / "combination-matrix.json").write_text(
            json.dumps({"tested": len(combos), "results": combos}, indent=1, ensure_ascii=False) + "\n")
        (OUT / "variable-axis-safety.json").write_text(
            json.dumps(axes, indent=1, ensure_ascii=False) + "\n")
        (OUT / "seven-name-report.json").write_text(
            json.dumps(seven, indent=1, ensure_ascii=False) + "\n")
        (OUT / "golden-production-influence.json").write_text(
            json.dumps(golden_influence(), indent=1, ensure_ascii=False) + "\n")
        CURATION_FILE.write_text(json.dumps(curation, indent=1, ensure_ascii=False) + "\n")

    from collections import Counter
    print(f"\ncombinations: {Counter(c['verdict'] for c in combos)}")
    print(f"curation:     {Counter(v['state'] for v in curation['features'].values())}")
    print(f"seven names:  {seven['outcome']} "
          f"({seven['valid_candidates']}/{seven['internal_candidates']} valid, "
          f"strategies={seven['successful_strategies']})")
    print(f"best/product: {len(best)} products have a manufacturable best font")
    if not write:
        print("\n(dry run — pass --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
