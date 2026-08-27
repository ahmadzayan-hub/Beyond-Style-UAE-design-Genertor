"""Real millimetre measurements of built jewellery geometry.

Every number here comes from the FINAL mm geometry — after glyph outlines
have been placed, scaled, stroked and composed — not from font units and not
from a ratio. These are the numbers a manufacturing decision may rest on.

The relative stroke figure in `app/fonts/axes.py` is explicitly NOT one of
these: it is an aesthetic/relative metric over font units and is labelled as
such. Nothing in this module may be sourced from it.

Method: deterministic bisection on morphological erosion/dilation. Eroding a
shape by e/2 removes anything narrower than e, so the largest e that leaves
the shape non-empty is its minimum material width. The same idea run on the
complement gives the minimum gap.
"""
from __future__ import annotations

from shapely.geometry import MultiPolygon, Polygon

#: Bisection bounds in mm. 0.02mm resolution is far finer than any workshop
#: tolerance, so the answer is limited by the geometry, not the search.
_SEARCH_MAX_MM = 12.0
_TOLERANCE_MM = 0.02

MEASUREMENT_BASIS = "REAL_MM_FROM_BUILT_GEOMETRY"


def _bisect(predicate, lo: float = 0.0, hi: float = _SEARCH_MAX_MM) -> float:
    """Largest value in [lo, hi] for which `predicate` still holds."""
    if not predicate(lo):
        return 0.0
    while hi - lo > _TOLERANCE_MM:
        mid = (lo + hi) / 2
        if predicate(mid):
            lo = mid
        else:
            hi = mid
    return round(lo, 3)


def min_material_width_mm(geom) -> float:
    """Narrowest solid material anywhere in the piece."""
    if geom is None or geom.is_empty:
        return 0.0
    survives = lambda e: not geom.buffer(-e / 2).is_empty  # noqa: E731
    return _bisect(survives)


def min_gap_mm(geom) -> float:
    """Narrowest gap between separate pieces of material.

    Exact pairwise distance between components rather than a dilation
    search: dilation returns 0 as soon as any two parts touch, which hides
    the real spacing everywhere else. `inf` when the piece is a single
    connected component."""
    if geom is None or geom.is_empty:
        return 0.0
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    if len(polys) < 2:
        return float("inf")
    gaps = [
        polys[i].distance(polys[j])
        for i in range(len(polys))
        for j in range(i + 1, len(polys))
    ]
    return round(min(gaps), 3)


def _interior_rings(geom) -> list:
    polys = geom.geoms if hasattr(geom, "geoms") else [geom]
    return [ring for p in polys if isinstance(p, Polygon) for ring in p.interiors]


def counter_clearance_mm(geom) -> float:
    """Smallest opening inside a letter counter — the hole that closes first
    when the material thickens. `inf` when the piece has no counters."""
    rings = _interior_rings(geom)
    if not rings:
        return float("inf")
    clearances = []
    for ring in rings:
        hole = Polygon(ring)
        if hole.is_empty or not hole.is_valid:
            continue
        clearances.append(_bisect(lambda e, h=hole: not h.buffer(-e / 2).is_empty))
    return round(min(clearances), 3) if clearances else float("inf")


def island_areas_mm2(geom, small_threshold_mm2: float = 1.0) -> dict:
    """Disconnected components, and which of them are too small to handle."""
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    areas = sorted(round(p.area, 4) for p in polys)
    return {
        "component_count": len(polys),
        "areas_mm2": areas,
        "small_islands": [a for a in areas if a < small_threshold_mm2],
        "small_island_threshold_mm2": small_threshold_mm2,
    }


def overall_dimensions_mm(geom) -> dict:
    if geom is None or geom.is_empty:
        return {"width_mm": 0.0, "height_mm": 0.0, "area_mm2": 0.0}
    minx, miny, maxx, maxy = geom.bounds
    return {
        "width_mm": round(maxx - minx, 3),
        "height_mm": round(maxy - miny, 3),
        "area_mm2": round(geom.area, 3),
    }


def measure_mm(geom, attachment_geom=None) -> dict:
    """The full real-mm measurement set for one built piece.

    `attachment_geom` is the loop/bail region when the composition has one;
    its narrowest material is reported separately because an attachment
    carries the whole weight of the piece."""
    if geom is None or geom.is_empty:
        return {"basis": MEASUREMENT_BASIS, "empty": True}
    result = {
        "basis": MEASUREMENT_BASIS,
        "empty": False,
        "min_material_width_mm": min_material_width_mm(geom),
        "min_gap_mm": min_gap_mm(geom),
        "counter_clearance_mm": counter_clearance_mm(geom),
        **island_areas_mm2(geom),
        **overall_dimensions_mm(geom),
    }
    result["bridge_width_mm"] = result["min_material_width_mm"]
    result["counter_count"] = len(_interior_rings(geom))
    result["attachment_width_mm"] = (
        min_material_width_mm(attachment_geom) if attachment_geom is not None else None
    )
    # inf is not JSON — report the honest reason instead of a fake number.
    for key in ("min_gap_mm", "counter_clearance_mm"):
        if result[key] == float("inf"):
            result[key] = None
            result[f"{key}_status"] = "NOT_APPLICABLE_NO_GAP_OR_COUNTER"
    return result


def meets_workshop_rules(measurements: dict, rules) -> dict:
    """Compare REAL mm measurements against the workshop profile.

    This is the manufacturing decision surface. A relative or aesthetic
    metric may never appear here."""
    if measurements.get("empty"):
        return {"passed": False, "failures": ["empty geometry"], "basis": MEASUREMENT_BASIS}
    failures = []
    if measurements["min_material_width_mm"] < rules.min_stroke_mm:
        failures.append(
            f"min material {measurements['min_material_width_mm']}mm "
            f"< required {rules.min_stroke_mm}mm"
        )
    gap = measurements.get("min_gap_mm")
    if gap is not None and gap < rules.min_gap_mm:
        failures.append(f"min gap {gap}mm < required {rules.min_gap_mm}mm")
    counter = measurements.get("counter_clearance_mm")
    if counter is not None and counter < rules.min_gap_mm:
        failures.append(
            f"counter clearance {counter}mm < required {rules.min_gap_mm}mm "
            "(letter openings closing up)"
        )
    if measurements["small_islands"]:
        failures.append(f"{len(measurements['small_islands'])} island(s) below handling size")
    if (measurements["width_mm"] > rules.max_width_mm
            or measurements["height_mm"] > rules.max_height_mm):
        failures.append(
            f"{measurements['width_mm']}×{measurements['height_mm']}mm exceeds "
            f"{rules.max_width_mm}×{rules.max_height_mm}mm envelope"
        )
    return {"passed": not failures, "failures": failures, "basis": MEASUREMENT_BASIS}
