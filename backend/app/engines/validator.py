"""Constraint / manufacturing validator.

Pure-geometry checks against a configurable WorkshopRules profile.
Detects: disconnected geometry / floating islands, thin strokes, weak
bridges, too-small gaps (holes), open paths (from outline extraction),
unsafe attachment loops, oversize parts, and unverified text identity.

Fixes are PROPOSED (deterministic descriptions with parameters), never
applied here.
"""
from __future__ import annotations

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import nearest_points, unary_union

from ..config import WorkshopRules
from ..schemas.jewellery_design import (
    ProposedFix,
    TextIdentityProof,
    ValidationReport,
    ValidationSeverity,
    Violation,
    ViolationCode,
)
from .geometry_engine import BuiltGeometry

QUAD_SEGS = 8


def _erosion_survivors(geom: MultiPolygon, radius: float):
    eroded = geom.buffer(-radius, quad_segs=QUAD_SEGS)
    if eroded.is_empty:
        return []
    if eroded.geom_type == "Polygon":
        return [eroded]
    return [g for g in eroded.geoms if g.geom_type == "Polygon"]


def validate(
    built: BuiltGeometry,
    rules: WorkshopRules,
    identity: TextIdentityProof,
    font_production_allowed: bool = True,
    expected_loops: int = 0,
) -> ValidationReport:
    violations: list[Violation] = []
    geom = built.geometry
    parts = list(geom.geoms) if not geom.is_empty else []

    # --- text identity gate (Arabic truth rule) ---
    if not identity.verified:
        violations.append(
            Violation(
                code=ViolationCode.TEXT_IDENTITY_UNVERIFIED,
                severity=ValidationSeverity.ERROR,
                detail=f"Character identity not proven: {identity.detail}",
            )
        )

    # --- font rights gate ---
    if not font_production_allowed:
        violations.append(
            Violation(
                code=ViolationCode.FONT_RIGHTS_BLOCK,
                severity=ValidationSeverity.ERROR,
                detail="Font rights status forbids commercial production export.",
            )
        )

    # --- structural checks ---
    if not parts:
        violations.append(
            Violation(
                code=ViolationCode.EMPTY_GEOMETRY,
                severity=ValidationSeverity.ERROR,
                detail="No geometry produced.",
            )
        )
        return _report(violations, rules, 0, 0)

    for issue in built.outline_issues:
        violations.append(
            Violation(
                code=ViolationCode.OPEN_PATH,
                severity=ValidationSeverity.ERROR,
                detail=issue,
            )
        )

    # Disconnected components / floating islands.
    if len(parts) > 1:
        main = max(parts, key=lambda p: p.area)
        for p in parts:
            if p is main:
                continue
            pa, pb = nearest_points(p, main)
            code = (
                ViolationCode.FLOATING_ISLAND
                if p.area < main.area * 0.05
                else ViolationCode.DISCONNECTED_COMPONENT
            )
            violations.append(
                Violation(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    detail=f"Component (area {p.area:.2f} mm²) not connected to main body.",
                    location_mm=(p.centroid.x, p.centroid.y),
                    proposed_fix=ProposedFix(
                        action="add_bridge",
                        detail="Connect with straight bridge along shortest path.",
                        params={
                            "from": [pa.x, pa.y],
                            "to": [pb.x, pb.y],
                            "width_mm": rules.min_bridge_mm,
                        },
                    ),
                )
            )

    # Thin strokes: parts that vanish when eroded by effective_min_stroke/2.
    half_stroke = rules.effective_min_stroke_mm / 2
    survivors = _erosion_survivors(geom, half_stroke)
    surviving_union = unary_union(survivors) if survivors else None
    for p in parts:
        if surviving_union is None or not p.intersects(surviving_union):
            violations.append(
                Violation(
                    code=ViolationCode.THIN_STROKE,
                    severity=ValidationSeverity.ERROR,
                    detail=(
                        f"Region thinner than min stroke {rules.min_stroke_mm}mm"
                        f" (+kerf {rules.kerf_mm}mm) everywhere."
                    ),
                    location_mm=(p.centroid.x, p.centroid.y),
                    proposed_fix=ProposedFix(
                        action="thicken",
                        detail="Apply positive stroke offset.",
                        params={"offset_mm": half_stroke},
                    ),
                )
            )

    # Weak bridges: erosion splits a connected part into multiple pieces.
    for p in parts:
        local = _erosion_survivors(MultiPolygon([p]), half_stroke)
        if len(local) > 1:
            violations.append(
                Violation(
                    code=ViolationCode.WEAK_BRIDGE,
                    severity=ValidationSeverity.ERROR,
                    detail=(
                        f"Connected region necks below {rules.min_stroke_mm}mm"
                        f" and would separate ({len(local)} pieces after erosion)."
                    ),
                    location_mm=(p.centroid.x, p.centroid.y),
                    proposed_fix=ProposedFix(
                        action="thicken_bridge",
                        detail="Widen the neck to at least min bridge width.",
                        params={"min_width_mm": rules.min_bridge_mm},
                    ),
                )
            )

    # Gaps: interior holes narrower than the effective minimum gap vanish
    # when the hole polygon is eroded by half the gap.
    hole_count = 0
    half_gap = rules.effective_min_gap_mm / 2
    loop_holes: list[Polygon] = []
    for p in parts:
        for ring in p.interiors:
            hole = Polygon(ring)
            hole_count += 1
            loop_holes.append(hole)
            if hole.buffer(-half_gap, quad_segs=QUAD_SEGS).is_empty:
                violations.append(
                    Violation(
                        code=ViolationCode.GAP_TOO_SMALL,
                        severity=ValidationSeverity.ERROR,
                        detail=(
                            f"Interior gap narrower than {rules.min_gap_mm}mm"
                            f" (kerf-adjusted {rules.effective_min_gap_mm:.2f}mm)."
                        ),
                        location_mm=(hole.centroid.x, hole.centroid.y),
                        proposed_fix=ProposedFix(
                            action="widen_gap",
                            detail="Enlarge cutout or merge into solid.",
                            params={"min_gap_mm": rules.min_gap_mm},
                        ),
                    )
                )

    # Attachment loops: expected loops must exist as holes with the required
    # inner diameter and wall thickness.
    if expected_loops:
        ok_loops = 0
        # 5% tolerance absorbs circle-polygonization error in construction.
        need_r = rules.loop_inner_diameter_mm / 2 * 0.95
        for center in built.loop_centers_mm:
            c = Point(center)
            candidates = [h for h in loop_holes if h.distance(c) < rules.loop_inner_diameter_mm]
            good = False
            for h in candidates:
                # Largest inscribed circle radius of the hole must fit the ring.
                inscribed = h.buffer(-need_r, quad_segs=QUAD_SEGS)
                if not inscribed.is_empty:
                    good = True
                    break
            if good:
                ok_loops += 1
            else:
                violations.append(
                    Violation(
                        code=ViolationCode.UNSAFE_LOOP,
                        severity=ValidationSeverity.ERROR,
                        detail=(
                            f"Attachment loop at {center} missing or inner diameter"
                            f" < {rules.loop_inner_diameter_mm}mm."
                        ),
                        location_mm=center,
                        proposed_fix=ProposedFix(
                            action="enlarge_loop",
                            detail="Increase loop inner diameter.",
                            params={"inner_diameter_mm": rules.loop_inner_diameter_mm},
                        ),
                    )
                )
        if ok_loops < expected_loops and not any(
            v.code == ViolationCode.UNSAFE_LOOP for v in violations
        ):
            violations.append(
                Violation(
                    code=ViolationCode.UNSAFE_LOOP,
                    severity=ValidationSeverity.ERROR,
                    detail=f"Expected {expected_loops} loops, verified {ok_loops}.",
                )
            )

    # Size envelope.
    if built.width_mm > rules.max_width_mm or built.height_mm > rules.max_height_mm:
        violations.append(
            Violation(
                code=ViolationCode.OVERSIZE,
                severity=ValidationSeverity.ERROR,
                detail=(
                    f"Design {built.width_mm:.1f}×{built.height_mm:.1f}mm exceeds"
                    f" {rules.max_width_mm}×{rules.max_height_mm}mm envelope."
                ),
                proposed_fix=ProposedFix(
                    action="rescale",
                    detail="Reduce target height.",
                    params={
                        "max_width_mm": rules.max_width_mm,
                        "max_height_mm": rules.max_height_mm,
                    },
                ),
            )
        )

    return _report(violations, rules, len(parts), hole_count)


def _report(violations, rules: WorkshopRules, n_parts: int, n_holes: int) -> ValidationReport:
    errors = [v for v in violations if v.severity == ValidationSeverity.ERROR]
    return ValidationReport(
        passed=not errors,
        production_export_allowed=not errors,
        violations=violations,
        rules_profile=rules.profile_name,
        checked_component_count=n_parts,
        hole_count=n_holes,
    )
