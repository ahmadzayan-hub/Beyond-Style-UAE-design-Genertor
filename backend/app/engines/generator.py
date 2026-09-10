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
    "engraved_band": 8,
    "multi_name": 9,
}
LOOPS_CLASSES = {"none": 0, "top": 1, "left_right": 2, "upper_left_right": 3}
EXPECTED_LOOPS = {"none": 0, "top": 1, "left_right": 2, "upper_left_right": 2}


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
    """Deterministic identity. `font_axes` is omitted from the payload when
    empty so that adding the field did not renumber every pre-axis design;
    once coordinates ARE set they are part of identity, so a different
    weight is a different candidate rather than a silent restyle."""
    exclude = set()
    if not recipe.font_axes:
        exclude.add("font_axes")
    if recipe.ring is None:
        # Same invariant as font_axes: a None ring must serialize exactly
        # like the pre-ring schema so no existing candidate is renumbered.
        exclude.add("ring")
    if recipe.multi_name is None:
        exclude.add("multi_name")
    dumped = recipe.model_dump_json(exclude=exclude) if exclude else recipe.model_dump_json()
    payload = f"{design_id}|{dumped}|{source_sha}|{GENERATOR_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _width_allowance_mm(recipe: RecipeParams, rules: WorkshopRules) -> float:
    """Width the composition adds beyond the fitted text: chain rings at
    both ends, bar overhangs, hairline lift. Keeps stacked designs inside
    the product envelope after construction."""
    allowance = 2.0  # hairline lift + closing on both sides
    ch = recipe.connector_height_mm
    if recipe.composition in ("baseline_bar", "underline_bar", "top_bar"):
        allowance += 2 * ch * 1.5
    if recipe.composition in ("frame_circle", "frame_rect", "plate_rect", "plate_oval"):
        allowance += 2 * (recipe.frame_margin_mm + max(ch, 1.1))
    if recipe.loops == "left_right":
        r_out = rules.loop_inner_diameter_mm / 2 + rules.loop_wall_mm
        allowance += 2 * (2 * r_out - rules.loop_wall_mm * 0.85)
    return allowance


