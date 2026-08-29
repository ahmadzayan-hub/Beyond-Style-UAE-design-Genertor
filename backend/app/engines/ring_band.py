"""Engraved ring band — flat-pattern (unrolled) construction.

A ring band is manufactured from a flat strip: CUT = the band rectangle
(developed length × band height), ENGRAVE = the text vector placed inside
it. This is a different manufacturing mode from the cut-out silhouette
products: engraved strokes are marks on solid metal, so dots may float
freely (no bridges) and counters never fall out — the constraints that
matter are engraving stroke width, edge margins, and fit.

Flat-pattern maths: EU ring size = inner circumference in mm. The strip is
cut at the NEUTRAL AXIS length so the engraved face reads true after
rolling: L = size_eu + π · thickness.

Deterministic throughout — the same recipe always yields byte-identical
geometry. The customer's text is never altered to make it fit; when the
band cannot carry it legibly the candidate is BLOCKED, not shrunk into
illegibility.
"""
from __future__ import annotations

import math

from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon, box

from ..config import WorkshopRules
from ..schemas.jewellery_design import (
    RecipeParams,
    ValidationSeverity,
    Violation,
    ViolationCode,
)
from .geometry_engine import BuiltGeometry

RING_SIZE_EU_MIN = 44
RING_SIZE_EU_MAX = 70
DEFAULT_SIZE_EU = 52
DEFAULT_BAND_HEIGHT_MM = 7.5
DEFAULT_THICKNESS_MM = 1.5
BAND_HEIGHT_MIN_MM = 5.0
BAND_HEIGHT_MAX_MM = 10.0
#: Engraved strokes below this width fill in during casting/engraving.
ENGRAVE_MIN_STROKE_MM = 0.30
#: Clear metal between engraving and the band edge.
EDGE_MARGIN_MM = 0.8
#: The build refuses to shrink text below this fraction of the requested
#: height — smaller would be illegible, and text is never altered to fit.
MIN_LEGIBLE_SCALE = 0.6

BORDERS = ("none", "double_line", "ornament_diamond")
RULES_PROFILE = "RING_ENGRAVING_V1"


def band_length_mm(size_eu: float, thickness_mm: float = DEFAULT_THICKNESS_MM) -> float:
    """Developed (flat-pattern) strip length at the neutral axis."""
    return round(size_eu + math.pi * thickness_mm, 3)


