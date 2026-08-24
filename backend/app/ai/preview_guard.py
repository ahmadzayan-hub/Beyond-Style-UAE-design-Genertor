"""Photoreal preview identity guard.

AI previews must never change the customer's design: before a generated
preview is shown, its silhouette is compared to the canonical vector
geometry. If divergence exceeds the threshold the preview is REJECTED
(regenerate or fall back to compositing the canonical SVG over the
generated background — the canonical lettering is never replaced).
Pure Pillow+shapely; works without any AI model, so it is fully testable.
"""
from __future__ import annotations

import io

from PIL import Image
from shapely import wkt as shapely_wkt

from .config import PREVIEW_IDENTITY_MAX_DIVERGENCE

GRID = 64


def geometry_occupancy(geometry_wkt: str) -> list[bool]:
    from shapely.geometry import Point
    from shapely.prepared import prep

    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    prepared = prep(geom)
    cells = []
    for j in range(GRID):
        cy = maxy - (j + 0.5) * h / GRID  # image row order (top-down)
        for i in range(GRID):
            cx = minx + (i + 0.5) * w / GRID
            cells.append(prepared.contains(Point(cx, cy)))
    return cells


def image_occupancy(image_bytes: bytes, threshold: int = 128, subject_darker: bool = True) -> list[bool]:
    """Foreground occupancy of a rendered preview (grayscale threshold on
    the design region, resized to the guard grid)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((GRID, GRID))
    px = list(img.getdata())
    return [(p < threshold) if subject_darker else (p >= threshold) for p in px]


def identity_divergence(geometry_wkt: str, image_bytes: bytes, subject_darker: bool = True) -> float:
    """1 − IoU between canonical silhouette and rendered silhouette."""
    a = geometry_occupancy(geometry_wkt)
    b = image_occupancy(image_bytes, subject_darker=subject_darker)
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    iou = inter / union if union else 0.0
    return 1.0 - iou


def check_preview(geometry_wkt: str, image_bytes: bytes, subject_darker: bool = True) -> dict:
    divergence = identity_divergence(geometry_wkt, image_bytes, subject_darker)
    return {
        "divergence": round(divergence, 4),
        "threshold": PREVIEW_IDENTITY_MAX_DIVERGENCE,
        "accepted": divergence <= PREVIEW_IDENTITY_MAX_DIVERGENCE,
        "action_if_rejected": "regenerate or composite canonical SVG over background",
    }
