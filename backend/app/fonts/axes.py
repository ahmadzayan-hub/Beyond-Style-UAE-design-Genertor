"""Variable-axis design-space safety.

Measures what actually happens to the OUTLINES as a variable axis moves, by
instancing the font with fontTools and re-measuring real glyph geometry at
each grid point — stroke width, counter closure, negative space, island
count and bounding-box growth.

IMPORTANT LIMIT, stated up front: the shaping/outline path
(`app/engines/arabic_engine.py`, `outline_extractor.py`) loads each font at
its DEFAULT instance and has no axis plumbing. So the ranges computed here
are honest measurements of the design space, but the generator cannot yet
render a non-default weight. They are stored as `NOT_YET_REACHABLE_BY_
GENERATOR` and must not be advertised as selectable until that plumbing
exists.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

#: Arabic letters that between them exercise counters, dots, ascenders and
#: descenders — the shapes most at risk when a weight axis is pushed.
PROBE_CHARS = ["ع", "م", "ه", "ن", "و", "ر", "ب", "ط", "ص", "ك"]

#: Bounded representative grid, per the review brief.
GRID_FRACTIONS = [0.0, 0.25, 0.5, 0.75, 1.0]


def axis_grid(axis: dict) -> list[float]:
    """min / 25% / default / 75% / max, de-duplicated and ordered.

    The default is included explicitly because it is the only point the
    generator can currently render."""
    lo, hi, default = axis["min"], axis["max"], axis["default"]
    points = {round(lo + f * (hi - lo), 2) for f in GRID_FRACTIONS}
    points.add(round(default, 2))
    return sorted(points)


def _contour_metrics(pen_value: RecordingPen) -> tuple[int, int]:
    """(contour count, closed-contour count) from a recorded outline."""
    contours = sum(1 for op, _ in pen_value.value if op == "moveTo")
    closed = sum(1 for op, _ in pen_value.value if op == "closePath")
    return contours, closed


def measure_instance(font: TTFont, upem: int) -> dict:
    """Geometry of the probe glyphs at one instantiated axis position."""
    cmap = font.getBestCmap()
    glyphset = font.getGlyphSet()
    stroke_widths, fills, islands, areas, bboxes = [], [], [], [], []

    for ch in PROBE_CHARS:
        name = cmap.get(ord(ch))
        if name is None:
            continue
        rec = RecordingPen()
        glyphset[name].draw(rec)
        area_pen, bounds_pen = AreaPen(glyphset), BoundsPen(glyphset)
        glyphset[name].draw(area_pen)
        glyphset[name].draw(bounds_pen)
        if bounds_pen.bounds is None:
            continue
        x0, y0, x1, y1 = bounds_pen.bounds
        bbox_area = max((x1 - x0) * (y1 - y0), 1.0)
        area = abs(area_pen.value)
        contours, _ = _contour_metrics(rec)
        # Perimeter from the recorded points — enough for a stroke-width
        # proxy (2·area/perimeter is the width of an equivalent ribbon).
        pts = [p for op, args in rec.value for p in (args or []) if isinstance(p, tuple)]
        perim = sum(
            math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)
        ) or 1.0
        # RELATIVE stroke proxy only. Perimeter is summed over control
        # points, not true curve length, so the absolute value is not a
        # millimetre width — it is comparable ACROSS grid points of the
        # same glyph, which is all this is used for.
        stroke_widths.append(2 * area / perim / upem * 1000)
        fills.append(area / bbox_area)
        islands.append(contours)
        areas.append(area / (upem * upem))
        bboxes.append(bbox_area / (upem * upem))

    n = max(len(stroke_widths), 1)
    return {
        "probe_glyphs": len(stroke_widths),
        "stroke_proxy_mean": round(sum(stroke_widths) / n, 2),
        "stroke_proxy_min": round(min(stroke_widths), 2) if stroke_widths else 0.0,
        "stroke_proxy_note": "relative across grid points only; NOT a millimetre width",
        "mean_fill_ratio": round(sum(fills) / n, 4),
        "negative_space": round(1 - sum(fills) / n, 4),
        "mean_contours": round(sum(islands) / n, 2),
        "max_contours": max(islands) if islands else 0,
        "mean_bbox_area": round(sum(bboxes) / n, 5),
    }


def sweep_axis(font_path: Path, axis: dict) -> list[dict]:
    """Instance the font at each grid point and measure. Real instancing —
    no interpolation of the metrics themselves."""
    out = []
    for value in axis_grid(axis):
        base = TTFont(font_path)
        inst = instancer.instantiateVariableFont(base, {axis["tag"]: value}, inplace=False)
        buf = io.BytesIO()
        inst.save(buf)
        buf.seek(0)
        static = TTFont(buf)
        upem = static["head"].unitsPerEm
        metrics = measure_instance(static, upem)
        metrics.update(axis=axis["tag"], value=value,
                       is_default=abs(value - axis["default"]) < 1e-6)
        out.append(metrics)
    return out


#: A grid point is unsafe when the letters start closing up: counters
#: filling in (fill ratio climbing past this) is what destroys readability
#: and creates unmanufacturable pinch points at small sizes.
FILL_CEILING = {"small": 0.42, "normal": 0.52}
#: How far the relative stroke proxy may fall below the default instance
#: before the letters are judged too thin for this design space. Relative,
#: because the proxy has no absolute millimetre meaning — the real stroke
#: gate is the manufacturing validator on built geometry.
MAX_STROKE_THINNING = 0.15


def classify_grid(sweep: list[dict], small_size: bool) -> list[dict]:
    """Mark each grid point safe/unsafe against the geometric limits, with
    the reason recorded rather than a bare boolean."""
    ceiling = FILL_CEILING["small" if small_size else "normal"]
    default_point = next((p for p in sweep if p["is_default"]), None)
    default_contours = default_point["mean_contours"] if default_point else None
    default_stroke = default_point["stroke_proxy_min"] if default_point else None
    out = []
    for point in sweep:
        reasons = []
        if point["mean_fill_ratio"] > ceiling:
            reasons.append(f"counters closing (fill {point['mean_fill_ratio']} > {ceiling})")
        if default_stroke and point["stroke_proxy_min"] < default_stroke * (1 - MAX_STROKE_THINNING):
            thinning = 1 - point["stroke_proxy_min"] / default_stroke
            reasons.append(f"strokes {thinning:.0%} thinner than the default instance")
        if default_contours is not None and point["mean_contours"] > default_contours + 0.5:
            reasons.append("new islands appear versus the default instance")
        out.append({**point, "safe": not reasons, "reasons": reasons})
    return out


def safe_range(classified: list[dict]) -> dict:
    """The widest CONTIGUOUS safe span containing the default instance —
    a safe island unreachable from the default is not a usable range."""
    safe_points = [p for p in classified if p["safe"]]
    if not safe_points:
        return {"min": None, "max": None, "status": "NO_SAFE_RANGE"}
    values = [p["value"] for p in classified]
    safe_flags = {p["value"]: p["safe"] for p in classified}
    default = next((p["value"] for p in classified if p["is_default"]), values[0])
    if not safe_flags.get(default):
        return {"min": None, "max": None, "status": "DEFAULT_INSTANCE_UNSAFE"}
    lo = hi = default
    for v in sorted(values):
        if v <= default and safe_flags[v]:
            lo = min(lo, v)
        elif v <= default:
            lo = default
    for v in sorted(values, reverse=True):
        if v >= default and safe_flags[v]:
            hi = max(hi, v)
        elif v >= default:
            hi = default
    return {"min": lo, "max": hi, "status": "MEASURED"}
