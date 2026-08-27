"""Product-specific jewellery suitability.

A font is never given one universal score. The same face is measured
separately against each product envelope, because what makes a beautiful
medallion makes an illegible ring.

Ten of the thirteen dimensions are MEASURED from real built geometry and
each records its method. Three — CalligraphicGrace, OrnamentalPotential,
LuxuryFeel — are genuine aesthetic judgements and are returned as `None`
with status NOT_ASSESSED, awaiting human review of the proof sheets. They
are never guessed, and the aggregate says how many were measured.
"""
from __future__ import annotations

import statistics

from ..config import DEFAULT_RULES, get_profile
from ..engines.generator import build_candidate
from ..schemas.jewellery_design import ImmutableSourceText, RecipeParams
from .curation import COMPUTED_DIMENSIONS, HUMAN_REVIEW_DIMENSIONS, PRODUCTS, ProductProfile


def _recipe(font_id: str, profile: ProductProfile, composition: str, **over) -> RecipeParams:
    return RecipeParams(
        recipe_id=f"suitability-{font_id}-{profile.product}-{composition}",
        name=f"{font_id} for {profile.product}",
        font_id=font_id,
        composition=composition,
        target_height_mm=profile.target_height_mm,
        stroke_delta_mm=over.pop("stroke_delta_mm", 0.35),
        dot_strategy=over.pop("dot_strategy", "merge"),
        loops=over.pop("loops", "top" if "earring" in profile.product else "none"),
        max_lines=over.pop("max_lines", 3 if profile.multi_name else 1),
        **over,
    )


def _rhythm(runs) -> float:
    """Evenness of glyph advances — a steady rhythm reads as considered,
    an erratic one as accidental. 1.0 = perfectly even."""
    advances = [g.x_advance_mm for r in runs for g in r.glyphs if g.x_advance_mm > 0]
    if len(advances) < 2:
        return 1.0
    mean = statistics.fmean(advances)
    if mean <= 0:
        return 0.0
    cv = statistics.pstdev(advances) / mean
    return max(0.0, min(1.0, 1.0 - cv))


def _balance(geom) -> float:
    """How close the ink's centroid sits to the bounding-box centre."""
    if geom.is_empty:
        return 0.0
    minx, miny, maxx, maxy = geom.bounds
    w, h = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    c = geom.centroid
    dx = abs(c.x - (minx + maxx) / 2) / w
    dy = abs(c.y - (miny + maxy) / 2) / h
    return max(0.0, 1.0 - 2 * (dx + dy) / 2)


def measure(font_id: str, profile: ProductProfile) -> dict:
    """Build the font into this product's envelope and measure it."""
    source = ImmutableSourceText.create(profile.representative_text, confirmed=True)
    profile_loops = "top" if "earring" in profile.product else "none"
    rules = DEFAULT_RULES
    try:
        rules = get_profile("pendant", "silver-925")
    except Exception:
        pass

    # A font is judged over a small parameter spread, not one arbitrary
    # setting — otherwise "unmanufacturable" would just mean "I picked a
    # bad stroke". Long text also gets the same stacking the production
    # generator applies, so multi-name products are measured fairly.
    words = len(profile.representative_text.split())
    # Long-text products (multi-name, medallion phrase) go through the REAL
    # production long-text adaptation rather than a hand-built recipe, so
    # the benchmark measures what production would actually produce.
    if words > 2:
        from ..engines.generator import generate_candidates

        everything, _ = generate_candidates(f"suit-{font_id}", source, rules)
        same_font = [c for c in everything if c.recipe.font_id == font_id]
        attempts = [{
            "path": "production_long_text_adaptation",
            "recipe_id": c.recipe.recipe_id,
            "composition": c.recipe.composition,
            "max_lines": c.recipe.max_lines,
            "validation_passed": bool(c.validation and c.validation.passed),
            "violations": [v.code for v in (c.validation.violations if c.validation else [])][:4],
            "width_mm": round(c.features.width_mm, 2) if c.features else None,
            "height_mm": round(c.features.height_mm, 2) if c.features else None,
        } for c in same_font]
        built_ok = [(c, bool(c.validation and c.validation.passed)) for c in same_font]
        if built_ok:
            return _score(font_id, profile, attempts, built_ok)

    lines = 3 if words > 2 else 1
    # Connector strategy matters more than stroke: letters left unjoined
    # fail DISCONNECTED_COMPONENT regardless of the face. Both the product's
    # own composition and the connector-bearing baseline bar are tried, so
    # the measurement reflects the font, not one unlucky layout.
    compositions = list(dict.fromkeys(profile.preferred_compositions + ("baseline_bar",)))
    connectors = [(profile_loops, "merge"), ("left_right", "bridge")]
    attempts, built_ok = [], []
    for composition in compositions:
        for stroke in (0.35, 0.45):
            for loops, dots in connectors:
                try:
                    recipe = _recipe(font_id, profile, composition, stroke_delta_mm=stroke,
                                     max_lines=lines, loops=loops, dot_strategy=dots)
                    cand = build_candidate("suit", source, recipe, rules)
                except Exception as exc:
                    attempts.append({"composition": composition, "stroke_delta_mm": stroke,
                                     "loops": loops, "dot_strategy": dots,
                                     "error": f"{type(exc).__name__}: {exc}"})
                    continue
                passed = bool(cand.validation and cand.validation.passed)
                attempts.append({
                    "composition": composition, "stroke_delta_mm": stroke,
                    "loops": loops, "dot_strategy": dots, "max_lines": lines,
                    "validation_passed": passed,
                    "violations": [v.code for v in (cand.validation.violations if cand.validation else [])][:4],
                    "width_mm": round(cand.features.width_mm, 2) if cand.features else None,
                    "height_mm": round(cand.features.height_mm, 2) if cand.features else None,
                })
                built_ok.append((cand, passed))

    return _score(font_id, profile, attempts, built_ok)


