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
from .arabic_engine import DECORATIVE_GLYPH_ID, upem
from .outline_extractor import extract_contours

QUAD_SEGS = 8  # deterministic buffer resolution


@dataclass
class BuiltGeometry:
    geometry: MultiPolygon  # final manufacturing silhouette, mm (canonical)
    # Text-only geometry in the same final coordinates. Used by the proof
    # renderer to differentiate raised text on solid plates. Display aid
    # only — the manufacturing truth remains `geometry`.
    text_geometry: MultiPolygon | None = None
    # Ring inner-face engraving (flat pattern, mirrored for the back face).
    inner_text_geometry: MultiPolygon | None = None
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



def decorative_polygon(glyph_name: str, units: int) -> Polygon:
    """Deterministic outlines for decorative symbols, in font units.
    heart: two circles + a point, ~0.55 em tall, centred in a 0.95 em
    advance, raised to sit on the x-height band like a separator."""
    import math

    kind = glyph_name.split(".", 1)[-1]
    if kind != "heart":
        raise ValueError(f"unknown decorative symbol {glyph_name}")
    em = float(units)
    size = 0.55 * em
    cx = 0.95 * em / 2
    base_y = 0.12 * em
    r = size * 0.27
    top = base_y + size
    lobes = unary_union([
        Point(cx - r * 0.98, top - r).buffer(r, resolution=24),
        Point(cx + r * 0.98, top - r).buffer(r, resolution=24),
    ])
    body = Polygon([
        (cx - 2 * r * 0.98 - r * 0.02, top - r),
        (cx, base_y),
        (cx + 2 * r * 0.98 + r * 0.02, top - r),
    ])
    return unary_union([lobes, body])


def build_text_body(runs: list[ShapedRun], recipe: RecipeParams) -> tuple[Polygon | MultiPolygon, list[str]]:
    """Place glyph polygons using HarfBuzz advances/offsets (font units),
    then scale to target mm height. Letter spacing is added between glyphs.
    """
    font = get_registry().get(recipe.font_id)
    units = upem(font)
    # Outlines are pulled at the SAME coordinates the runs were shaped at.
    from ..fonts.instances import normalize_axes

    axes = normalize_axes(recipe.font_axes)
    issues: list[str] = []
    glyph_polys = []
    pen_x = 0.0
    # Extra tracking in font units, applied after each glyph.
    spacing_units = recipe.letter_spacing_mm / recipe.target_height_mm * units if recipe.target_height_mm else 0
    for run in runs:
        for g in run.glyphs:
            if g.glyph_id == DECORATIVE_GLYPH_ID:
                # Parametric symbol (e.g. ♥): drawn by the engine, never a
                # font substitution. Sized relative to the em so it sits
                # with the letters at any text height.
                poly = decorative_polygon(g.glyph_name, units)
                glyph_polys.append(affinity.translate(poly, xoff=pen_x + g.x_offset_mm, yoff=g.y_offset_mm))
                pen_x += g.x_advance_mm + spacing_units
                continue
            contours, gi = extract_contours(str(font.path), g.glyph_id, axes)
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

    if recipe.ring is not None:
        # Engraved band text is cut by the engraver's line width, not the
        # sheet-cut minimums: keep the curated buffer, no cut normalisation.
        if recipe.stroke_delta_mm:
            body = body.buffer(recipe.stroke_delta_mm, quad_segs=QUAD_SEGS)
        return body, issues
    delta = effective_stroke_delta(body, recipe)
    if delta:
        body = body.buffer(delta, quad_segs=QUAD_SEGS)
    return body, issues


#: Jewellery realism (owner review 2026-09-04: "the designs are not real").
#: Fine name jewellery reads at a mean stroke of roughly 8 % of the text
#: height (about 1.0 mm on a 12 mm name). Fonts are typographic, not
#: metalwork: heavy faces plus a fixed positive buffer produced 1.3–1.7 mm
#: strokes that looked melted. The recipe's stroke_delta is now the UPPER
#: bound of the buffer; the effective buffer is chosen so the mean stroke
#: lands on the target, with a small erosion allowed for bold faces. The
#: manufacturing validator still enforces the absolute minimum stroke.
TARGET_STROKE_RATIO = 0.082
MIN_TARGET_STROKE_MM = 0.85
#: Narrowest metal the lettering should carry (hairlines, necks): the
#: workshop bridge minimum (0.8 mm) plus margin. A local "thicken only the
#: thin parts" pass was tried and measured to LOWER validity (it seeds
#: slivers next to neighbouring strokes), so modulated faces are lifted
#: with a global buffer sized from their hairlines instead.
MIN_NECK_MM = 0.85
#: Detached dots are normalised to crisp circles of at least this diameter
#: before bridging — a real jeweller never cuts a 0.6 mm speck.
MIN_DOT_DIAMETER_MM = 1.25
#: Junction fillet reach where a letter meets a frame/ring wall.
JUNCTION_FILLET_MM = 0.55


