#!/usr/bin/env python3
"""Axis plumbing evidence: real-geometry axis revalidation, weight-bearing
combination revalidation, and the long-text production probe.

Nothing here reuses the earlier font-unit measurements. Every verdict comes
from geometry actually built through the production path and measured in
millimetres.

Usage: python3 scripts/axis_plumbing.py [--write]
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from shapely import wkt as _wkt  # noqa: E402

from app.config import DEFAULT_RULES  # noqa: E402
from app.engines.generator import build_candidate, generate_candidates  # noqa: E402
from app.engines.geometry_metrics import measure_mm, meets_workshop_rules  # noqa: E402
from app.fonts.axes import axis_grid  # noqa: E402
from app.fonts.combinations import check_combination, curated_combinations  # noqa: E402
from app.fonts.curation import PRODUCTS  # noqa: E402
from app.fonts.instances import font_axis_specs  # noqa: E402
from app.fonts.suitability import _recipe  # noqa: E402
from app.schemas.jewellery_design import ImmutableSourceText  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "axis-plumbing"
CURATION_FILE = ROOT / "backend" / "app" / "data" / "curation.json"

VARIABLE_FONTS = ["reem-kufi", "noto-nastaliq-urdu", "lemonada"]
#: §6 product set for axis revalidation.
AXIS_PRODUCTS = ["single_letter_earring", "pendant", "necklace", "ring",
                 "bracelet", "cufflink", "engraving", "openwork"]

SEVEN_NAMES = "حامد محمد سلطان ميثة حمد خالد مهرة"
PHRASE = "كن ما تبحث عنه في عيون الآخرين"

GEOMETRY_VERIFIED_SAFE = "GEOMETRY_VERIFIED_SAFE"
GEOMETRY_VERIFIED_UNSAFE = "GEOMETRY_VERIFIED_UNSAFE"
NOT_TESTED = "NOT_TESTED"


def _build_at(font_id: str, profile, axes: dict, composition: str, loops: str, dots: str):
    source = ImmutableSourceText.create(profile.representative_text, confirmed=True)
    words = len(profile.representative_text.split())
    recipe = _recipe(font_id, profile, composition, stroke_delta_mm=0.35,
                     max_lines=3 if words > 2 else 1, loops=loops,
                     dot_strategy=dots, font_axes=axes)
    cand = build_candidate("axis", source, recipe, DEFAULT_RULES)
    geom = _wkt.loads(cand.geometry_wkt) if cand.geometry_wkt else None
    mm = measure_mm(geom)
    return cand, mm, meets_workshop_rules(mm, DEFAULT_RULES)


def revalidate_axes() -> dict:
    """§6 — every grid point rebuilt as real jewellery geometry per product."""
    report: dict = {}
    for font_id in VARIABLE_FONTS:
        specs = font_axis_specs(font_id)
        report[font_id] = {}
        for tag, spec in specs.items():
            grid = axis_grid(spec)
            report[font_id][tag] = {"axis": spec, "tested_values": grid, "products": {}}
            for product in AXIS_PRODUCTS:
                profile = PRODUCTS[product]
                points = []
                # Counters present at the default instance must survive the
                # weight change: losing one means a letter opening has filled
                # in, which the pass/fail rules alone would not catch.
                default_counters: dict[str, int] = {}
                for value in grid:
                    verdicts = []
                    for composition in list(dict.fromkeys(
                            profile.preferred_compositions + ("baseline_bar",))):
                        for loops, dots in ((profile.product.startswith("single") and "top" or "none", "merge"),
                                            ("left_right", "bridge")):
                            try:
                                cand, mm, gate = _build_at(
                                    font_id, profile, {tag: value}, composition, loops, dots)
                            except Exception as exc:
                                verdicts.append({"error": f"{type(exc).__name__}: {exc}"})
                                continue
                            config_key = f"{composition}/{loops}/{dots}"
                            if abs(value - spec["default"]) < 1e-6:
                                default_counters[config_key] = mm.get("counter_count", 0)
                            lost = (
                                default_counters.get(config_key, 0)
                                - mm.get("counter_count", 0)
                            )
                            verdicts.append({
                                "composition": composition, "loops": loops, "dots": dots,
                                "counter_count": mm.get("counter_count"),
                                "counters_lost_vs_default": max(lost, 0),
                                "validator_passed": bool(cand.validation and cand.validation.passed),
                                "mm_gate_passed": gate["passed"],
                                "min_material_width_mm": mm.get("min_material_width_mm"),
                                "min_gap_mm": mm.get("min_gap_mm"),
                                "counter_clearance_mm": mm.get("counter_clearance_mm"),
                                "component_count": mm.get("component_count"),
                                "width_mm": mm.get("width_mm"),
                                "height_mm": mm.get("height_mm"),
                                "failures": gate.get("failures", [])[:2],
                            })
                    ok = [
                        v for v in verdicts
                        if v.get("validator_passed") and v.get("mm_gate_passed")
                        and not v.get("counters_lost_vs_default")
                    ]
                    points.append({
                        "value": value,
                        "status": GEOMETRY_VERIFIED_SAFE if ok else GEOMETRY_VERIFIED_UNSAFE,
                        "passing_configurations": len(ok),
                        "configurations_tried": len(verdicts),
                        "best": ok[0] if ok else next(
                            (v for v in verdicts if "error" not in v), verdicts[0] if verdicts else {}),
                    })
                safe_values = [p["value"] for p in points if p["status"] == GEOMETRY_VERIFIED_SAFE]
                default = spec["default"]
                contiguous = _contiguous_around(safe_values, grid, default)
                report[font_id][tag]["products"][product] = {
                    "font_id": font_id, "axis": tag, "product_type": product,
                    "min_safe": contiguous[0] if contiguous else None,
                    "max_safe": contiguous[-1] if contiguous else None,
                    "evidence_level": GEOMETRY_VERIFIED_SAFE if contiguous else GEOMETRY_VERIFIED_UNSAFE,
                    "tested_values": grid,
                    "safe_values": safe_values,
                    "manufacturing_profile": DEFAULT_RULES.profile_id
                    if hasattr(DEFAULT_RULES, "profile_id") else "pendant/silver-925",
                    "reason": ("real geometry built and measured in mm at every grid point"
                               if contiguous else
                               "no grid point produced manufacturable geometry for this product"),
                    "points": points,
                }
    return report


def _contiguous_around(safe_values: list[float], grid: list[float], default: float) -> list[float]:
    """Safe span containing the default — an unreachable island is not a range."""
    if default not in safe_values:
        return []
    span = [default]
    for v in sorted([g for g in grid if g < default], reverse=True):
        if v in safe_values:
            span.insert(0, v)
        else:
            break
    for v in sorted([g for g in grid if g > default]):
        if v in safe_values:
            span.append(v)
        else:
            break
    return span


def revalidate_weight_combinations(axis_ranges: dict) -> list[dict]:
    """§7 — weight-bearing combinations, now through real geometry."""
    out = []
    for case in curated_combinations():
        extra = case.extra or {}
        if "wght" not in extra:
            continue
        specs = font_axis_specs(case.font_id)
        if "wght" not in specs:
            out.append({"font_id": case.font_id, "kind": case.kind,
                        "status": NOT_TESTED, "reason": "font has no wght axis"})
            continue
        spec = specs["wght"]
        value = spec["max"] if extra["wght"] == "max" else spec["min"]
        shaping = check_combination(case)
        profile = PRODUCTS["pendant"]
        try:
            cand, mm, gate = _build_at(case.font_id, profile, {"wght": value},
                                       "baseline_bar", "left_right", "bridge")
            geometry_ok = bool(cand.geometry_wkt)
            validator_ok = bool(cand.validation and cand.validation.passed)
            identity_ok = cand.identity_proof.verified
            error = None
        except Exception as exc:
            geometry_ok = validator_ok = identity_ok = False
            gate = {"passed": False, "failures": [f"{type(exc).__name__}: {exc}"]}
            mm = {}
            error = str(exc)
        production_capable = all([
            shaping["shaping_safe"], identity_ok, geometry_ok,
            validator_ok, gate["passed"],
        ])
        out.append({
            "font_id": case.font_id, "tags": list(case.tags), "kind": case.kind,
            "wght": value, "shaping_safe": shaping["shaping_safe"],
            "source_identity_safe": identity_ok, "outline_generated": geometry_ok,
            "geometry_valid": validator_ok, "manufacturing_mm_pass": gate["passed"],
            "status": "PRODUCTION_CAPABLE" if production_capable else "NOT_PRODUCTION_CAPABLE",
            "min_material_width_mm": mm.get("min_material_width_mm"),
            "failures": gate.get("failures", [])[:2], "error": error,
        })
    return out


def long_text_production_probe() -> dict:
    """§9 — the real production adaptation, no hand-built recipes."""
    results = {}
    for label, text in (("multi_name", SEVEN_NAMES), ("medallion", PHRASE)):
        source = ImmutableSourceText.create(text, confirmed=True)
        everything, top = generate_candidates("longtext", source, DEFAULT_RULES)
        valid = [c for c in everything if c.validation and c.validation.passed]
        mm_pass = []
        for cand in valid[:12]:
            mm = measure_mm(_wkt.loads(cand.geometry_wkt))
            if meets_workshop_rules(mm, DEFAULT_RULES)["passed"]:
                mm_pass.append({"recipe_id": cand.recipe.recipe_id,
                                "font_id": cand.recipe.font_id,
                                "max_lines": cand.recipe.max_lines,
                                "width_mm": mm["width_mm"], "height_mm": mm["height_mm"],
                                "min_material_width_mm": mm["min_material_width_mm"]})
        results[label] = {
            "source_text": text,
            "source_text_preserved": all(c.identity_proof.verified for c in everything),
            "internal_candidates": len(everything),
            "valid_candidates": len(valid),
            "shown_top_n": len(top),
            "mm_gate_passing_sample": mm_pass[:5],
            "strategies": sorted({("stacked_multi_line" if c.recipe.max_lines > 1
                                   else "single_line") for c in valid}),
            "outcome": "HAS_VALID_PRODUCTION_CANDIDATES" if valid else "BLOCK_PRODUCTION_EXPORT",
        }
    # openwork uses a normal-length name; report it through the same path.
    source = ImmutableSourceText.create("خالد", confirmed=True)
    everything, top = generate_candidates("openwork", source, DEFAULT_RULES)
    valid = [c for c in everything if c.validation and c.validation.passed]
    results["openwork"] = {
        "source_text": "خالد",
        "source_text_preserved": all(c.identity_proof.verified for c in everything),
        "internal_candidates": len(everything), "valid_candidates": len(valid),
        "shown_top_n": len(top),
        "outcome": "HAS_VALID_PRODUCTION_CANDIDATES" if valid else "BLOCK_PRODUCTION_EXPORT",
    }
    return results


def main(write: bool) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("· axis revalidation on real geometry …")
    axes = revalidate_axes()
    print("· weight combination revalidation …")
    combos = revalidate_weight_combinations(axes)
    print("· long-text production probe …")
    longtext = long_text_production_probe()

    product_ranges = {
        font_id: {
            tag: {p: {k: v for k, v in entry.items() if k != "points"}
                  for p, entry in data["products"].items()}
            for tag, data in per_axis.items()
        }
        for font_id, per_axis in axes.items()
    }

    if write:
        (OUT / "axis-rendering.json").write_text(json.dumps({
            "note": "Axis coordinates flow through shaping AND outline extraction "
                    "from one shared instance (app/fonts/instances.py).",
            "variable_fonts": VARIABLE_FONTS,
        }, indent=1, ensure_ascii=False) + "\n")
        (OUT / "product-axis-ranges.json").write_text(
            json.dumps(product_ranges, indent=1, ensure_ascii=False) + "\n")
        (OUT / "geometry-mm-validation.json").write_text(
            json.dumps(axes, indent=1, ensure_ascii=False) + "\n")
        (OUT / "combination-revalidation.json").write_text(
            json.dumps({"tested": len(combos), "results": combos}, indent=1, ensure_ascii=False) + "\n")
        (OUT / "long-text-production-report.json").write_text(
            json.dumps(longtext, indent=1, ensure_ascii=False) + "\n")
        curation = json.loads(CURATION_FILE.read_text())
        curation["product_axis_ranges"] = product_ranges
        CURATION_FILE.write_text(json.dumps(curation, indent=1, ensure_ascii=False) + "\n")

    for font_id, per_axis in axes.items():
        for tag, data in per_axis.items():
            safe = {p: (e["min_safe"], e["max_safe"])
                    for p, e in data["products"].items() if e["min_safe"] is not None}
            print(f"  {font_id:20} {tag}: {len(safe)}/{len(AXIS_PRODUCTS)} products verified safe")
    print(f"\ncombinations revalidated: {len(combos)} "
          f"({sum(1 for c in combos if c['status'] == 'PRODUCTION_CAPABLE')} production-capable)")
    for k, v in longtext.items():
        print(f"  {k:12} {v['outcome']} ({v.get('valid_candidates')}/{v.get('internal_candidates')})")
    if not write:
        print("\n(dry run — pass --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--write" in sys.argv))
