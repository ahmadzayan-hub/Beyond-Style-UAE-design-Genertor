"""Vector edit operations on the editable visual geometry of a version.

Deterministic, versioned, fail-safe. Every operation works on real mm
polygons (Shapely) and is replayable: a version stores the cumulative
ordered op list, and any later regeneration from the recipe replays it.

Fail-safes (an op that trips one is REJECTED, never silently degraded):
* the confirmed text outline is protected — no op may remove text area
  (cuts that touch letters are refused, mirroring is refused because it
  would reverse the Arabic reading direction);
* the result must be a valid, non-empty polygon set;
* bridges/rings honour the workshop minimums (bridge width, ring inner
  diameter and wall) and must touch the existing design, so an op can
  never create a floating island by construction.

Source text is never touched here — `immutableSourceText` lives on the
version and is untouched by definition; this module only sees geometry.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid

from ..config import WorkshopRules
from .geometry_engine import QUAD_SEGS, BuiltGeometry, _as_multipolygon

SUPPORTED_OPS = ("translate", "rotate", "scale", "add_bridge", "add_ring", "add_shape", "cut_shape")
REFUSED_OPS = {
    "mirror": "Mirroring would reverse the Arabic reading direction; refused.",
    "flip": "Mirroring would reverse the Arabic reading direction; refused.",
    "node_edit": "Node/anchor editing is not implemented; not offered as a fake tool.",
    "pen": "Pen/path drawing is not implemented; not offered as a fake tool.",
}
RING_POSITIONS = ("top_center", "top_left", "top_right", "left", "right", "bottom_center")
TEXT_AREA_EPS_MM2 = 1e-3


class VectorEditRejected(ValueError):
    """An op tripped a fail-safe. The message is user-facing."""


def _num(params: dict, key: str, lo: float, hi: float, default: float | None = None) -> float:
    if key not in params:
        if default is None:
            raise VectorEditRejected(f"Missing parameter '{key}'.")
        return default
    try:
        v = float(params[key])
    except (TypeError, ValueError):
        raise VectorEditRejected(f"Parameter '{key}' must be a number.")
    if not math.isfinite(v) or v < lo or v > hi:
        raise VectorEditRejected(f"Parameter '{key}'={v} outside allowed range [{lo}, {hi}].")
    return v


def _pt(params: dict, key: str) -> tuple[float, float]:
    p = params.get(key)
    if not (isinstance(p, (list, tuple)) and len(p) == 2):
        raise VectorEditRejected(f"Parameter '{key}' must be [x_mm, y_mm].")
    x, y = float(p[0]), float(p[1])
    if not (math.isfinite(x) and math.isfinite(y)) or abs(x) > 500 or abs(y) > 500:
        raise VectorEditRejected(f"Point '{key}' outside the 500 mm working area.")
    return x, y


def _shape(params: dict) -> Polygon:
    kind = params.get("shape")
    if kind == "circle":
        cx, cy = _pt(params, "center")
        d = _num(params, "diameter_mm", 0.3, 100)
        return Point(cx, cy).buffer(d / 2, quad_segs=QUAD_SEGS * 2)
    if kind == "rect":
        x, y = _pt(params, "origin")
        w = _num(params, "width_mm", 0.3, 200)
        h = _num(params, "height_mm", 0.3, 200)
        r = _num(params, "corner_radius_mm", 0, min(w, h) / 2, 0.0)
        rect = box(x, y, x + w, y + h)
        if r > 0:
            rect = rect.buffer(-r, join_style=2).buffer(r, quad_segs=QUAD_SEGS)
        return rect
    if kind == "capsule":
        a = _pt(params, "from")
        b = _pt(params, "to")
        w = _num(params, "width_mm", 0.3, 50)
        return LineString([a, b]).buffer(w / 2, quad_segs=QUAD_SEGS)
    raise VectorEditRejected("shape must be one of circle | rect | capsule.")


def _ring_center(params: dict, geom: MultiPolygon, inner_d: float, wall: float) -> tuple[float, float]:
    """Explicit center, or a named position on the design's bounding box
    placed so the ring's wall overlaps the outline by ~wall/2."""
    if "center" in params:
        return _pt(params, "center")
    pos = params.get("position", "top_center")
    if pos not in RING_POSITIONS:
        raise VectorEditRejected(f"position must be one of {RING_POSITIONS}.")
    minx, miny, maxx, maxy = geom.bounds
    outer_r = inner_d / 2 + wall
    inset = outer_r - wall * 0.5
    cx = (minx + maxx) / 2
    if pos == "top_center":
        c = (cx, maxy + inset)
    elif pos == "bottom_center":
        c = (cx, miny - inset)
    elif pos == "top_left":
        c = (minx + outer_r, maxy + inset)
    elif pos == "top_right":
        c = (maxx - outer_r, maxy + inset)
    elif pos == "left":
        c = (minx - inset, (miny + maxy) / 2)
    else:
        c = (maxx + inset, (miny + maxy) / 2)
    # A silhouette rarely fills its bounding box: solder the ring onto the
    # nearest metal by sliding it toward the outline until the wall overlaps
    # it by wall/2 (the same seating rule the composition engine uses).
    from shapely.ops import nearest_points

    p = Point(c)
    gap = p.distance(geom)
    if gap > 0:
        q = nearest_points(p, geom)[1]
        vx, vy = q.x - p.x, q.y - p.y
        n = math.hypot(vx, vy) or 1.0
        shift = gap - outer_r + wall * 0.5
        if shift > 0:
            c = (p.x + vx / n * shift, p.y + vy / n * shift)
    return c


