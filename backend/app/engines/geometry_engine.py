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
    geometry: MultiPolygon  # final geometry, mm
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


def bridge_components(geom, bridge_width_mm: float, max_bridges: int = 24) -> tuple[MultiPolygon, int]:
    """Deterministically connect disconnected parts with straight bridges of
    `bridge_width_mm` along the shortest line between the smallest part and
    the largest remaining body. Purely geometric, repeatable, testable."""
    geom = _as_multipolygon(geom)
    added = 0
    while len(geom.geoms) > 1 and added < max_bridges:
        parts = sorted(geom.geoms, key=lambda p: (p.area, p.bounds))
        small = parts[0]
        rest = unary_union(parts[1:])
        p1, p2 = nearest_points(small, rest)
        # Extend slightly into both bodies to guarantee overlap.
        line = LineString([p1, p2])
        if line.length == 0:
            line = LineString([p1, Point(p2.x + 1e-6, p2.y + 1e-6)])
        bridge = line.buffer(bridge_width_mm / 2, cap_style="square", quad_segs=QUAD_SEGS)
        geom = _as_multipolygon(unary_union([geom, bridge]))
        added += 1
    return geom, added


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


def compose(runs: list[ShapedRun], recipe: RecipeParams, loop_inner_d: float, loop_wall: float, bridge_width: float, min_gap_eff: float = 0.4) -> BuiltGeometry:
    """Full parametric construction for one candidate."""
    body, issues = build_text_body(runs, recipe)
    if body.is_empty:
        return BuiltGeometry(geometry=MultiPolygon([]), outline_issues=issues)

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
    # "bare": text only; dots must be bridged.

    geom = _as_multipolygon(unary_union(parts))

    bridges = 0
    if recipe.dot_strategy == "bridge":
        geom, bridges = bridge_components(geom, bridge_width)

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
            geom, extra = bridge_components(geom, bridge_width)
            bridges += extra

    geom = _as_multipolygon(geom.buffer(0))
    return BuiltGeometry(
        geometry=geom,
        outline_issues=issues,
        bridges_added=bridges,
        loop_centers_mm=loop_centers,
    )