def thin_parts(body, min_w: float):
    """Regions of `body` narrower than `min_w` (opening residue, corner
    slivers removed). One cheap morphological pass — shared by the
    contrast test and the hairline enforcement."""
    if body.is_empty:
        return body
    opened = body.buffer(-min_w / 2, quad_segs=QUAD_SEGS).buffer(min_w / 2 + 0.02, quad_segs=QUAD_SEGS)
    thin = body.difference(opened)
    return thin.buffer(-0.04, quad_segs=QUAD_SEGS).buffer(0.04, quad_segs=QUAD_SEGS)


def mean_stroke_mm(body) -> float:
    """Mean stroke width of a silhouette: 2·area / perimeter (exact for a
    long uniform band, a stable proxy for lettering)."""
    if body.is_empty or body.length == 0:
        return 0.0
    return 2.0 * body.area / body.length


def effective_stroke_delta(body, recipe: RecipeParams) -> float:
    """Buffer chosen from the face's own metal at this size, never eroding:
    - necks/hairlines thinner than the workshop minimum are lifted with a
      global buffer sized from the thinnest class present (probed with
      coarse openings), because a global lift keeps calligraphic
      modulation smooth where local patching lumps it;
    - a light face is additionally brought toward the fine-jewellery mean
      stroke target.
    The recipe's stroke_delta stays the upper bound. Erosion was tried and
    measured to open joins between letters (WEAK_BRIDGE), so a heavy face
    keeps its weight — lighter looks come from lighter font instances.
    """
    measured = mean_stroke_mm(body)
    if measured <= 0:
        return recipe.stroke_delta_mm
    thin = thin_parts(body, MIN_NECK_MM)
    lift = 0.0
    if thin.area > 0.02:
        thinnest = mean_stroke_mm(thin)
        for probe in (0.35, 0.5, 0.65):
            if thin_parts(body, probe).area > 0.02:
                thinnest = probe * 0.85
                break
        lift = (MIN_NECK_MM - thinnest) / 2.0 + 0.05
    target = max(MIN_TARGET_STROKE_MM, TARGET_STROKE_RATIO * recipe.target_height_mm)
    toward_target = (target - measured) / 2.0
    return round(max(0.0, min(recipe.stroke_delta_mm, max(lift, toward_target))), 3)


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
        # Solder fillets where the bridge lands (a bar meeting a curved tail
        # tangentially would otherwise leave a neck under the minimum).
        ends = unary_union([small, rest])
        fillet = _junction_fillet(bridge, ends, reach=bridge_width_mm * 0.7)
        geom = _as_multipolygon(unary_union([geom, bridge, fillet]))
        added += 1
    if added and fillet_mm > 0:
        # Closing fillet: smooths bridge junctions without moving strokes.
        geom = _as_multipolygon(
            geom.buffer(fillet_mm, quad_segs=QUAD_SEGS).buffer(-fillet_mm, quad_segs=QUAD_SEGS)
        )
    return geom, added


def normalise_dots(geom, text_height_mm: float):
    """Detached dot-sized parts become crisp circles of equal-or-minimum
    area at the same centroid (identity-preserving: the dot is still the
    source glyph's dot, only its outline is cleaned for metal)."""
    parts = list(_as_multipolygon(geom).geoms)
    if len(parts) <= 1:
        return geom
    max_area = max(p.area for p in parts)
    dot_limit_area = (0.22 * text_height_mm) ** 2
    out = []
    for p in parts:
        minx, miny, maxx, maxy = p.bounds
        size = max(maxx - minx, maxy - miny)
        if p.area < min(max_area * 0.2, dot_limit_area) and size < 0.3 * text_height_mm:
            r = max((p.area / 3.14159) ** 0.5, MIN_DOT_DIAMETER_MM / 2)
            out.append(Point(p.centroid).buffer(r, quad_segs=QUAD_SEGS * 2))
        else:
            out.append(p)
    return _as_multipolygon(unary_union(out))


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