def _clean(geom) -> MultiPolygon:
    geom = make_valid(geom)
    return _as_multipolygon(geom.buffer(0))


def _text_loss(built: BuiltGeometry) -> float:
    """Area of the text outline that lies outside the metal. Non-zero on
    some generated bases (display-only text layer vs. normalised strokes),
    so protection is measured as ADDITIONAL loss caused by an op."""
    if built.text_geometry is None or built.text_geometry.is_empty or built.geometry.is_empty:
        return 0.0
    return built.text_geometry.difference(built.geometry).area


def _protect_text(before: float, out: BuiltGeometry, what: str) -> None:
    lost = _text_loss(out) - before
    if lost > TEXT_AREA_EPS_MM2:
        raise VectorEditRejected(
            f"{what} would remove {lost:.3f} mm² of the confirmed text outline. "
            "Letters are protected: cut around them or move the shape."
        )


def _transform_all(built: BuiltGeometry, fn) -> BuiltGeometry:
    def tf(g):
        return None if g is None else _as_multipolygon(fn(g))

    centers = []
    for cx, cy in built.loop_centers_mm:
        p = fn(Point(cx, cy))
        centers.append((p.x, p.y))
    return replace(
        built,
        geometry=tf(built.geometry),
        text_geometry=tf(built.text_geometry),
        inner_text_geometry=tf(built.inner_text_geometry),
        loop_centers_mm=centers,
    )


