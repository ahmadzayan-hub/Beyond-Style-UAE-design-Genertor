"""Vector Composition Engine — ARTISTIC COMPOSITION SECOND.

Multi-name / multi-word jewellery compositions built from the SAME
validated glyph vectors: each name is shaped once (HarfBuzz) and outlined
once; every variant only moves, rotates, scales groups of those vectors,
lets them touch/interlock, welds them and adds safe bridges and real
attachment rings. No glyph is ever redrawn; the identity proof covers the
whole source text through per-name index offsets.

Layouts (deterministic, seedable):
  interwoven_stack   rows with alternating offsets, descenders nested into
                     the row below (negative leading where no collision)
  arch               names along an upper arc, rotated tangentially
  circular           names around a ring, upright at the top, tangential
  radial             names radiating from a welded central hub
  cluster            greedy packing — each name placed to touch the cluster
                     with a small rotation (free/asymmetric composition)
  family_tree        first name largest on top, others staggered below,
                     joined by baseline extensions
  oval               cluster fitted to an elliptical silhouette
  horizontal_flow    one flowing line with alternating baselines (bracelet)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from ..schemas.jewellery_design import RecipeParams, ShapedRun, TextIdentityProof
from .arabic_engine import _offset_runs, normalize, shape_text, verify_identity
from .geometry_engine import (
    JUNCTION_FILLET_MM, MIN_NECK_MM, QUAD_SEGS, BuiltGeometry, _as_multipolygon, _junction_fillet,
    bridge_components, build_text_body, fill_small_holes, heal_pinches, normalise_dots, _loop_ring,
    mean_stroke_mm, thin_parts,
)


def _lift_hairlines(geom, min_w: float):
    """Lift only the necks/hairlines thinner than `min_w` (same morphology
    as the single-text engine), leaving every other stroke untouched."""
    thin = thin_parts(geom, min_w)
    if thin.is_empty or thin.area < 1e-3:
        return geom
    grow = max(0.0, (min_w - mean_stroke_mm(thin)) / 2 + 0.03)
    if grow <= 0:
        return geom
    return _as_multipolygon(unary_union([geom, thin.buffer(grow, quad_segs=QUAD_SEGS)]))


def _weld(parts: list) -> MultiPolygon:
    """Union of placed parts plus solder fillets wherever two parts touch or
    nearly touch — a kiss becomes a joint wider than the bridge minimum."""
    fillets = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            if parts[i].distance(parts[j]) < JUNCTION_FILLET_MM:
                fillets.append(_junction_fillet(parts[i], parts[j], reach=0.7))
    return _as_multipolygon(unary_union(parts + [f for f in fillets if not f.is_empty]))

#: Customer-facing layouts. `cluster` (free packing) exists but is not
#: presentable yet — it stays out of the set rather than shipping a blob.
LAYOUTS = ["interwoven_stack", "family_tree", "oval", "arch", "circular", "horizontal_flow"]
#: Reinforced bridge width for multi-name pieces (spec §14: 1.2–1.5 mm in
#: critical bridges).
REINFORCED_BRIDGE_MM = 1.2
MAX_ROTATION_DEG = 25.0


def split_names(text: str) -> list[str]:
    parts = [p.strip() for p in normalize(text).replace("\r", "").split("\n")]
    names = [p for p in parts if p]
    if len(names) <= 1:
        names = [w for w in normalize(text).split() if w]
    return names


def is_multi_name(text: str) -> bool:
    n = normalize(text)
    return ("\n" in n.strip() and len(split_names(n)) >= 2) or len(n.split()) >= 3


@dataclass
class Word:
    index: int
    text: str
    source_offset: int
    runs: list[ShapedRun]
    body: Polygon | MultiPolygon           # outlined at base height, origin at 0,0
    issues: list[str] = field(default_factory=list)


@dataclass
class Composition:
    layout: str
    variant: int
    geometry: MultiPolygon
    text_geometry: MultiPolygon
    words_placed: list[dict]
    bridges: int
    loop_centers: list[tuple[float, float]]
    fitted_scale: float
    issues: list[str]


def shape_words(text: str, font_id: str, recipe: RecipeParams, features=None) -> tuple[list[Word], TextIdentityProof]:
    """Shape and outline every name once; prove identity over the whole text."""
    normalized = normalize(text)
    names = split_names(normalized)
    words: list[Word] = []
    covered: set[int] = set()
    notdef = 0
    cursor = 0
    for i, name in enumerate(names):
        offset = normalized.index(name, cursor)
        runs = shape_text(name, font_id, features)
        proof = verify_identity(name, runs)
        notdef += proof.notdef_glyph_count
        covered.update(offset + k for k in proof.covered_codepoint_indices)
        body, issues = build_text_body(runs, recipe)
        words.append(Word(i, name, offset, _offset_runs(runs, offset), body, issues))
        cursor = offset + len(name)
    # separators (newlines/spaces) are layout, covered by the structure
    for k, ch in enumerate(normalized):
        if ch.isspace():
            covered.add(k)
    uncovered = [k for k in range(len(normalized)) if k not in covered]
    proof = TextIdentityProof(
        verified=not uncovered and notdef == 0 and bool(names),
        covered_codepoint_indices=sorted(covered), uncovered_codepoint_indices=uncovered,
        notdef_glyph_count=notdef, detail="ok" if not uncovered and notdef == 0 else f"uncovered={uncovered[:20]} notdef={notdef}",
    )
    return words, proof


# ------------------------------------------------------------- placement

def _place(body, x: float, y: float, angle: float = 0.0, scale: float = 1.0):
    g = body
    if scale != 1.0:
        g = affinity.scale(g, xfact=scale, yfact=scale, origin=(0, 0))
    if angle:
        g = affinity.rotate(g, angle, origin="centroid")
    minx, miny, maxx, maxy = g.bounds
    return affinity.translate(g, xoff=x - (minx + maxx) / 2, yoff=y - (miny + maxy) / 2)


def _touch(moving, cluster, direction: tuple[float, float], overlap: float, max_step: float = 60.0):
    """Slide `moving` along `direction` until it overlaps `cluster` by
    ~`overlap` mm (welded touch), never more than max_step."""
    dx, dy = direction
    norm = math.hypot(dx, dy) or 1.0
    dx, dy = dx / norm, dy / norm
    lo, hi = 0.0, max_step
    # ensure hi is far enough to be free
    for _ in range(24):
        mid = (lo + hi) / 2
        cand = affinity.translate(moving, xoff=dx * mid, yoff=dy * mid)
        d = cand.distance(cluster)
        if d > 0:
            hi = mid
        else:
            lo = mid
    # lo touches; back off by (−overlap) so they overlap slightly
    t = max(0.0, lo - overlap)
    return affinity.translate(moving, xoff=dx * t, yoff=dy * t)


def _hierarchy(words: list[Word], variant: int) -> list[float]:
    n = len(words)
    if variant % 3 == 0:
        return [1.0] * n
    if variant % 3 == 1:
        return [1.22 if i == 0 else 1.0 for i in range(n)]      # first name leads
    return [1.15 if i in (0, n // 2) else 0.95 for i in range(n)]  # two anchors


def _rows_of(n: int, variant: int, target_aspect: float = 1.5) -> list[int]:
    """Row plan for n names: candidates like 2-3-2, 3-4, 1-3-3 …; the plan
    whose block aspect (≈ names-per-row × 1.4 : rows) is nearest the
    envelope aspect wins, with the variant cycling through the runners-up."""
    plans = {
        2: [[2], [1, 1]], 3: [[2, 1], [1, 2], [3]], 4: [[2, 2], [1, 2, 1], [3, 1]],
        5: [[2, 3], [3, 2], [1, 3, 1], [2, 1, 2]], 6: [[3, 3], [2, 2, 2], [2, 3, 1], [1, 2, 3]],
        7: [[2, 3, 2], [3, 4], [4, 3], [1, 3, 3], [2, 2, 3], [3, 2, 2]],
        8: [[3, 2, 3], [4, 4], [2, 4, 2], [2, 3, 3]],
    }
    options = plans.get(n) or [[max(2, round(n / 3))] * 3]
    for plan in options:
        while sum(plan) < n:
            plan[-1] += 1
        while sum(plan) > n:
            plan[-1] -= 1
    ranked = sorted(options, key=lambda pl: abs((max(pl) * 1.45) / len(pl) - target_aspect))
    return [r for r in ranked[variant % len(ranked)] if r > 0]


def _rows_for_words(words, scales, variant: int, stroke: float, target_aspect: float) -> list[int]:
    """Row plan measured with the real name widths/heights: the plan whose
    block aspect is nearest the envelope aspect fills the piece instead of
    leaving a wide, shallow strip."""
    n = len(words)
    plans = {
        2: [[2], [1, 1]], 3: [[2, 1], [1, 2], [3]], 4: [[2, 2], [1, 2, 1], [3, 1], [1, 3]],
        5: [[2, 3], [3, 2], [1, 3, 1], [2, 1, 2], [1, 2, 2]], 6: [[3, 3], [2, 2, 2], [2, 3, 1], [1, 2, 3], [1, 3, 2]],
        7: [[2, 3, 2], [3, 4], [4, 3], [1, 3, 3], [2, 2, 3], [3, 2, 2], [1, 2, 2, 2], [2, 2, 2, 1]],
        8: [[3, 2, 3], [4, 4], [2, 4, 2], [2, 3, 3], [2, 2, 2, 2]],
    }
    options = plans.get(n) or [[max(2, round(n / 3))] * 3]
    widths = [(w.body.bounds[2] - w.body.bounds[0]) * scales[i] for i, w in enumerate(words)]
    heights = [(w.body.bounds[3] - w.body.bounds[1]) * scales[i] for i, w in enumerate(words)]
    gap = stroke * 2.2

    def aspect(plan):
        idx = 0
        row_w = []
        for count in plan:
            row_w.append(sum(widths[idx: idx + count]) + gap * (count - 1))
            idx += count
        block_w = max(row_w)
        block_h = sum(heights) / n * len(plan) * 0.82
        return block_w / max(block_h, 1e-6)

    ranked = sorted(options, key=lambda pl: abs(aspect(pl) - target_aspect))
    return list(ranked[variant % min(len(ranked), 3)])


def _branch(x0: float, x1: float, y: float, width: float, sag: float = 0.0, extend: float = 1.2):
    """A calligraphic branch: shallow arc (sagitta `sag`) with round ends,
    the connective metal behind a row of names."""
    pts = []
    n = 16
    for k in range(n + 1):
        t = k / n
        x = (x0 - extend) + t * ((x1 + extend) - (x0 - extend))
        pts.append((x, y + sag * (1 - (2 * t - 1) ** 2)))
    return LineString(pts).buffer(width / 2, cap_style="round", quad_segs=QUAD_SEGS)


def _row_layout(words, variant, stroke, tilt_deg=0.0, arc_r=None, branches=True, target_aspect=1.5):
    """Names upright (or gently tilted) in rows on calligraphic branches;
    rows nested with a small clearance so descenders reach into the row
    below without pinching — connectivity comes from the branches and
    reinforced bridges, never from a kiss between two letter tips."""
    scales = _hierarchy(words, variant)
    plan = _rows_for_words(words, scales, variant, stroke, target_aspect)
    placed_rows: list = []
    extras: list = []
    idx = 0
    y = 0.0
    branch_w = max(0.9, stroke * 0.85)
    for r_i, count in enumerate(plan):
        row = []
        widths = []
        for k in range(count):
            w = words[idx + k]
            g = _place(w.body, 0, 0, 0, scales[idx + k])
            row.append(g); widths.append(g.bounds[2] - g.bounds[0])
        gap = stroke * 2.2
        total = sum(widths) + gap * (count - 1)
        x = -total / 2 + ((r_i % 2) * 2 - 1) * (variant % 2) * 3.0
        placed = []
        for k, g in enumerate(row):
            gx = x + widths[k] / 2
            tilt = tilt_deg * (1 if k % 2 == 0 else -1) * (1 if r_i % 2 == 0 else -1)
            if arc_r:
                theta = gx / arc_r
                gy = y - arc_r * (1 - math.cos(theta))
                tilt = max(-MAX_ROTATION_DEG, min(MAX_ROTATION_DEG, -math.degrees(theta)))
            else:
                gy = y
            g2 = _place(g, gx, gy - (g.bounds[3] - g.bounds[1]) / 2, tilt, 1.0)
            placed.append(g2)
            x += widths[k] + gap
        row_union = unary_union(placed)
        if placed_rows:
            above = unary_union(placed_rows)
            # nest: bring the row up until clearance is ~0.6 mm (no pinch)
            row_union2 = affinity.translate(row_union, yoff=-3.0)
            row_union2 = _touch(row_union2, above, (0, 1), 0.6)   # stop 0.6 mm short of contact
            dy = row_union2.bounds[3] - row_union.bounds[3]
            placed = [affinity.translate(g, yoff=dy) for g in placed]
            row_union = unary_union(placed)
        if branches:
            rminx, rminy, rmaxx, rmaxy = row_union.bounds
            # branch through the lower third of the letters (the baseline
            # zone), curved with the arc when the row is arched
            by = rminy + (rmaxy - rminy) * 0.30
            sag = -(rmaxx - rminx) ** 2 / (8 * arc_r) if arc_r else (0.9 if variant % 2 else -0.9)
            extras.append(_branch(rminx, rmaxx, by, branch_w, sag=sag))
        placed_rows.extend(placed)
        y = unary_union(placed_rows).bounds[1] - 0.8
        idx += count
    return placed_rows + extras


def layout_interwoven_stack(words, variant, stroke):
    return _row_layout(words, variant, stroke, tilt_deg=0.0)


def layout_arch(words, variant, stroke):
    return _row_layout(words, variant, stroke, arc_r=38.0 + 6 * (variant % 3))


def layout_circular(words, variant, stroke):
    """Wreath: upright names sitting ON a thin ring, the first name at the
    top; readable from one direction, joined by the ring itself."""
    n = len(words)
    scales = _hierarchy(words, variant)
    sizes = [(w.body.bounds[2] - w.body.bounds[0]) * scales[i] for i, w in enumerate(words)]
    r = max(sum(sizes) / (2 * math.pi) * 1.05, 11.0)
    placed = []
    for i, w in enumerate(words):
        ang = math.pi / 2 - i * (2 * math.pi / n) + (0.18 if variant % 2 else 0.0)
        placed.append(_place(w.body, r * math.cos(ang), r * math.sin(ang), 0, scales[i]))
    ring_t = max(stroke * 0.85, 0.9)
    ring = Point(0, 0).buffer(r + ring_t / 2, quad_segs=QUAD_SEGS * 4).difference(
        Point(0, 0).buffer(r - ring_t / 2, quad_segs=QUAD_SEGS * 4))
    return placed + [ring]


def layout_cluster(words, variant, stroke, envelope=(60.0, 40.0)):
    scales = _hierarchy(words, variant)
    order = sorted(range(len(words)), key=lambda i: -(words[i].body.area * scales[i]))
    first = order[0]
    placed = {first: _place(words[first].body, 0, 0, 0, scales[first])}
    cluster = placed[first]
    simple = cluster.simplify(0.08)
    dirs = [(1, 0.25), (-1, 0.25), (1, -0.25), (-1, -0.25), (0.2, 1), (-0.2, 1), (0.2, -1), (-0.2, -1)]
    for k, i in enumerate(order[1:]):
        rot = ((-1) ** k) * (3 + 3 * ((k + variant) % 3))   # gentle tilt, always readable
        g = _place(words[i].body, 0, 0, rot, scales[i])
        best = None
        start = (k * 3 + variant) % len(dirs)
        for d in dirs[start:] + dirs[:start]:
            far = affinity.translate(g, xoff=d[0] * 70, yoff=d[1] * 70)
            cand = _touch(far, simple, (-d[0], -d[1]), stroke * 1.3)
            minx = min(cluster.bounds[0], cand.bounds[0]); maxx = max(cluster.bounds[2], cand.bounds[2])
            miny = min(cluster.bounds[1], cand.bounds[1]); maxy = max(cluster.bounds[3], cand.bounds[3])
            w, h = maxx - minx, maxy - miny
            score = abs((w / max(h, 1e-6)) - envelope[0] / envelope[1]) * 2 + (w * h) / 700.0
            if best is None or score < best[0]:
                best = (score, cand)
        placed[i] = best[1]
        cluster = unary_union(list(placed.values()))
        simple = cluster.simplify(0.08)
    return [placed[i] for i in range(len(words))]


def layout_family_tree(words, variant, stroke):
    n = len(words)
    placed = [_place(words[0].body, 0, 0, 0, 1.3)]
    rest = words[1:]
    rows = [rest[: (len(rest) + 1) // 2], rest[(len(rest) + 1) // 2:]]
    y = placed[0].bounds[1] - 1.5
    branch_w = max(0.9, stroke * 0.85)
    for r_i, row in enumerate(rows):
        if not row:
            continue
        widths = [w.body.bounds[2] - w.body.bounds[0] for w in row]
        gap = stroke * 2.4
        total = sum(widths) + gap * (len(row) - 1)
        x = -total / 2 + (r_i * 3.0 if variant % 2 else -r_i * 3.0)
        row_h = 0
        for w, wd in zip(row, widths):
            g = _place(w.body, x + wd / 2, y - (w.body.bounds[3] - w.body.bounds[1]) / 2, 0, 1.0)
            placed.append(g)
            x += wd + gap
            row_h = max(row_h, g.bounds[3] - g.bounds[1])
        y -= row_h + 1.2
    # curved branches through each row's baseline zone + a slim trunk
    extras = []
    rows_geo = [placed[0]] + [unary_union(placed[1:1 + len(rows[0])])] + ([unary_union(placed[1 + len(rows[0]):])] if rows[1] else [])
    for k, rg in enumerate(rows_geo):
        minx, miny, maxx, maxy = rg.bounds
        extras.append(_branch(minx, maxx, miny + (maxy - miny) * 0.3, branch_w, sag=(-1.2 if k % 2 else 1.2)))
    top = placed[0].bounds[1] + (placed[0].bounds[3] - placed[0].bounds[1]) * 0.3
    bottom = min(p.bounds[1] for p in placed) + 1.0
    extras.append(LineString([(0.0, top), (0.0, bottom)]).buffer(branch_w / 2, cap_style="round", quad_segs=QUAD_SEGS))
    return placed + extras


def layout_oval(words, variant, stroke):
    placed = _row_layout(words, variant, stroke, tilt_deg=0.0, target_aspect=1.45)
    u = unary_union(placed)
    minx, miny, maxx, maxy = u.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    a, b = (maxx - minx) / 2 + stroke * 0.4, (maxy - miny) / 2 + stroke * 0.9
    ring_t = max(stroke * 0.9, 1.0)
    outer = affinity.scale(Point(cx, cy).buffer(1, quad_segs=QUAD_SEGS * 4), a + ring_t, b + ring_t, origin=(cx, cy))
    inner = affinity.scale(Point(cx, cy).buffer(1, quad_segs=QUAD_SEGS * 4), a, b, origin=(cx, cy))
    return placed + [outer.difference(inner)]


def layout_horizontal_flow(words, variant, stroke):
    placed = []
    x = 0.0
    prev = None
    for i, w in enumerate(words):
        g = _place(w.body, 0, 0, 0, 1.0)
        minx, miny, maxx, maxy = g.bounds
        dy = ((-1) ** i) * (maxy - miny) * 0.28
        g = affinity.translate(g, xoff=x - minx, yoff=dy)
        if prev is not None:
            g = _touch(affinity.translate(g, xoff=8.0), prev, (-1, 0), stroke * 0.9)
        placed.append(g)
        prev = unary_union(placed)
        x = g.bounds[2]
    return placed


LAYOUT_FN = {
    "interwoven_stack": layout_interwoven_stack, "arch": layout_arch, "circular": layout_circular,
    "cluster": layout_cluster, "family_tree": layout_family_tree,
    "oval": layout_oval, "horizontal_flow": layout_horizontal_flow,
}


# ------------------------------------------------------------- assembly

def upper_attachment_centers(geom, r_out: float, wall: float, inner_d: float | None = None) -> list[tuple[float, float]]:
    """Two discreet rings on the upper-left and upper-right metal: the
    extreme x points within the top 35 % band. Each ring is walked outward
    along the diagonal until its chain hole is clear of every letter while
    its wall still overlaps the metal (soldered) — never a hole cut through
    a name, never a ring floating beside it."""
    minx, miny, maxx, maxy = geom.bounds
    band_lo = maxy - (maxy - miny) * 0.35
    pts = [pt for poly in _as_multipolygon(geom).geoms for pt in poly.exterior.coords if pt[1] >= band_lo]
    if not pts:
        pts = [pt for poly in _as_multipolygon(geom).geoms for pt in poly.exterior.coords]
    lx, ly = min(pts, key=lambda p: p[0])
    rx, ry = max(pts, key=lambda p: p[0])
    overlap = wall * 0.85
    hole_r = (inner_d / 2 if inner_d else r_out - wall) + 0.12
    out = []
    for (px, py), sx in (((lx, ly), -1), ((rx, ry), +1)):
        d = (r_out - overlap) / math.sqrt(2)
        centre = (px + sx * d, py + d)
        for _ in range(30):
            hole = Point(centre).buffer(hole_r, quad_segs=QUAD_SEGS * 2)
            if hole.distance(geom) >= 0.05:
                break
            d += 0.12
            centre = (px + sx * d, py + d)
        out.append(centre)
    return out


def compose_multi_name(text: str, recipe: RecipeParams, rules, *, layout: str, variant: int,
                       envelope_mm: tuple[float, float] = (60.0, 40.0),
                       attachments: str = "upper_left_right") -> tuple[list[ShapedRun], TextIdentityProof, BuiltGeometry, dict]:
    words, proof = shape_words(text, recipe.font_id, recipe)
    stroke = max(mean_stroke_mm(unary_union([w.body for w in words])), 0.8)
    placed = LAYOUT_FN[layout](words, variant, stroke)
    word_polys = placed[: len(words)]
    extras = placed[len(words):]
    text_geom = _as_multipolygon(unary_union(word_polys))
    geom = _weld(word_polys + extras)

    # Fit the composition (plus attachment allowance) into the envelope —
    # uniform scale only, applied to already-outlined vectors.
    r_out = rules.loop_inner_diameter_mm / 2 + rules.loop_wall_mm
    allow_w = 2 * (2 * r_out - rules.loop_wall_mm * 0.85) if attachments != "none" else 0.0
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    s = min((envelope_mm[0] - allow_w) / w, (envelope_mm[1] - r_out) / h, 1.8)
    if abs(s - 1.0) > 1e-6:
        geom = affinity.scale(geom, xfact=s, yfact=s, origin=(0, 0))
        text_geom = affinity.scale(text_geom, xfact=s, yfact=s, origin=(0, 0))
    minx, miny, _, _ = geom.bounds
    geom = affinity.translate(geom, xoff=-minx, yoff=-miny)
    text_geom = affinity.translate(text_geom, xoff=-minx, yoff=-miny)

    bridge_w = max(rules.min_bridge_mm, REINFORCED_BRIDGE_MM)
    geom = normalise_dots(_as_multipolygon(geom), recipe.target_height_mm * s)
    geom, bridges = bridge_components(geom, bridge_w, style="vertical")
    # Lift any hairline neck to the reinforced minimum — local, never a
    # global fattening (spec §14: local reinforcement in critical bridges).
    geom = _lift_hairlines(geom, max(MIN_NECK_MM, 0.95))
    geom = heal_pinches(geom, rules.effective_min_stroke_mm / 2)
    geom = fill_small_holes(geom, rules.effective_min_gap_mm)

    loop_centers: list[tuple[float, float]] = []
    if attachments == "upper_left_right":
        for c in upper_attachment_centers(geom, r_out, rules.loop_wall_mm, rules.loop_inner_diameter_mm):
            ring = _loop_ring(c, rules.loop_inner_diameter_mm, rules.loop_wall_mm)
            hole = Point(c).buffer(rules.loop_inner_diameter_mm / 2 + 0.05, quad_segs=QUAD_SEGS * 2)
            fillet = _junction_fillet(geom, ring, reach=0.8).difference(hole)
            geom = _as_multipolygon(unary_union([geom, ring, fillet]))
            loop_centers.append(c)
        # Bridges only (no hairline pass after the rings: their 0.9 mm wall
        # must never be dilated into the chain hole). Pinch healing protects
        # the chain holes explicitly.
        geom, extra = bridge_components(geom, bridge_w, style="nearest")
        bridges += extra
        holes = unary_union([Point(c).buffer(rules.loop_inner_diameter_mm / 2 + 0.05, quad_segs=QUAD_SEGS * 2) for c in loop_centers])
        geom = heal_pinches(geom, rules.effective_min_stroke_mm / 2, protect=holes)
        geom = fill_small_holes(geom, rules.effective_min_gap_mm)
    geom = _as_multipolygon(geom.buffer(0))
    built = BuiltGeometry(geometry=geom, text_geometry=_as_multipolygon(text_geom),
                          outline_issues=[i for wd in words for i in wd.issues],
                          bridges_added=bridges, loop_centers_mm=loop_centers)
    runs = [r for wd in words for r in wd.runs]
    meta = {"layout": layout, "variant": variant, "names": [wd.text for wd in words],
            "fitted_scale": round(s, 4), "bridge_width_mm": bridge_w, "attachments": attachments,
            "envelope_mm": list(envelope_mm)}
    return runs, proof, built, meta


def variant_plan(count: int = 10) -> list[tuple[str, int]]:
    """6–12 variants across layouts, deterministic order."""
    plan = []
    v = 0
    while len(plan) < max(6, min(12, count)):
        for layout in LAYOUTS:
            plan.append((layout, v))
            if len(plan) >= max(6, min(12, count)):
                break
        v += 1
    return plan


#: Faces used for multi-name pieces when the customer named no script:
#: one per script family, all rights-cleared and sweep-validated.
DEFAULT_MULTI_NAME_FONTS = ["katibeh", "amiri-regular", "scheherazade-new", "reem-kufi", "cairo", "aref-ruqaa"]


def multi_name_recipes(hints: dict | None, count_per_font: int = 8) -> list[RecipeParams]:
    """Recipe set for a multi-name text: chosen faces × layout variants.
    The customer's script choice narrows the faces; the envelope comes
    from the brief (default 60×40 mm, spec §14)."""
    from ..fonts.capabilities import recipes_for_script, resolve_script_request

    hints = hints or {}
    fonts: list[str] = []
    fam = hints.get("script_family")
    if fam:
        res = resolve_script_request(fam)
        fonts = list(res.get("fonts") or ([res["recommended_font_id"]] if res.get("recommended_font_id") else []))
        fonts = fonts[:3]
        for extra in DEFAULT_MULTI_NAME_FONTS:
            if len(fonts) >= 3:
                break
            if extra not in fonts:
                fonts.append(extra)
    if not fonts:
        fonts = DEFAULT_MULTI_NAME_FONTS[:4]
    envelope = tuple(hints.get("envelope_mm") or (60.0, 40.0))
    attachments = hints.get("attachments") or "upper_left_right"
    out = []
    for font_id in fonts:
        for layout, variant in variant_plan(count_per_font):
            out.append(RecipeParams(
                recipe_id=f"mn.{font_id}.{layout}.v{variant}", name=f"{layout.replace('_', ' ')} · {font_id}",
                font_id=font_id, composition="multi_name", stroke_delta_mm=0.25, dot_strategy="bridge",
                loops=attachments, target_height_mm=11.0,
                multi_name={"layout": layout, "variant": variant, "envelope_mm": list(envelope)},
                dna={"family": f"multi-name-{layout}", "visual_purpose": f"{layout} multi-name composition",
                     "products": ["pendant", "necklace", "brooch"], "rights": "BEYOND_STYLE_ORIGINAL_PARAMETRIC",
                     "curation": "ENGINE"},
            ))
    return out