def _extreme_vertex(geom, axis: int, sign: int, prefer_x: float | None = None) -> tuple[float, float]:
    """Vertex of the silhouette that is extreme along `axis` (0=x, 1=y) in
    direction `sign`; ties within 0.15 mm resolved toward `prefer_x`."""
    pts = []
    for poly in _as_multipolygon(geom).geoms:
        pts.extend(poly.exterior.coords)
    best = max(pts, key=lambda p: sign * p[axis])
    lim = sign * best[axis] - 0.15
    near = [p for p in pts if sign * p[axis] >= lim]
    if prefer_x is not None:
        return min(near, key=lambda p: abs(p[0] - prefer_x))
    return best


def attachment_ring_centers(geom, loops: str, r_out: float, wall: float) -> list[tuple[float, float]]:
    """Jump-ring centres that FUSE into the silhouette: the ring sits on the
    true extremity of the metal (top-most stroke, or the two ends of the
    name) and overlaps it by most of its wall — the way a real bail or
    chain ring is soldered — instead of floating beside the bounding box
    and being reached by a stalk."""
    minx, miny, maxx, maxy = geom.bounds
    overlap = wall * 0.85
    if loops == "top":
        # The bail hangs from the top of the CENTRAL band of the main body
        # (largest component) so the piece hangs level — never from a side
        # ascender, a dot or a detached mark. On a flat top (bar) the ring
        # sits at the centre of the bar.
        main = max(_as_multipolygon(geom).geoms, key=lambda p: p.area)
        cx = (minx + maxx) / 2
        band = box(cx - (maxx - minx) * 0.22, miny - 1, cx + (maxx - minx) * 0.22, maxy + 1)
        central = main.intersection(band)
        target = central if not central.is_empty else main
        inner_r = r_out - wall

        def _centre_for(part):
            top_y = part.bounds[3]
            cut = part.intersection(LineString([(minx - 1, top_y - 0.12), (maxx + 1, top_y - 0.12)]))
            if not cut.is_empty:
                segs = list(cut.geoms) if hasattr(cut, "geoms") else [cut]
                x = min(segs, key=lambda g: abs(g.centroid.x - cx)).centroid.x
            else:
                x, _ = _extreme_vertex(part, 1, +1, prefer_x=cx)
            return (x, top_y + r_out - overlap)

        def _hole_clear(c):
            # nothing but the attachment stroke may enter the chain hole
            return geom.distance(Point(c)) >= inner_r + 0.1 or geom.buffer(0).intersection(
                Point(c).buffer(inner_r + 0.1)).area < 0.05

        centre = _centre_for(target)
        if not _hole_clear(centre):
            centre = _centre_for(main)          # global top of the body
        while not _hole_clear(centre) and centre[1] < maxy + r_out:
            centre = (centre[0], centre[1] + 0.2)  # lift until the hole is free
        return [centre]
    # Chain rings sit on the true ends of the metal within the hanging band
    # (bar ends, or the first/last letter) — never beside empty space.
    lo, hi = miny + (maxy - miny) * 0.05, miny + (maxy - miny) * 0.75
    pts = [pt for poly in _as_multipolygon(geom).geoms for pt in poly.exterior.coords if lo <= pt[1] <= hi]
    if not pts:
        pts = [pt for poly in _as_multipolygon(geom).geoms for pt in poly.exterior.coords]
    lx, ly = min(pts, key=lambda p: p[0])
    rx, ry = max(pts, key=lambda p: p[0])
    return [(lx - r_out + overlap, ly), (rx + r_out - overlap, ry)]


def heal_pinches(geom, half_stroke: float, protect=None, max_piece_area: float = 0.06):
    """Heal pinch points: specks that survive erosion by `half_stroke` as
    separate tiny pieces are joined by a local closing (a solder fillet at
    that spot only). `protect` (e.g. chain holes) is never filled. Letters
    elsewhere are untouched."""
    geom = _as_multipolygon(geom)
    eroded = geom.buffer(-half_stroke, quad_segs=QUAD_SEGS)
    pieces = [g for g in getattr(eroded, "geoms", [eroded]) if not g.is_empty]
    if len(pieces) <= 1:
        return geom
    main_area = max(p.area for p in pieces)
    additions = []
    for p in pieces:
        if p.area >= main_area or p.area > max_piece_area:
            continue
        zone = p.buffer(half_stroke + 0.9, quad_segs=QUAD_SEGS)
        local = geom.intersection(zone)
        closed = local.buffer(0.6, quad_segs=QUAD_SEGS).buffer(-0.6, quad_segs=QUAD_SEGS).intersection(zone)
        if protect is not None:
            closed = closed.difference(protect)
        additions.append(closed)
    if not additions:
        return geom
    return _as_multipolygon(unary_union([geom] + additions))