def apply_op(built: BuiltGeometry, op: dict[str, Any], rules: WorkshopRules) -> tuple[BuiltGeometry, dict]:
    """Apply ONE op. Returns (new_built, log_entry). Raises VectorEditRejected."""
    name = op.get("op")
    params = op.get("params") or {}
    if not isinstance(params, dict):
        raise VectorEditRejected("params must be an object.")
    if name in REFUSED_OPS:
        raise VectorEditRejected(REFUSED_OPS[name])
    if name not in SUPPORTED_OPS:
        raise VectorEditRejected(f"Unknown op '{name}'. Supported: {', '.join(SUPPORTED_OPS)}.")
    geom = built.geometry
    if geom.is_empty:
        raise VectorEditRejected("Nothing to edit: the version has no geometry.")
    log: dict[str, Any] = {"op": name}
    loss_before = _text_loss(built)

    if name == "translate":
        dx = _num(params, "dx_mm", -200, 200)
        dy = _num(params, "dy_mm", -200, 200)
        out = _transform_all(built, lambda g: affinity.translate(g, dx, dy))
        log.update(dx_mm=dx, dy_mm=dy)
    elif name == "rotate":
        ang = _num(params, "angle_deg", -180, 180)
        b = geom.bounds
        origin = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        out = _transform_all(built, lambda g: affinity.rotate(g, ang, origin=origin))
        log.update(angle_deg=ang)
    elif name == "scale":
        f = _num(params, "factor", 0.5, 2.0)
        b = geom.bounds
        origin = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        out = _transform_all(built, lambda g: affinity.scale(g, f, f, origin=origin))
        log.update(factor=f, note="uniform scale only; stroke widths scale with it and are re-validated")
    elif name == "add_bridge":
        a = _pt(params, "from")
        b2 = _pt(params, "to")
        w = _num(params, "width_mm", 0.1, 20, rules.min_bridge_mm)
        if w < rules.min_bridge_mm - 1e-9:
            raise VectorEditRejected(f"Bridge width {w} mm is below the workshop minimum {rules.min_bridge_mm} mm.")
        bridge = LineString([a, b2]).buffer(w / 2, quad_segs=QUAD_SEGS)
        if not bridge.intersects(geom):
            raise VectorEditRejected("Bridge does not touch the design; it would be a floating piece.")
        out = replace(built, geometry=_clean(unary_union([geom, bridge])), bridges_added=built.bridges_added + 1)
        log.update(width_mm=w, length_mm=round(LineString([a, b2]).length, 3))
    elif name == "add_ring":
        inner_d = _num(params, "inner_diameter_mm", 0.5, 20, rules.loop_inner_diameter_mm)
        wall = _num(params, "wall_mm", 0.3, 10, rules.loop_wall_mm)
        if inner_d < rules.loop_inner_diameter_mm - 1e-9 or wall < rules.loop_wall_mm - 1e-9:
            raise VectorEditRejected(
                f"Ring below workshop minimum (inner ⌀ {rules.loop_inner_diameter_mm} mm, wall {rules.loop_wall_mm} mm)."
            )
        cx, cy = _ring_center(params, geom, inner_d, wall)
        outer = Point(cx, cy).buffer(inner_d / 2 + wall, quad_segs=QUAD_SEGS * 2)
        hole = Point(cx, cy).buffer(inner_d / 2, quad_segs=QUAD_SEGS * 2)
        if not outer.intersects(geom):
            raise VectorEditRejected("Ring does not touch the design; move it onto the outline.")
        if built.text_geometry is not None and hole.buffer(0.05).intersects(built.text_geometry):
            raise VectorEditRejected("Ring hole would cut into the letters; move it outward.")
        merged = unary_union([geom, outer]).difference(hole)
        out = replace(built, geometry=_clean(merged), loop_centers_mm=[*built.loop_centers_mm, (cx, cy)])
        log.update(center_mm=[round(cx, 3), round(cy, 3)], inner_diameter_mm=inner_d, wall_mm=wall)
    elif name == "add_shape":
        shp = _shape(params)
        if not shp.intersects(geom):
            raise VectorEditRejected("Shape does not touch the design; it would be a floating piece.")
        out = replace(built, geometry=_clean(unary_union([geom, shp])))
        log.update(shape=params.get("shape"), area_mm2=round(shp.area, 3))
    else:  # cut_shape
        shp = _shape(params)
        if built.text_geometry is not None and shp.intersection(built.text_geometry).area > TEXT_AREA_EPS_MM2:
            raise VectorEditRejected("Cut would remove part of the confirmed text outline; letters are protected.")
        for cx, cy in built.loop_centers_mm:
            if shp.distance(Point(cx, cy)) < rules.loop_inner_diameter_mm / 2 + rules.loop_wall_mm:
                raise VectorEditRejected("Cut would weaken a chain ring wall.")
        cut = geom.difference(shp)
        if cut.is_empty:
            raise VectorEditRejected("Cut would remove the whole design.")
        out = replace(built, geometry=_clean(cut))
        log.update(shape=params.get("shape"), area_mm2=round(shp.area, 3))

    if out.geometry.is_empty or not out.geometry.is_valid:
        raise VectorEditRejected(f"'{name}' produced invalid or empty geometry; refused.")
    _protect_text(loss_before, out, f"'{name}'")
    log["bounds_mm"] = [round(v, 3) for v in out.geometry.bounds]
    return out, log


def apply_ops(built: BuiltGeometry, ops: list[dict[str, Any]], rules: WorkshopRules) -> tuple[BuiltGeometry, list[dict]]:
    """Replay an ordered op list. All-or-nothing: the first rejected op
    aborts and the caller keeps the untouched input."""
    if len(ops) > 200:
        raise VectorEditRejected("Too many vector operations on one version (max 200).")
    logs: list[dict] = []
    cur = built
    for i, op in enumerate(ops):
        try:
            cur, entry = apply_op(cur, op, rules)
        except VectorEditRejected as exc:
            raise VectorEditRejected(f"op {i + 1} ({op.get('op')}): {exc}") from None
        logs.append(entry)
    return cur, logs
