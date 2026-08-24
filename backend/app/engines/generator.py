"""Deterministic candidate generator + diversity scorer.

Expands the seed recipe library along fixed variation axes to produce ≥30
structured candidates per request, shapes/builds/validates each one, then
selects a maximally diverse top-N by greedy max-min distance over a
normalized feature space. No randomness: identical input → identical output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import GENERATOR_VERSION, WorkshopRules
from ..fonts.registry import get_registry
from ..schemas.jewellery_design import (
    CandidateFeatures,
    DesignCandidate,
    ImmutableSourceText,
    RecipeParams,
)
from .arabic_engine import (
    apply_kashida,
    remap_runs_to_source,
    shape_multiline,
    shape_text,
    verify_identity,
)
from .geometry_engine import compose
from .validator import validate

RECIPES_FILE = Path(__file__).resolve().parent.parent / "data" / "design_recipes.json"

COMPOSITION_CLASSES = {
    "bare": 0,
    "baseline_bar": 1,
    "underline_bar": 2,
    "plate_oval": 3,
    "plate_rect": 4,
    "frame_circle": 5,
    "frame_rect": 6,
    "top_bar": 7,
}
LOOPS_CLASSES = {"none": 0, "top": 1, "left_right": 2}


def load_recipe_library() -> dict:
    return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))


def expand_recipes(min_count: int = 30) -> list[RecipeParams]:
    """Curated bases first (each has a distinct visual purpose); a small
    deterministic set of stroke/spacing variants adds parameter spread.
    No filler generation."""
    lib = load_recipe_library()
    bases = [RecipeParams(**r) for r in lib["recipes"]]
    axes = lib["variation_axes"]
    variants: list[RecipeParams] = list(bases)
    i = 0
    while len(variants) < max(min_count, len(bases) + 8):
        base = bases[i % len(bases)]
        ds = axes["stroke_delta_mm"][1 + (i // len(bases)) % (len(axes["stroke_delta_mm"]) - 1)]
        variants.append(
            base.model_copy(
                update={
                    "recipe_id": f"{base.recipe_id}.v{i}",
                    "stroke_delta_mm": round(base.stroke_delta_mm + ds, 3),
                }
            )
        )
        i += 1
    return variants


def _adapt_for_text_length(recipes: list[RecipeParams], text: str) -> list[RecipeParams]:
    """Deterministic long-text adaptation.

    9–8+ letters, ≤2 words: bolder strokes + larger piece (single line).
    3+ words: convert layout-capable recipes to stacked multi-line (2 or 3
    lines by word count, alternating for diversity); plates/frames keep
    their composition around the stacked block. Kashida is disabled on
    stacked text (elongation fights balanced line widths)."""
    n = sum(1 for c in text if not c.isspace())
    words = [w for w in text.split(" ") if w]
    if n <= 8:
        return recipes
    if len(words) <= 2:
        return [
            r.model_copy(
                update={
                    "stroke_delta_mm": round(r.stroke_delta_mm + 0.2, 3),
                    "target_height_mm": r.target_height_mm + 4.0,
                }
            )
            for r in recipes
        ]
    out = []
    base_lines = 3 if len(words) >= 5 else 2
    for i, r in enumerate(recipes):
        lines = base_lines if i % 2 == 0 else min(base_lines + 1, len(words), 4)
        out.append(
            r.model_copy(
                update={
                    "max_lines": max(r.max_lines, lines),
                    "kashida_count": 0,
                    "swash": "none" if r.swash == "double_flourish" else r.swash,
                    "stroke_delta_mm": round(r.stroke_delta_mm + 0.15, 3),
                }
            )
        )
    return out


def _candidate_id(design_id: str, recipe: RecipeParams, source_sha: str) -> str:
    payload = f"{design_id}|{recipe.model_dump_json()}|{source_sha}|{GENERATOR_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_geometry_for_recipe(source_text: str, recipe: RecipeParams, rules: WorkshopRules):
    """Shared deterministic build path (generator + designer edits).
    Applies the Glyph Variant Library (OT feature set, kashida with source
    index remapping) and multi-line composition. Returns (runs, proof, built).
    """
    from ..fonts.glyph_variants import resolve_features

    features = None
    if recipe.ot_feature_set != "default":
        try:
            features = resolve_features(recipe.ot_feature_set, recipe.font_id)
        except (KeyError, ValueError):
            features = None  # inapplicable to this font → standard forms

    line_runs = None
    if recipe.max_lines > 1 and " " in source_text.strip():
        line_runs, proof = shape_multiline(
            source_text, recipe.font_id, recipe.max_lines, features
        )
        runs = [r for line in line_runs for r in line]
    else:
        display, imap = apply_kashida(source_text, recipe.kashida_count)
        runs = shape_text(display, recipe.font_id, features)
        if recipe.kashida_count > 0:
            runs = remap_runs_to_source(runs, imap, source_text)
        proof = verify_identity(source_text, runs)

    built = compose(
        runs,
        recipe,
        loop_inner_d=rules.loop_inner_diameter_mm,
        loop_wall=rules.loop_wall_mm,
        bridge_width=rules.min_bridge_mm,
        min_gap_eff=rules.effective_min_gap_mm,
        line_runs=line_runs,
        fit_width_mm=rules.max_width_mm - 4.0,
    )
    return runs, proof, built


def build_candidate(
    design_id: str,
    source: ImmutableSourceText,
    recipe: RecipeParams,
    rules: WorkshopRules,
) -> DesignCandidate:
    registry = get_registry()
    font = registry.get(recipe.font_id)
    runs, proof, built = build_geometry_for_recipe(source.normalized_text, recipe, rules)
    expected_loops = {"none": 0, "top": 1, "left_right": 2}[recipe.loops]
    report = validate(
        built,
        rules,
        proof,
        font_production_allowed=font.commercial_production_allowed,
        expected_loops=expected_loops,
    )

    geom = built.geometry
    features = None
    if not geom.is_empty:
        from .similarity import grid_to_hex, occupancy_grid
        w, h = built.width_mm, built.height_mm
        bbox_area = w * h if w and h else 1.0
        perimeter = geom.length
        area = geom.area
        features = CandidateFeatures(
            width_mm=round(w, 3),
            height_mm=round(h, 3),
            aspect_ratio=round(w / h, 4) if h else 0,
            fill_ratio=round(area / bbox_area, 4),
            hole_count=report.hole_count,
            complexity=round(perimeter**2 / area, 2) if area else 0,
            stroke_delta_mm=recipe.stroke_delta_mm,
            composition_class=COMPOSITION_CLASSES[recipe.composition],
            font_index=sorted(f.font_id for f in registry.list()).index(recipe.font_id),
            loops_class=LOOPS_CLASSES[recipe.loops],
            occupancy_hex=grid_to_hex(occupancy_grid(geom)),
        )

    # Scored later in generate_candidates() via the configurable ranking
    # engine (needs the whole pool for the originality dimension).
    return DesignCandidate(
        candidate_id=_candidate_id(design_id, recipe, source.sha256),
        design_id=design_id,
        source_text_sha256=source.sha256,
        recipe=recipe,
        shaped_runs=runs,
        identity_proof=proof,
        validation=report,
        features=features,
        score=0.0,
        geometry_wkt=geom.wkt if not geom.is_empty else "",
        text_geometry_wkt=(
            built.text_geometry.wkt
            if built.text_geometry is not None and not built.text_geometry.is_empty
            else ""
        ),
    )


DOT_CLASSES = {"round": 0, "diamond": 1, "square": 2, "petal": 3}
SWASH_CLASSES = {"none": 0, "underline_flourish": 1, "tail_sweep": 2, "double_flourish": 3}


def _feature_vector(c: DesignCandidate) -> list[float]:
    f = c.features
    r = c.recipe
    return [
        f.aspect_ratio,
        f.fill_ratio,
        f.hole_count,
        f.complexity,
        f.stroke_delta_mm,
        f.composition_class,
        f.font_index,
        f.loops_class,
        DOT_CLASSES.get(r.dot_style, 0),
        SWASH_CLASSES.get(r.swash, 0),
        float(r.kashida_count),
        float(r.max_lines),
    ]


def _normalize_matrix(rows: list[list[float]]) -> list[list[float]]:
    cols = list(zip(*rows))
    normed_cols = []
    for col in cols:
        lo, hi = min(col), max(col)
        span = hi - lo
        normed_cols.append([(v - lo) / span if span else 0.0 for v in col])
    return [list(r) for r in zip(*normed_cols)]


def _dist(a: list[float], b: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def select_diverse(candidates: list[DesignCandidate], n: int = 10) -> list[DesignCandidate]:
    """Greedy max-min diversity selection over valid candidates, with a
    perceptual near-duplicate gate: no two selections may exceed the
    occupancy-grid IoU threshold (visual comparison aid, never truth)."""
    from .similarity import NEAR_DUP_IOU, hex_to_grid, iou

    valid = [c for c in candidates if c.validation and c.validation.passed and c.features]
    if not valid:
        return []
    vectors = _normalize_matrix([_feature_vector(c) for c in valid])
    grids = [hex_to_grid(c.features.occupancy_hex) if c.features.occupancy_hex else None for c in valid]

    def near_dup(i: int, chosen: list[int]) -> bool:
        if grids[i] is None:
            return False
        return any(
            grids[j] is not None and iou(grids[i], grids[j]) >= NEAR_DUP_IOU for j in chosen
        )

    by_score = sorted(range(len(valid)), key=lambda i: (-valid[i].score, valid[i].candidate_id))
    selected = [by_score[0]]
    # First pass: enforce the perceptual gate strictly.
    while len(selected) < min(n, len(valid)):
        best_i, best_d = None, -1.0
        for i in range(len(valid)):
            if i in selected or near_dup(i, selected):
                continue
            d = min(_dist(vectors[i], vectors[j]) for j in selected)
            if d > best_d or (d == best_d and valid[i].candidate_id < valid[best_i].candidate_id):
                best_i, best_d = i, d
        if best_i is None:
            break  # pool exhausted under the gate — return fewer, honestly
        selected.append(best_i)
    result = []
    for rank, i in enumerate(selected):
        c = valid[i]
        c.diversity_rank = rank + 1
        result.append(c)
    return result


def diversity_score(selected: list[DesignCandidate]) -> float:
    """Minimum pairwise normalized feature distance among the selection."""
    if len(selected) < 2:
        return 0.0
    vectors = _normalize_matrix([_feature_vector(c) for c in selected])
    dmin = float("inf")
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            dmin = min(dmin, _dist(vectors[i], vectors[j]))
    return round(dmin, 4)


def generate_candidates(
    design_id: str,
    source: ImmutableSourceText,
    rules: WorkshopRules,
    min_internal: int = 30,
    top_n: int = 10,
    hints: dict | None = None,
) -> tuple[list[DesignCandidate], list[DesignCandidate]]:
    """Returns (all_internal_candidates, diverse_top_n). `hints` come from
    deterministic reference intake; they add a transparent score bonus so
    reference-matching styles seed the diverse selection first — they never
    bypass validation or the schema."""
    recipes = _adapt_for_text_length(expand_recipes(min_internal), source.normalized_text)
    all_candidates = [build_candidate(design_id, source, r, rules) for r in recipes]
    _apply_ranking(all_candidates)
    if hints:
        _apply_hint_bonus(all_candidates, hints)
    top = select_diverse(all_candidates, top_n)
    _attach_quality_reports(top)
    return all_candidates, top


def _attach_quality_reports(top: list[DesignCandidate]) -> None:
    from .quality import evaluate
    from .similarity import hex_to_grid, iou

    grids = {
        c.candidate_id: hex_to_grid(c.features.occupancy_hex)
        for c in top
        if c.features and c.features.occupancy_hex
    }
    for c in top:
        pool_max_iou = 0.0
        g = grids.get(c.candidate_id)
        if g is not None:
            others = [v for k, v in grids.items() if k != c.candidate_id]
            if others:
                pool_max_iou = max(iou(g, o) for o in others)
        c.quality_report = evaluate(
            c.geometry_wkt,
            c.text_geometry_wkt or None,
            identity_verified=c.identity_proof.verified,
            validation_passed=bool(c.validation and c.validation.passed),
            occupancy_hex=c.features.occupancy_hex if c.features else None,
            pool_min_iou=pool_max_iou,
        )


def _apply_hint_bonus(candidates: list[DesignCandidate], hints: dict) -> None:
    preferred_comp = set(hints.get("preferred_compositions", []))
    preferred_recipes = set(hints.get("preferred_recipes", []))
    for c in candidates:
        bonus = 0.0
        if c.recipe.composition in preferred_comp:
            bonus += 4.0
        if any(c.recipe.recipe_id.startswith(r) for r in preferred_recipes):
            bonus += 4.0
        if bonus and c.score_breakdown is not None:
            c.score = round(c.score + bonus, 4)
            c.score_breakdown["intake_hint_bonus"] = bonus


def _apply_ranking(candidates: list[DesignCandidate]) -> None:
    """Score the pool with the configurable ranking engine (spec weights).
    Originality uses distance from the pool mean in normalized feature space."""
    from .ranking import DEFAULT_RANKING, score_candidate

    with_features = [c for c in candidates if c.features]
    vectors = _normalize_matrix([_feature_vector(c) for c in with_features]) if with_features else []
    mean = (
        [sum(col) / len(col) for col in zip(*vectors)] if vectors else None
    )
    vec_by_id = {c.candidate_id: v for c, v in zip(with_features, vectors)}
    for c in candidates:
        score, breakdown = score_candidate(
            identity_verified=c.identity_proof.verified,
            validation_passed=bool(c.validation and c.validation.passed),
            features=c.features,
            stroke_slack_ratio=c.recipe.stroke_delta_mm / 0.3,
            pool_mean_vector=mean,
            feature_vector=vec_by_id.get(c.candidate_id),
        )
        c.score = score
        c.score_breakdown = breakdown
        c.ranking_config_version = DEFAULT_RANKING.version