def _border_geometry(length: float, height: float, style: str) -> list[Polygon]:
    """Deterministic parametric border ornaments inside the band edges.
    Engraved marks — part of the ENGRAVE layer, never the CUT outline."""
    if style == "none":
        return []
    line_w = 0.35
    inset = EDGE_MARGIN_MM
    parts: list[Polygon] = [
        box(inset, inset, length - inset, inset + line_w),
        box(inset, height - inset - line_w, length - inset, height - inset),
    ]
    if style == "ornament_diamond":
        # A row of small diamonds along each rail, evenly spaced.
        step = 4.0
        size = 0.9
        n = int((length - 2 * (inset + 2)) // step)
        for rail_y in (inset + line_w + 0.9, height - inset - line_w - 0.9):
            for i in range(n):
                cx = inset + 2 + step / 2 + i * step
                parts.append(
                    Polygon(
                        [
                            (cx, rail_y - size / 2),
                            (cx + size / 2, rail_y),
                            (cx, rail_y + size / 2),
                            (cx - size / 2, rail_y),
                        ]
                    )
                )
    return parts


def build_ring_geometry(
    source_text: str, recipe: RecipeParams, rules: WorkshopRules
):
    """Ring branch of the shared build choke point. Returns (runs, proof,
    BuiltGeometry) exactly like the silhouette branch, with:
    geometry = the CUT band rectangle, text_geometry = the ENGRAVE layer.
    """
    from ..fonts.glyph_variants import resolve_features
    from .arabic_engine import shape_text, verify_identity
    from .geometry_engine import compose

    ring = dict(recipe.ring or {})
    size_eu = float(ring.get("size_eu", DEFAULT_SIZE_EU))
    height = float(ring.get("band_height_mm", DEFAULT_BAND_HEIGHT_MM))
    thickness = float(ring.get("thickness_mm", DEFAULT_THICKNESS_MM))
    border = ring.get("border", "none")
    length = band_length_mm(size_eu, thickness)

    features = None
    if recipe.ot_feature_set != "default":
        try:
            features = resolve_features(recipe.ot_feature_set, recipe.font_id)
        except (KeyError, ValueError):
            features = None

    # Two engraved faces at most, expressed inside the single immutable
    # source text as OUTER\nINNER — exactly the two-name necklace pattern.
    # The text of each face is customer truth; more than two faces is
    # refused, never silently merged.
    faces = source_text.split("\n")
    if len(faces) > 2:
        raise ValueError("A ring band supports at most two engraved faces (outer\\ninner).")
    outer_text = faces[0]
    inner_text = faces[1] if len(faces) == 2 and faces[1].strip() else None

    # Text height budget: inside the margins, minus border rails when present.
    border_allowance = 1.6 if border != "none" else 0.0
    text_h = height - 2 * EDGE_MARGIN_MM - 2 * border_allowance
    field_len = length - 2 * (EDGE_MARGIN_MM + 1.2)

    def _build_face(face_text: str, face_h: float):
        """Shape → outline → fit (downscale only, never alter text) →
        center on the band. Returns (runs, per-line proof, geometry, issues)."""
        runs = shape_text(face_text, recipe.font_id, features)
        line_proof = verify_identity(face_text, runs)
        # Engraved marks stand alone: keep dots, no loops, no plates. The
        # composed geometry is an ENGRAVE layer, not a cut-out silhouette.
        text_recipe = recipe.model_copy(
            update={
                "composition": "bare",
                "loops": "none",
                "dot_strategy": "keep",
                "target_height_mm": face_h,
                "max_lines": 1,
            }
        )
        built_text = compose(
            runs,
            text_recipe,
            loop_inner_d=rules.loop_inner_diameter_mm,
            loop_wall=rules.loop_wall_mm,
            bridge_width=rules.min_bridge_mm,
            min_gap_eff=rules.effective_min_gap_mm,
            line_runs=None,
            fit_width_mm=field_len,
        )
        geom = built_text.geometry
        face_issues = list(built_text.outline_issues)
        tminx, tminy, tmaxx, tmaxy = geom.bounds
        tw = tmaxx - tminx
        if tw > field_len and tw > 0:
            scale = field_len / tw
            if scale < MIN_LEGIBLE_SCALE:
                face_issues.append("ENGRAVING_TEXT_OVERFLOW")
                scale = MIN_LEGIBLE_SCALE
            geom = affinity.scale(geom, xfact=scale, yfact=scale, origin=(tminx, tminy))
            tminx, tminy, tmaxx, tmaxy = geom.bounds
            tw = tmaxx - tminx
        th = tmaxy - tminy
        geom = affinity.translate(
            geom,
            xoff=(length - tw) / 2 - tminx,
            yoff=(height - th) / 2 - tminy,
        )
        return runs, line_proof, geom, face_issues

    runs, outer_proof, outer_geom, issues = _build_face(outer_text, text_h)

    inner_engrave = None
    inner_proof = None
    if inner_text is not None:
        inner_runs, inner_proof, inner_geom, inner_issues = _build_face(
            inner_text, height - 2 * EDGE_MARGIN_MM  # inner face has no border rails
        )
        issues.extend(inner_issues)
        runs = runs + inner_runs
        # The back face is engraved with the strip flipped, so the flat
        # pattern is MIRRORED about the strip's vertical centerline — the
        # text then reads correctly from inside the rolled ring.
        inner_geom = affinity.scale(inner_geom, xfact=-1, yfact=1, origin=(length / 2, 0))
        inner_engrave = MultiPolygon(
            [p for p in getattr(inner_geom, "geoms", [inner_geom])
             if not p.is_empty and p.geom_type == "Polygon"]
        )

    # Merge identity over the FULL source text; the "\n" separator is
    # layout, covered by the face split itself (same convention as
    # shape_multiline's consumed separators).
    if inner_proof is None:
        proof = outer_proof
    else:
        covered = set(outer_proof.covered_codepoint_indices)
        covered.add(len(outer_text))  # the \n
        covered.update(len(outer_text) + 1 + i for i in inner_proof.covered_codepoint_indices)
        notdef = outer_proof.notdef_glyph_count + inner_proof.notdef_glyph_count
        uncovered = [i for i in range(len(source_text)) if i not in covered]
        verified = not uncovered and notdef == 0 and len(source_text) > 0
        from ..schemas.jewellery_design import TextIdentityProof

        proof = TextIdentityProof(
            verified=verified,
            covered_codepoint_indices=sorted(covered),
            uncovered_codepoint_indices=uncovered,
            notdef_glyph_count=notdef,
            detail="ok" if verified else f"uncovered={uncovered[:20]} notdef={notdef}",
        )

    engrave_parts = [g for g in getattr(outer_geom, "geoms", [outer_geom])]
    engrave_parts.extend(_border_geometry(length, height, border))
    engrave = MultiPolygon(
        [p for p in engrave_parts if not p.is_empty and p.geom_type == "Polygon"]
    )

    band = MultiPolygon([box(0.0, 0.0, length, height)])
    return runs, proof, BuiltGeometry(
        geometry=band,
        text_geometry=engrave,
        inner_text_geometry=inner_engrave,
        outline_issues=issues,
        bridges_added=0,
        loop_centers_mm=[],
    )


def ring_violations(candidate, rules: WorkshopRules) -> list[Violation]:
    """Engraving-mode checks on a built ring candidate (real mm, measured
    from the actual engrave geometry — never estimated)."""
    from shapely import wkt as shapely_wkt

    from .geometry_metrics import min_material_width_mm

    ring = dict(candidate.recipe.ring or {})
    size_eu = float(ring.get("size_eu", DEFAULT_SIZE_EU))
    height = float(ring.get("band_height_mm", DEFAULT_BAND_HEIGHT_MM))
    out: list[Violation] = []

    if not (RING_SIZE_EU_MIN <= size_eu <= RING_SIZE_EU_MAX):
        out.append(Violation(
            code=ViolationCode.RING_SIZE_OUT_OF_RANGE,
            severity=ValidationSeverity.ERROR,
            detail=f"EU size {size_eu:g} outside catalogue {RING_SIZE_EU_MIN}–{RING_SIZE_EU_MAX}.",
        ))
    if not (BAND_HEIGHT_MIN_MM <= height <= BAND_HEIGHT_MAX_MM):
        out.append(Violation(
            code=ViolationCode.RING_SIZE_OUT_OF_RANGE,
            severity=ValidationSeverity.ERROR,
            detail=f"Band height {height:g} mm outside {BAND_HEIGHT_MIN_MM}–{BAND_HEIGHT_MAX_MM} mm.",
        ))

    if not candidate.text_geometry_wkt:
        out.append(Violation(
            code=ViolationCode.EMPTY_GEOMETRY,
            severity=ValidationSeverity.ERROR,
            detail="Ring has no engraving geometry.",
        ))
        return out
    band = shapely_wkt.loads(candidate.geometry_wkt)
    safe_zone = band.buffer(-EDGE_MARGIN_MM + 1e-9)
    faces = [("outer", candidate.text_geometry_wkt)]
    if candidate.inner_text_geometry_wkt:
        faces.append(("inner", candidate.inner_text_geometry_wkt))
    for face, wkt_str in faces:
        engrave = shapely_wkt.loads(wkt_str)
        stroke = min_material_width_mm(engrave)
        if stroke < ENGRAVE_MIN_STROKE_MM:
            out.append(Violation(
                code=ViolationCode.ENGRAVING_STROKE_TOO_THIN,
                severity=ValidationSeverity.ERROR,
                detail=f"Narrowest {face}-face engraved stroke {stroke:.2f} mm < {ENGRAVE_MIN_STROKE_MM} mm.",
            ))
        if not engrave.within(safe_zone):
            out.append(Violation(
                code=ViolationCode.ENGRAVING_MARGIN_TOO_SMALL,
                severity=ValidationSeverity.ERROR,
                detail=f"{face.capitalize()}-face engraving closer than {EDGE_MARGIN_MM} mm to the band edge.",
            ))
    return out


def _refeature_from_engraving(candidate) -> None:
    """Every ring shares the same CUT rectangle, so diversity ranking and
    near-duplicate filtering must look at the ENGRAVE layer — the part of
    the design the customer actually compares."""
    from shapely import wkt as shapely_wkt

    from .similarity import grid_to_hex, occupancy_grid

    if not candidate.text_geometry_wkt or candidate.features is None:
        return
    engrave = shapely_wkt.loads(candidate.text_geometry_wkt)
    minx, miny, maxx, maxy = engrave.bounds
    w, h = maxx - minx, maxy - miny
    area = engrave.area
    bbox = w * h if w and h else 1.0
    perimeter = engrave.length
    candidate.features = candidate.features.model_copy(update={
        "width_mm": round(w, 3),
        "height_mm": round(h, 3),
        "aspect_ratio": round(w / h, 4) if h else 0,
        "fill_ratio": round(area / bbox, 4),
        "complexity": round(perimeter**2 / area, 2) if area else 0,
        "occupancy_hex": grid_to_hex(occupancy_grid(engrave)),
    })


def ring_recipes(source_text: str) -> list[RecipeParams]:
    """Deterministic ring recipe pool: every registered font × border style
    × band height. Fonts that cannot shape the text fail identity honestly
    downstream and are filtered like any other invalid candidate."""
    from ..fonts.registry import get_registry

    recipes = []
    for font in get_registry().list():
        for border in BORDERS:
            for h in (6.5, 7.5):
                recipes.append(RecipeParams(
                    recipe_id=f"ring-{font.font_id}-{border}-{h:g}",
                    name=f"Ring band · {font.font_id} · {border}",
                    font_id=font.font_id,
                    composition="engraved_band",
                    loops="none",
                    dot_strategy="keep",
                    target_height_mm=h,  # informational; band height governs
                    ring={"band_height_mm": h, "border": border},
                ))
    return recipes


def ring_rules(base: WorkshopRules) -> WorkshopRules:
    """A band strip is legitimately long (EU 70 → ~74.7 mm developed), so
    the width ceiling follows the largest catalogue size; every other rule
    stays as configured."""
    return base.model_copy(update={
        "product": "ring",
        "max_width_mm": band_length_mm(RING_SIZE_EU_MAX) + 2.0,
        "max_height_mm": BAND_HEIGHT_MAX_MM + 2.0,
        # Slenderness guards thin CUT-OUT pieces against bending; a band is
        # deliberately a long strip that gets rolled. Ceiling = the longest
        # catalogue strip over the narrowest band.
        "max_slenderness": band_length_mm(RING_SIZE_EU_MAX) / BAND_HEIGHT_MIN_MM + 1.0,
    })


def generate_ring_candidates(design_id, source, rules, hints=None):
    """Ring counterpart of generate_candidates: same (all, top) contract,
    same ranking and diversity engines, engraving-mode validation."""
    from .generator import _apply_ranking, build_candidate, select_diverse

    rules = ring_rules(rules)
    ring_hints = dict((hints or {}).get("ring") or {})
    size_eu = ring_hints.get("size_eu", DEFAULT_SIZE_EU)

    candidates = []
    for recipe in ring_recipes(source.normalized_text):
        merged = dict(recipe.ring)
        merged["size_eu"] = size_eu
        if "band_height_mm" in ring_hints:
            merged["band_height_mm"] = ring_hints["band_height_mm"]
        recipe = recipe.model_copy(update={"ring": merged})
        try:
            c = build_candidate(design_id, source, recipe, rules)
        except Exception:
            continue  # a font that cannot shape this text at all
        extra = ring_violations(c, rules)
        if extra:
            c.validation.violations.extend(extra)
            if any(v.severity == ValidationSeverity.ERROR for v in extra):
                c.validation.passed = False
                c.validation.production_export_allowed = False
        c.validation.rules_profile = RULES_PROFILE
        _refeature_from_engraving(c)
        candidates.append(c)

    _apply_ranking(candidates)
    valid = [c for c in candidates if c.validation and c.validation.passed]
    top = select_diverse(valid, n=10)
    return candidates, top
