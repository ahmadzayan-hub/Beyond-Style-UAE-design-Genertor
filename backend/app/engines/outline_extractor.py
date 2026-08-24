"""Glyph outline extraction: glyph id → flattened closed contours.

Outlines come from the font's glyf/CFF table via fontTools, flattened with a
fixed deterministic sampling so identical inputs always give identical
polygons. Output is in font units; mm scaling happens in the geometry engine.

An unclosed contour is reported, never silently closed with guesswork
(fontTools pens close contours explicitly via closePath; a missing
closePath marks the glyph as OPEN_PATH for the validator).
"""
from __future__ import annotations

from functools import lru_cache

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

CURVE_STEPS = 12  # fixed for determinism


@lru_cache(maxsize=8)
def _glyphset(font_path: str):
    tt = TTFont(font_path, lazy=True)
    return tt.getGlyphSet(), tt.getGlyphOrder()


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _quad_points(p0, p1, p2, steps=CURVE_STEPS):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        a = _lerp(p0, p1, t)
        b = _lerp(p1, p2, t)
        pts.append(_lerp(a, b, t))
    return pts


def _cubic_points(p0, p1, p2, p3, steps=CURVE_STEPS):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        a = _lerp(p0, p1, t)
        b = _lerp(p1, p2, t)
        c = _lerp(p2, p3, t)
        d = _lerp(a, b, t)
        e = _lerp(b, c, t)
        pts.append(_lerp(d, e, t))
    return pts


def extract_contours(font_path: str, glyph_id: int) -> tuple[list[list[tuple[float, float]]], list[str]]:
    """Return (closed_contours, issues). Each contour is a list of (x, y)
    points in font units. Issues lists structural problems (open paths)."""
    glyphset, order = _glyphset(font_path)
    if glyph_id >= len(order):
        return [], [f"glyph id {glyph_id} out of range"]
    glyph = glyphset[order[glyph_id]]
    pen = DecomposingRecordingPen(glyphset)
    glyph.draw(pen)

    contours: list[list[tuple[float, float]]] = []
    issues: list[str] = []
    current: list[tuple[float, float]] = []
    closed = True

    for op, args in pen.value:
        if op == "moveTo":
            if current:
                issues.append("open path: contour not closed before moveTo")
            current = [args[0]]
            closed = False
        elif op == "lineTo":
            current.append(args[0])
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:
                # All-off-curve TrueType contour: on-curve points are implied
                # midpoints between consecutive off-curve points.
                offs = pts[:-1]
                start = _lerp(offs[-1], offs[0], 0.5)
                current = [start]
                ring = offs + [offs[0]]
                p0 = start
                for j in range(len(ring) - 1):
                    mid = _lerp(ring[j], ring[j + 1], 0.5)
                    current.extend(_quad_points(p0, ring[j], mid))
                    p0 = mid
                closed = False
                continue
            p0 = current[-1]
            # Implied on-curve midpoints between consecutive off-curve points.
            offs, last = pts[:-1], pts[-1]
            for j, off in enumerate(offs):
                end = _lerp(off, offs[j + 1], 0.5) if j + 1 < len(offs) else last
                current.extend(_quad_points(p0, off, end))
                p0 = end
            if not offs:
                current.append(last)
        elif op == "curveTo":
            p0 = current[-1]
            pts = list(args)
            # May contain multiple cubic segments (PostScript style).
            for j in range(0, len(pts) - 2, 3):
                seg = _cubic_points(p0, pts[j], pts[j + 1], pts[j + 2])
                current.extend(seg)
                p0 = pts[j + 2]
        elif op == "closePath":
            if len(current) >= 3:
                contours.append(current)
            current = []
            closed = True
        elif op == "endPath":
            issues.append("open path: endPath without closePath")
            current = []

    if current and not closed:
        issues.append("open path: trailing unclosed contour")
    return contours, issues