def _score(font_id: str, profile: ProductProfile, attempts: list, built_ok: list) -> dict:
    """Shared scoring for both the parametric sweep and the production
    long-text path, so neither can drift into its own definition."""
    if not built_ok:
        return {
            "font_id": font_id, "product": profile.product,
            "buildable": False, "attempts": attempts,
            "dimensions": {k: {"score": None, "status": "NOT_MEASURED",
                               "method": v} for k, v in COMPUTED_DIMENSIONS.items()},
        }

    # Prefer a manufacturable build; fall back to the first that built.
    cand, passed = next((c for c in built_ok if c[1]), built_ok[0])
    geom = cand.geometry_wkt
    from shapely import wkt as _wkt

    shape = _wkt.loads(geom) if geom else None
    feats = cand.features
    fill = feats.fill_ratio if feats else 0.0
    holes = feats.hole_count if feats else 0
    parts = len(getattr(shape, "geoms", [])) if shape is not None else 0
    pass_rate = sum(1 for _, ok in built_ok if ok) / len(built_ok)
    within_envelope = bool(feats and feats.width_mm <= profile.max_width_mm)

    dims = {
        "Readability": min(1.0, (1.0 if cand.identity_proof.verified else 0.0)
                           * (1.0 - min(fill, 1.0) * 0.5)),
        "Rhythm": _rhythm(cand.shaped_runs),
        "Balance": _balance(shape) if shape is not None else 0.0,
        "NegativeSpace": max(0.0, 1.0 - fill),
        "StrokeRobustness": 1.0 if passed else 0.0,
        "DotIslandRisk": max(0.0, 1.0 - 0.08 * max(parts - 1, 0)),
        "Compactness": max(0.0, 1.0 - abs(fill - 0.45)),
        "SmallSizeSuitability": (1.0 if passed else 0.0) if profile.small_size else
                                (0.75 if passed else 0.0),
        "MultiNameSuitability": (1.0 if passed else 0.0) if profile.multi_name else
                                (0.5 if passed else 0.0),
        "ManufacturingHarmony": pass_rate * (1.0 if within_envelope else 0.6),
    }
    scored = {
        name: {"score": round(value, 4), "status": "MEASURED",
               "method": COMPUTED_DIMENSIONS[name]}
        for name, value in dims.items()
    }
    scored.update({
        name: {"score": None, "status": "NOT_ASSESSED", "method": method}
        for name, method in HUMAN_REVIEW_DIMENSIONS.items()
    })
    measured = [v["score"] for v in scored.values() if v["score"] is not None]
    return {
        "font_id": font_id,
        "product": profile.product,
        "buildable": True,
        "manufacturable": passed,
        "within_envelope": within_envelope,
        "attempts": attempts,
        "dimensions": scored,
        "measured_dimension_count": len(measured),
        "unassessed_dimension_count": len(HUMAN_REVIEW_DIMENSIONS),
        # Deliberately named "computed", not "aesthetic": it contains no
        # taste judgement, and a manufacturing failure zeroes the two
        # dimensions that matter most rather than being averaged away.
        "computed_suitability": round(statistics.fmean(measured), 4) if measured else None,
        "human_review_required": True,
    }


def suitability_matrix(font_ids: list[str]) -> list[dict]:
    return [measure(f, p) for f in font_ids for p in PRODUCTS.values()]


def best_font_per_product(matrix: list[dict]) -> dict[str, dict]:
    """Ranked on measured dimensions only, and only among manufacturable
    builds — a pretty score never promotes an unmanufacturable font."""
    out: dict[str, dict] = {}
    for row in matrix:
        if not row.get("manufacturable") or row.get("computed_suitability") is None:
            continue
        best = out.get(row["product"])
        if best is None or row["computed_suitability"] > best["computed_suitability"]:
            out[row["product"]] = {
                "font_id": row["font_id"],
                "computed_suitability": row["computed_suitability"],
                "human_review_required": True,
            }
    return out