def _junction_fillet(a, b, reach: float = JUNCTION_FILLET_MM):
    """Solid fillet where two parts meet or nearly meet: the region within
    `reach` of both. Turns a kiss between a letter and a frame wall into a
    soldered joint wider than the bridge minimum, like a real jeweller's
    solder fillet — never a spoke across empty space."""
    zone = a.buffer(reach, quad_segs=QUAD_SEGS).intersection(b.buffer(reach, quad_segs=QUAD_SEGS))
    return zone if not zone.is_empty else Polygon()


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
        # Thin bar fused into the letter bottoms; the classic name-necklace
        # construction. Its ends are where the chain rings sit.
        bar_t = max(ch * 0.8, 0.9)
        parts.append(box(minx - ch * 1.5, miny - bar_t * 0.45, maxx + ch * 1.5, miny + bar_t * 0.55))
    elif recipe.composition == "plate_oval":
        m = recipe.frame_margin_mm
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        plate = affinity.scale(Point(cx, cy).buffer(1, quad_segs=QUAD_SEGS * 4), xfact=w / 2 + m, yfact=h / 2 + m, origin=(cx, cy))
        parts.append(plate)
    elif recipe.composition == "plate_rect":
        # Tag plate with rounded corners (a sharp slab reads as a label).
        m = recipe.frame_margin_mm
        rad = min(0.25 * h, m + ch)
        plate = box(minx - m + rad, miny - m + rad, maxx + m - rad, maxy + m - rad).buffer(
            rad, quad_segs=QUAD_SEGS * 2
        )
        parts.append(plate)
    elif recipe.composition == "frame_circle":
        # The name is inscribed so its horizontal extremes fuse into the
        # ring wall — no spokes. A tall name touches top/bottom instead.
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        ring_t = max(ch, 1.1)          # medallion rings are heavier than strokes
        overlap = ring_t * 0.3         # letters kiss the inner wall, never pierce it
        far = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                  for poly in _as_multipolygon(body).geoms for x, y in poly.exterior.coords)
        r = max(far - overlap, h / 2 + recipe.frame_margin_mm * 0.5)
        ring = Point(cx, cy).buffer(r + ring_t, quad_segs=QUAD_SEGS * 4).difference(
            Point(cx, cy).buffer(r, quad_segs=QUAD_SEGS * 4)
        )
        parts.append(ring)
        parts.append(_junction_fillet(body, ring))
    elif recipe.composition == "frame_rect":
        # Open frame; the name's ends fuse into the side bars — no spokes.
        m = recipe.frame_margin_mm
        bar_t = max(ch * 0.8, 0.9)
        overlap = bar_t * 0.6
        rad = min(0.2 * h, m + bar_t)
        outer = box(minx + overlap - bar_t + rad, miny - m - bar_t + rad,
                    maxx - overlap + bar_t - rad, maxy + m + bar_t - rad).buffer(rad, quad_segs=QUAD_SEGS * 2)
        inner = box(minx + overlap + rad, miny - m + rad, maxx - overlap - rad, maxy + m - rad).buffer(
            rad, quad_segs=QUAD_SEGS * 2
        )
        frame = outer.difference(inner)
        parts.append(frame)
        parts.append(_junction_fillet(body, frame))
    elif recipe.composition == "top_bar":
        # Hanging bar above the text; letters suspend from it.
        parts.append(box(minx - ch, maxy - ch * 0.3, maxx + ch, maxy + ch))
    # "bare": text only; dots must be bridged.

    geom = _as_multipolygon(unary_union(parts))

    bridges = 0
    frame_center = None
    # Dots join their own letter straight up/down in every composition —
    # frames no longer need radial spokes because the name is inscribed
    # to fuse with the frame wall.
    bridge_style = "vertical"
    if recipe.dot_strategy == "bridge":
        geom = normalise_dots(geom, recipe.target_height_mm)
        geom, bridges = bridge_components(
            geom, bridge_width, style=bridge_style, frame_center=frame_center
        )

    # Fill counters below the cuttable gap size (before loops, so loop
    # holes are never affected).
    geom = fill_small_holes(geom, min_gap_eff)

    # Attachment loops go on last so they fuse with the final silhouette.
    loop_centers: list[tuple[float, float]] = []
    if recipe.loops != "none":
        r_out = loop_inner_d / 2 + loop_wall
        centers = attachment_ring_centers(geom, recipe.loops, r_out, loop_wall)
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
