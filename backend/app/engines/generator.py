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
from .arabic_engine import shape_text, verify_identity
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
}
LOOPS_CLASSES = {"none": 0, "top": 1, "left_right": 2}


def load_recipe_library() -> dict:
    return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))


def expand_recipes(min_count: int = 30) -> list[RecipeParams]:
    """Deterministically expand base recipes along variation axes until at
    least `min_count` structured parameter sets exist."""
    lib = load_recipe_library()
    bases = [RecipeParams(**r) for r in lib["recipes"]]
    axes = lib["variation_axes"]
    variants: list[RecipeParams] = []
    for base in bases:
        for i, ds in enumerate(axes["stroke_delta_mm"]):
            for j, sp in enumerate(axes["letter_spacing_mm"]):
                v = base.model_copy(
                    update={
                        "recipe_id": f"{base.recipe_id}.v{i}{j}",
                        "stroke_delta_mm": round(base.stroke_delta_mm + ds, 3),
                        "letter_spacing_mm": round(base.letter_spacing_mm + sp, 3),
                    }
                )
                variants.append(v)
                if len(variants) >= min_count * 2:
                    return variants
    k = 0
    while len(variants) < min_count:
        base = bases[k % len(bases)]
        ys = axes["y_scale"][(k // len(bases)) % len(axes["y_scale"])]
        variants.append(
            base.model_copy(
                update={"recipe_id": f"{base.recipe_id}.y{k}", "y_scale": base.y_scale * ys}
            )
        )
        k += 1
    return variants


def _candidate_id(design_id: str, recipe: RecipeParams, source_sha: str) -> str:
    payload = f"{design_id}|{recipe.model_dump_json()}|{source_sha}|{GENERATOR_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_candidate(
    design_id: str,
    source: ImmutableSourceText,
    recipe: RecipeParams,
    rules: WorkshopRules,
) -> DesignCandidate:
    registry = get_registry()
    font = registry.get(recipe.font_id)
    runs = shape_text(source.normalized_text, recipe.font_id)
    proof = verify_identity(source.normalized_text, runs)
    built = compose(
        runs,
        recipe,
        loop_inner_d=rules.loop_inner_diameter_mm,
        loop_wall=rules.loop_wall_mm,
        bridge_width=rules.min_bridge_mm,
        min_gap_eff=rules.effective_min_gap_mm,
    )
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
    )


def _feature_vector(c: DesignCandidate) -> list[float]:
    f = c.features
    return [
        f.aspect_ratio,
        f.fill_ratio,
        f.hole_count,
        f.complexity,
        f.stroke_delta_mm,
        f.composition_class,
        f.font_index,
        f.loops_class,
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
    """Greedy max-min diversity selection over valid candidates."""
    valid = [c for c in candidates if c.validation and c.validation.passed and c.features]
    if not valid:
        return []
    vectors = _normalize_matrix([_feature_vector(c) for c in valid])
    by_score = sorted(range(len(valid)), key=lambda i: (-valid[i].score, valid[i].candidate_id))
    selected = [by_score[0]]
    while len(selected) < min(n, len(valid)):
        best_i, best_d = None, -1.0
        for i in range(len(valid)):
            if i in selected:
                continue
            d = min(_dist(vectors[i], vectors[j]) for j in selected)
            # deterministic tie-break by candidate id
            if d > best_d or (d == best_d and valid[i].candidate_id < valid[best_i].candidate_id):
                best_i, best_d = i, d
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
) -> tuple[list[DesignCandidate], list[DesignCandidate]]:
    """Returns (all_internal_candidates, diverse_top_n)."""
    recipes = expand_recipes(min_internal)
    all_candidates = [build_candidate(design_id, source, r, rules) for r in recipes]
    _apply_ranking(all_candidates)
    top = select_diverse(all_candidates, top_n)
    return all_candidates, top


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