def build_geometry_for_recipe(source_text: str, recipe: RecipeParams, rules: WorkshopRules):
    """Shared deterministic build path (generator + designer edits).
    Applies the Glyph Variant Library (OT feature set, kashida with source
    index remapping) and multi-line composition. Returns (runs, proof, built).
    """
    from ..fonts.glyph_variants import resolve_features
    from ..fonts.instances import validate_axes

    # Single choke point: generation and designer edits both come through
    # here, so an unsupported or out-of-range coordinate is refused with a
    # structured error rather than crashing inside the font library.
    if recipe.font_axes:
        validate_axes(recipe.font_id, recipe.font_axes)

    if recipe.ring is not None:
        # Engraved-band mode: same choke point (generation AND designer
        # edits), different construction — CUT band + ENGRAVE layer.
        from .ring_band import build_ring_geometry

        return build_ring_geometry(source_text, recipe, rules)

    if recipe.multi_name is not None:
        # Vector Composition Engine: every name shaped once, variants are
        # rigid transforms + welds + safe bridges of the same vectors.
        from .composition_engine import compose_multi_name

        spec = recipe.multi_name
        runs, proof, built, _meta = compose_multi_name(
            source_text, recipe, rules, layout=spec["layout"], variant=int(spec.get("variant", 0)),
            envelope_mm=tuple(spec.get("envelope_mm", (60.0, 40.0))),
            attachments=recipe.loops if recipe.loops == "upper_left_right" else "none",
        )
        return runs, proof, built

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
        fit_width_mm=rules.max_width_mm - _width_allowance_mm(recipe, rules),
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
    expected_loops = EXPECTED_LOOPS[recipe.loops]
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
            font_index=registry.get(recipe.font_id).diversity_index,
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
        inner_text_geometry_wkt=(
            built.inner_text_geometry.wkt
            if built.inner_text_geometry is not None and not built.inner_text_geometry.is_empty
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


def _build_workers() -> int:
    """Composition builds are CPU-bound and independent per recipe. Use a
    small fork pool (BS_BUILD_WORKERS, default min(4, cpus)); 1 = inline."""
    import os

    raw = os.environ.get("BS_BUILD_WORKERS")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            return 1
    return max(1, min(4, os.cpu_count() or 1))


def _build_one(args):
    design_id, source, recipe, rules = args
    return build_candidate(design_id, source, recipe, rules)


def _build_many(design_id: str, source: ImmutableSourceText, recipes, rules: WorkshopRules) -> list[DesignCandidate]:
    """Deterministic, order-preserving parallel build. Falls back to the
    inline loop when a pool cannot be created (restricted sandboxes) so the
    result never depends on the executor."""
    workers = _build_workers()
    if workers <= 1 or len(recipes) < 4:
        return [build_candidate(design_id, source, r, rules) for r in recipes]
    try:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor

        ctx = mp.get_context("fork")
        with ProcessPoolExecutor(max_workers=min(workers, len(recipes)), mp_context=ctx) as pool:
            return list(pool.map(_build_one, [(design_id, source, r, rules) for r in recipes]))
    except Exception:  # noqa: BLE001 — any executor failure → identical inline result
        return [build_candidate(design_id, source, r, rules) for r in recipes]


def generate_candidates(
    design_id: str,
    source: ImmutableSourceText,
    rules: WorkshopRules,
    min_internal: int = 30,
    top_n: int = 10,
    hints: dict | None = None,
    trace: dict | None = None,
) -> tuple[list[DesignCandidate], list[DesignCandidate]]:
    """Returns (all_internal_candidates, diverse_top_n). `hints` come from
    deterministic reference intake; they add a transparent score bonus so
    reference-matching styles seed the diverse selection first — they never
    bypass validation or the schema. With hints, the structured archetype
    catalogue is queried by Design-DNA similarity and the top matches join
    the pool (additive: the hint-less pool — and every golden fixture built
    on it — is unchanged). `trace`, when given, receives the retrieval
    provenance for the audit event."""
    from .composition_engine import is_multi_name, multi_name_recipes

    if is_multi_name(source.normalized_text, hints):
        # Name lists go to the Vector Composition Engine (6–12 variants per
        # face from the same validated glyph vectors). Only when it cannot
        # supply `top_n` valid pieces is the pool topped up with the ordinary
        # stacked recipes, so the customer still sees ten valid options.
        recipes = multi_name_recipes(hints)
        all_candidates = _build_many(design_id, source, recipes, rules)
        valid_n = sum(1 for c in all_candidates if c.validation and c.validation.passed)
        if valid_n < top_n:
            stacked = _build_many(design_id, source, expand_recipes(min_internal), rules)
            all_candidates = all_candidates + stacked
            if trace is not None:
                trace["composition_topup"] = {"composition_valid": valid_n, "stacked_added": len(stacked)}
        from .ranking import DEFAULT_RANKING

        _apply_ranking(all_candidates, DEFAULT_RANKING)
        if hints:
            _apply_hint_bonus(all_candidates, hints)
        top = select_diverse(all_candidates, top_n)
        _attach_quality_reports(top)
        if trace is not None:
            trace["composition_engine"] = {"layouts": sorted({r.multi_name["layout"] for r in recipes}),
                                           "fonts": sorted({r.font_id for r in recipes}), "variants": len(recipes)}
        return all_candidates, top

    recipes = expand_recipes(min_internal)
    if hints:
        from .archetype_library import retrieve_archetypes

        extra, provenance = retrieve_archetypes(
            hints,
            product_type=hints.get("product_type"),
            text_length=len(source.normalized_text),
            exclude_ids={r.recipe_id for r in recipes},
        )
        recipes = recipes + extra
        if trace is not None:
            trace["retrieval"] = provenance
        recipes = recipes + _script_recipes(hints, {r.recipe_id for r in recipes}, base_recipes=recipes)
    recipes = _adapt_for_text_length(recipes, source.normalized_text)
    all_candidates = [build_candidate(design_id, source, r, rules) for r in recipes]
    from .ranking import DEFAULT_RANKING, REFERENCE_RANKING

    ranking_config = (
        REFERENCE_RANKING if hints and hints.get("source") == "reference_dna" else DEFAULT_RANKING
    )
    _apply_ranking(all_candidates, ranking_config)
    if hints:
        _apply_hint_bonus(all_candidates, hints)
    top = _select_with_script_priority(all_candidates, top_n, hints, trace)
    _attach_quality_reports(top)
    return all_candidates, top


# Slots of the shown ten reserved for the customer's chosen script when a
# TRUE (rights-cleared) source exists; the rest keeps contrast alternatives.
SCRIPT_PRIORITY_SLOTS = 8


def _true_script_fonts(hints: dict | None) -> list[str]:
    family = (hints or {}).get("script_family")
    if not family:
        return []
    from ..fonts.capabilities import resolve_script_request

    res = resolve_script_request(family)
    if res.get("outcome") != "AVAILABLE":
        return []
    return list(res.get("fonts") or ([res["font_id"]] if res.get("font_id") else []))


def _select_with_script_priority(candidates: list[DesignCandidate], top_n: int, hints: dict | None,
                                 trace: dict | None = None) -> list[DesignCandidate]:
    """When the customer chose a calligraphy style that we hold as a TRUE
    source, the shown set is drawn first from that script (diverse, valid),
    then topped up with the best contrasting alternatives. Without a true
    source (inspired-only styles) the ordinary diverse selection applies —
    nothing is dressed up as the classical script."""
    fonts = _true_script_fonts(hints)
    if not fonts:
        return select_diverse(candidates, top_n)
    primary_pool = [c for c in candidates if c.recipe.font_id in fonts]
    primary = select_diverse(primary_pool, min(top_n, SCRIPT_PRIORITY_SLOTS))
    chosen = {c.candidate_id for c in primary}
    rest = select_diverse([c for c in candidates if c.candidate_id not in chosen], top_n - len(primary))
    merged = primary + rest
    for rank, c in enumerate(merged):
        c.diversity_rank = rank + 1
    if trace is not None:
        trace["script_priority"] = {"fonts": fonts, "reserved": len(primary), "filled": len(rest)}
    return merged


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


def _script_recipes(hints: dict, existing: set[str], base_recipes: list[RecipeParams] | None = None) -> list[RecipeParams]:
    """Curated script recipes for a customer-chosen script family. Kept out
    of the default pool on purpose (the golden fixtures pin it); added only
    when the customer asked for that script.

    When the family has a TRUE source, the whole archetype spread (plates,
    bars, frames, medallions, variants) is additionally cloned onto that
    font, so the customer's calligraphy gets the same compositional breadth
    as the default pool instead of two sweep recipes. Font-specific axes and
    feature sets are dropped on the clone (validated per font)."""
    family = hints.get("script_family")
    if not family:
        return []
    from ..fonts.capabilities import recipes_for_script

    out = [RecipeParams(**r) for r in recipes_for_script(family) if r["recipe_id"] not in existing]
    seen = existing | {r.recipe_id for r in out}
    for font_id in _true_script_fonts(hints):
        for base in base_recipes or []:
            if base.ring is not None or base.multi_name is not None or base.font_id == font_id:
                continue
            rid = f"{base.recipe_id}@{font_id}"
            if rid in seen:
                continue
            seen.add(rid)
            out.append(base.model_copy(update={
                "recipe_id": rid, "font_id": font_id, "name": f"{base.name} · {font_id}",
                "font_axes": {}, "ot_feature_set": "default",
            }))
    return out


def _apply_hint_bonus(candidates: list[DesignCandidate], hints: dict) -> None:
    """Reference-intent match, applied as a transparent scaled bonus.
    style_strength (bonus_scale 0.5–1.5) maps "more original" ↔ "similar
    inspiration". Never bypasses validation or the near-duplicate gate."""
    preferred_comp = set(hints.get("preferred_compositions", []))
    preferred_recipes = set(hints.get("preferred_recipes", []))
    scale = float(hints.get("bonus_scale", 1.0))
    for c in candidates:
        bonus = 0.0
        if c.recipe.composition in preferred_comp:
            bonus += 4.0
        if any(c.recipe.recipe_id.startswith(r) for r in preferred_recipes):
            bonus += 4.0
        if hints.get("prefer_kashida") and c.recipe.kashida_count > 0:
            bonus += 3.0
        if hints.get("prefer_swash") and c.recipe.swash != "none":
            bonus += 3.0
        if c.recipe.font_id in (hints.get("preferred_fonts") or ()):
            bonus += 4.0  # customer-chosen script family
        bonus = round(bonus * scale, 4)
        if bonus and c.score_breakdown is not None:
            c.score = round(c.score + bonus, 4)
            c.score_breakdown["intake_hint_bonus"] = bonus
            c.score_breakdown["reference_intent_match"] = True


def _apply_ranking(candidates: list[DesignCandidate], ranking_config=None) -> None:
    """Score the pool with the configurable ranking engine (spec weights).
    Originality uses distance from the pool mean in normalized feature space."""
    from .ranking import DEFAULT_RANKING, score_candidate

    ranking_config = ranking_config or DEFAULT_RANKING

    with_features = [c for c in candidates if c.features]
    vectors = _normalize_matrix([_feature_vector(c) for c in with_features]) if with_features else []
    mean = (
        [sum(col) / len(col) for col in zip(*vectors)] if vectors else None
    )
    vec_by_id = {c.candidate_id: v for c, v in zip(with_features, vectors)}
    from shapely import wkt as _wkt

    from .geometry_engine import mean_stroke_mm

    for c in candidates:
        stroke_ratio = None
        if c.text_geometry_wkt and c.recipe.target_height_mm:
            stroke_ratio = mean_stroke_mm(_wkt.loads(c.text_geometry_wkt)) / c.recipe.target_height_mm
        score, breakdown = score_candidate(
            identity_verified=c.identity_proof.verified,
            validation_passed=bool(c.validation and c.validation.passed),
            features=c.features,
            stroke_slack_ratio=c.recipe.stroke_delta_mm / 0.3,
            pool_mean_vector=mean,
            feature_vector=vec_by_id.get(c.candidate_id),
            config=ranking_config,
            stroke_ratio=stroke_ratio,
        )
        c.score = score
        c.score_breakdown = breakdown
        c.ranking_config_version = ranking_config.version
