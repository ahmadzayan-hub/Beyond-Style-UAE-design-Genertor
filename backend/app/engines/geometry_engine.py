"""Parametric jewellery geometry engine.

Turns shaped glyph runs + a RecipeParams into real-mm vector geometry:
glyph outlines → per-glyph polygons (even-odd fill) → positioned text body
→ parametric transforms (scale, spacing, stroke delta) → composition
(bars/plates/frames) → deterministic dot bridging → attachment loops.

The output is a shapely (Multi)Polygon in millimetres plus construction
metadata. Source text is never touched here — only visual geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from ..fonts.registry import get_registry
from ..schemas.jewellery_design import RecipeParams, ShapedRun
from .arabic_engine import upem
from .outline_extractor import extract_contours

QUAD_SEGS = 8  # deterministic buffer resolution


@dataclass
class BuiltGeometry:
    geometry: MultiPolygon  # final manufacturing silhouette, mm (canonical)
    # Text-only geometry in the same final coordinates. Used by the proof
    # renderer to differentiate raised text on solid plates. Display aid
    # only — the manufacturing truth remains `geometry`.
    text_geometry: MultiPolygon | None = None
    outline_issues: list[str] = field(default_factory=list)
    bridges_added: int = 0
    loop_centers_mm: list[tuple[float, float]] = field(default_factory=list)

    @property
    def width_mm(self) -> float:
        b = self.geometry.bounds
        return b[2] - b[0]

    @property
    def height_mm(self) -> float:
        b = self.geometry.bounds
        return b[3] - b[1]


def _contours_to_polygon(contours: list[list[tuple[float, float]]]) -> Polygon | MultiPolygon | None:
    """Even-odd combination of closed contours (XOR), robust to winding."""
    result = None
    for pts in contours:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        result = poly if result is None else result.symmetric_difference(poly)
    if result is None or result.is_empty:
        return None
    if result.geom_type == "GeometryCollection":
        polys = [g for g in result.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        result = unary_union(polys) if polys else None
    return result


def build_text_body(runs: list[ShapedRun], recipe: RecipeParams) -> tuple[Polygon | MultiPolygon, list[str]]:
    """Place glyph polygons using HarfBuzz advances/offsets (font units),
    then scale to target mm height. Letter spacing is added between glyphs.
    """
    font = get_registry().get(recipe.font_id)
    units = upem(font)
    issues: list[str] = []
    glyph_polys = []
    pen_x = 0.0
    # Extra tracking in font units, applied after each glyph.
    spacing_units = recipe.letter_spacing_mm / recipe.target_height_mm * units if recipe.target_height_mm else 0
    for run in runs:
        for g in run.glyphs:
            contours, gi = extract_contours(str(font.path), g.glyph_id)
            issues.extend(gi)
            poly = _contours_to_polygon(contours)
            if poly is not None:
                placed = affinity.translate(poly, xoff=pen_x + g.x_offset_mm, yoff=g.y_offset_mm)
                glyph_polys.append(placed)
            pen_x += g.x_advance_mm + spacing_units
    body = unary_union(glyph_polys)
    if body.is_empty:
        return body, issues + ["empty text body"]

    # Scale to target height in mm, then apply anisotropic recipe scaling.
    minx, miny, maxx, maxy = body.bounds
    h = maxy - miny
    s = recipe.target_height_mm / h if h > 0 else 1.0
    body = affinity.scale(body, xfact=s * recipe.x_scale, yfact=s * recipe.y_scale, origin=(0, 0))
    minx, miny, _, _ = body.bounds
    body = affinity.translate(body, xoff=-minx, yoff=-miny)

    if recipe.stroke_delta_mm:
        body = body.buffer(recipe.stroke_delta_mm, quad_segs=QUAD_SEGS)
    return body, issues


def build_stacked_body(line_runs, recipe) -> tuple[Polygon | MultiPolygon, list[str]]:
    """Stacked multi-line text body: each line built and scaled to the
    target line height, centre-aligned, stacked top-to-bottom (first line
    on top) with proportional spacing. Deterministic."""
    from shapely import affinity as aff

    issues: list[str] = []
    bodies = []
    for runs in line_runs:
        body, iss = build_text_body(runs, recipe)
        issues.extend(iss)
        if not body.is_empty:
            bodies.append(body)
    if not bodies:
        return MultiPolygon([]), issues + ["empty text body"]
    spacing = recipe.target_height_mm * recipe.line_spacing_ratio
    placed = []
    y_cursor = 0.0
    for body in bodies:  # first line at top
        minx, miny, maxx, maxy = body.bounds
        h = maxy - miny
        w = maxx - minx
        shifted = aff.translate(body, xoff=-(minx + w / 2), yoff=y_cursor - maxy)
        placed.append(shifted)
        y_cursor -= h + spacing
    merged = unary_union(placed)
    minx, miny, _, _ = merged.bounds
    return aff.translate(merged, xoff=-minx, yoff=-miny), issues


def _as_multipolygon(geom) -> MultiPolygon:
    if geom.is_empty:
        return MultiPolygon([])
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    polys = [g for g in geom.geoms if g.geom_type == "Polygon"]
    for g in geom.geoms:
        if g.geom_type == "MultiPolygon":
            polys.extend(g.geoms)
    return MultiPolygon(polys)


def _bridge_target(small, rest, style: str, frame_center=None):
    """Aesthetic bridge anchor selection.

    - "vertical": dots/marks connect straight up/down to their own letter —
      the visually natural join. Restrict the target to a vertical slab
      around the part; fall back to nearest.
    - "radial": in frames/medallions, connect outward along the ray from the
      frame centre — like real medallion spokes, never a chord.
    - "nearest": shortest path (fallback).
    """
    if style == "vertical":
        minx, miny, maxx, maxy = small.bounds
        w = maxx - minx
        slab = box(minx - w * 0.6, -1e6, maxx + w * 0.6, 1e6)
        clipped = rest.intersection(slab)
        if not clipped.is_empty:
            return nearest_points(small, clipped)
    elif style == "radial" and frame_center is not None:
        cx, cy = frame_center
        px, py = small.centroid.x, small.centroid.y
        dx, dy = px - cx, py - cy
        norm = (dx * dx + dy * dy) ** 0.5
        if norm > 1e-9:
            far = Point(cx + dx / norm * 1e4, cy + dy / norm * 1e4)
            ray = LineString([(px, py), (far.x, far.y)])
            hit = rest.intersection(ray)
            if not hit.is_empty:
                target = nearest_points(small.centroid, hit)[1]
                return nearest_points(small, target)[0], target
    return nearest_points(small, rest)


def bridge_components(
    geom,
    bridge_width_mm: float,
    max_bridges: int = 24,
    style: str = "vertical",
    frame_center=None,
    fillet_mm: float = 0.1,
) -> tuple[MultiPolygon, int]:
    """Deterministically connect disconnected parts with aesthetic,
    manufacturing-aware bridges: flow-following anchors (see
    `_bridge_target`), round caps, and a morphological-closing fillet that
    softens the junctions. Output is validated downstream like any
    geometry."""
    geom = _as_multipolygon(geom)
    added = 0
    while len(geom.geoms) > 1 and added < max_bridges:
        parts = sorted(geom.geoms, key=lambda p: (p.area, p.bounds))
        small = parts[0]
        rest = unary_union(parts[1:])
        p1, p2 = _bridge_target(small, rest, style, frame_center)
        line = LineString([p1, p2])
        if line.length == 0:
            line = LineString([p1, Point(p2.x + 1e-6, p2.y + 1e-6)])
        bridge = line.buffer(bridge_width_mm / 2, cap_style="round", quad_segs=QUAD_SEGS)
        geom = _as_multipolygon(unary_union([geom, bridge]))
        added += 1
    if added and fillet_mm > 0:
        # Closing fillet: smooths bridge junctions without moving strokes.
        geom = _as_multipolygon(
            geom.buffer(fillet_mm, quad_segs=QUAD_SEGS).buffer(-fillet_mm, quad_segs=QUAD_SEGS)
        )
    return geom, added


def restyle_dots(body, style: dict, text_height_mm: float):
    """Replace detached dot components with a styled shape of equal area at
    the same centroid (round/diamond/square/petal). Only clearly dot-sized
    detached parts are restyled — letter bodies are never touched, and the
    identity proof is unaffected (dots remain rendered source glyphs)."""
    from shapely import affinity as aff

    parts = list(_as_multipolygon(body).geoms)
    if len(parts) <= 1 or style.get("shape", "circle") == "circle":
        return body
    max_area = max(p.area for p in parts)
    dot_limit_area = (0.22 * text_height_mm) ** 2
    out = []
    for p in parts:
        minx, miny, maxx, maxy = p.bounds
        size = max(maxx - minx, maxy - miny)
        is_dot = p.area < min(max_area * 0.2, dot_limit_area) and size < 0.3 * text_height_mm
        if not is_dot:
            out.append(p)
            continue
        c = p.centroid
        r = (p.area / 3.14159) ** 0.5 * style.get("scale", 1.0)
        shape_kind = style["shape"]
        if shape_kind == "diamond":
            s = Point(c).buffer(r * 1.25, quad_segs=1)  # square-ish
            s = aff.rotate(s, 45, origin=(c.x, c.y))
        elif shape_kind == "square":
            s = box(c.x - r, c.y - r, c.x + r, c.y + r)
        elif shape_kind == "petal":
            a = Point(c.x - r * 0.5, c.y).buffer(r, quad_segs=QUAD_SEGS)
            b = Point(c.x + r * 0.5, c.y).buffer(r, quad_segs=QUAD_SEGS)
            s = a.intersection(b)
        else:
            s = Point(c).buffer(r, quad_segs=QUAD_SEGS)
        out.append(s)
    return unary_union(out)


def _bezier_points(p0, p1, p2, p3, steps=24):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def build_swash(body_bounds, spec: dict, thickness_mm: float):
    """Parametric decorative flourish (pure ornament, never letter
    geometry). Deterministic cubic curves buffered to a tapered stroke."""
    minx, miny, maxx, maxy = body_bounds
    w = maxx - minx
    h = maxy - miny
    depth = h * spec.get("depth_ratio", 0.2)
    ext = w * spec.get("extend_ratio", 0.12)
    th = max(thickness_mm * spec.get("thickness_ratio", 0.6), 0.5)
    kind = spec.get("kind")
    curves = []
    if kind == "underline_curve":
        curves.append(_bezier_points(
            (maxx + ext, miny + h * 0.12), (maxx - w * 0.2, miny - depth),
            (minx + w * 0.2, miny - depth), (minx - ext, miny + h * 0.12)))
    elif kind == "end_curve":
        # Trailing sweep at the RTL end (left side), curling upward.
        curves.append(_bezier_points(
            (minx + w * 0.12, miny + h * 0.15), (minx - ext * 0.6, miny - depth),
            (minx - ext, miny + h * 0.25), (minx - ext * 0.7, miny + h * 0.7)))
    elif kind == "double_curve":
        curves.append(_bezier_points(
            (minx + w * 0.05, miny + h * 0.1), (minx - ext * 2, miny - depth),
            (minx - ext * 2.5, miny + h * 0.35), (minx - ext * 1.2, miny + h * 0.5)))
        curves.append(_bezier_points(
            (maxx - w * 0.05, miny + h * 0.1), (maxx + ext * 2, miny - depth),
            (maxx + ext * 2.5, miny + h * 0.35), (maxx + ext * 1.2, miny + h * 0.5)))
    parts = [LineString(c).buffer(th / 2, cap_style="round", quad_segs=QUAD_SEGS) for c in curves if len(c) > 1]
    return unary_union(parts) if parts else None


def fill_small_holes(geom, min_gap_eff_mm: float) -> MultiPolygon:
    """Fill interior holes narrower than the effective minimum cuttable gap.

    Standard laser/casting practice: counters below the cuttable size are
    left solid rather than cut. Deterministic construction step — applied
    BEFORE attachment loops so loop holes are never filled.
    """
    geom = _as_multipolygon(geom)
    half = min_gap_eff_mm / 2
    out = []
    for part in geom.geoms:
        keep = [
            ring
            for ring in part.interiors
            if not Polygon(ring).buffer(-half, quad_segs=QUAD_SEGS).is_empty
        ]
        out.append(Polygon(part.exterior, keep))
    return MultiPolygon(out)


def _loop_ring(center: tuple[float, float], inner_d: float, wall: float) -> Polygon:
    outer = Point(center).buffer(inner_d / 2 + wall, quad_segs=QUAD_SEGS * 2)
    inner = Point(center).buffer(inner_d / 2, quad_segs=QUAD_SEGS * 2)
    return outer.difference(inner)


def compose(runs: list[ShapedRun], recipe: RecipeParams, loop_inner_d: float, loop_wall: float, bridge_width: float, min_gap_eff: float = 0.4, line_runs=None, fit_width_mm: float | None = None) -> BuiltGeometry:
    """Full parametric construction for one candidate."""
    if line_runs is not None and len(line_runs) > 1:
        body, issues = build_stacked_body(line_runs, recipe)
        # Deterministic width-fit: shrink per-line height (floor 5.5mm) so
        # long stacked compositions respect the product envelope. Stroke
        # delta stays in absolute mm, so boldness is preserved.
        if fit_width_mm and not body.is_empty:
            bminx, _, bmaxx, _ = body.bounds
            width = bmaxx - bminx
            if width > fit_width_mm:
                factor = fit_width_mm / width
                new_h = max(round(recipe.target_height_mm * factor, 2), 5.5)
                if new_h < recipe.target_height_mm:
                    fitted = recipe.model_copy(update={"target_height_mm": new_h})
                    body, issues = build_stacked_body(line_runs, fitted)
    else:
        body, issues = build_text_body(runs, recipe)
    if body.is_empty:
        return BuiltGeometry(geometry=MultiPolygon([]), outline_issues=issues)

    # Glyph Variant Library: dot restyling (identity-preserving).
    if recipe.dot_style != "round":
        from ..fonts.glyph_variants import dot_style_spec

        body = restyle_dots(body, dot_style_spec(recipe.dot_style), recipe.target_height_mm)

    # Decorative swash flourish (pure ornament).
    if recipe.swash != "none":
        from ..fonts.glyph_variants import swash_spec

        sw = build_swash(body.bounds, swash_spec(recipe.swash), recipe.connector_height_mm)
        if sw is not None:
            body = unary_union([body, sw])

    text_body = _as_multipolygon(body)
    minx, miny, maxx, maxy = body.bounds
    w, h = maxx - minx, maxy - miny
    ch = recipe.connector_height_mm
    parts = [body]

    if recipe.composition == "baseline_bar":
        # Bar through the lower third of the text: connects letters and dots.
        y0 = miny + h * 0.22
        parts.append(box(minx - ch, y0, maxx + ch, y0 + ch))
    elif recipe.composition == "underline_bar":
        parts.append(box(minx - ch * 2, miny - ch, maxx + ch * 2, miny + ch * 0.35))
    elif recipe.composition == "plate_oval":
        m = recipe.frame_margin_mm
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        plate = affinity.scale(Point(cx, cy).buffer(1, quad_segs=QUAD_SEGS * 4), xfact=w / 2 + m, yfact=h / 2 + m, origin=(cx, cy))
        parts.append(plate)
    elif recipe.composition == "plate_rect":
        m = recipe.frame_margin_mm
        plate = box(minx - m, miny - m, maxx + m, maxy + m).buffer(0)
        parts.append(plate)
    elif recipe.composition == "frame_circle":
        m = recipe.frame_margin_mm
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        r = ((w / 2 + m) ** 2 + (h / 2 + m) ** 2) ** 0.5
        ring = Point(cx, cy).buffer(r + ch, quad_segs=QUAD_SEGS * 4).difference(
            Point(cx, cy).buffer(r, quad_segs=QUAD_SEGS * 4)
        )
        parts.append(ring)
    elif recipe.composition == "frame_rect":
        # Open rectangular frame around the text (openwork tag).
        m = recipe.frame_margin_mm
        outer = box(minx - m - ch, miny - m - ch, maxx + m + ch, maxy + m + ch)
        inner = box(minx - m, miny - m, maxx + m, maxy + m)
        parts.append(outer.difference(inner))
    elif recipe.composition == "top_bar":
        # Hanging bar above the text; letters suspend from it.
        parts.append(box(minx - ch, maxy - ch * 0.3, maxx + ch, maxy + ch))
    # "bare": text only; dots must be bridged.

    geom = _as_multipolygon(unary_union(parts))

    bridges = 0
    frame_center = None
    bridge_style = "vertical"
    if recipe.composition in ("frame_circle", "frame_rect"):
        gminx, gminy, gmaxx, gmaxy = geom.bounds
        frame_center = ((gminx + gmaxx) / 2, (gminy + gmaxy) / 2)
        bridge_style = "radial"
    if recipe.dot_strategy == "bridge":
        geom, bridges = bridge_components(
            geom, bridge_width, style=bridge_style, frame_center=frame_center
        )

    # Fill counters below the cuttable gap size (before loops, so loop
    # holes are never affected).
    geom = fill_small_holes(geom, min_gap_eff)

    # Attachment loops go on last so they fuse with the final silhouette.
    loop_centers: list[tuple[float, float]] = []
    if recipe.loops != "none":
        minx, miny, maxx, maxy = geom.bounds
        r_out = loop_inner_d / 2 + loop_wall
        if recipe.loops == "top":
            centers = [((minx + maxx) / 2, maxy + r_out * 0.55)]
        else:  # left_right
            cy = (miny + maxy) / 2
            centers = [(minx - r_out * 0.55, cy), (maxx + r_out * 0.55, cy)]
        for c in centers:
            geom = _as_multipolygon(unary_union([geom, _loop_ring(c, loop_inner_d, loop_wall)]))
            loop_centers.append(c)
        # Loops overlap the body by design; if any remained detached, bridge.
        if recipe.dot_strategy == "bridge":
            geom, extra = bridge_components(
                geom, bridge_width, style=bridge_style, frame_center=frame_center
            )
            bridges += extra

    geom = _as_multipolygon(geom.buffer(0))
    return BuiltGeometry(
        geometry=geom,
        text_geometry=text_body,
        outline_issues=issues,
        bridges_added=bridges,
        loop_centers_mm=loop_centers,
    )
