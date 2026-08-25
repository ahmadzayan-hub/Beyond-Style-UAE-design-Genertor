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
    if w <= 0 or h <= 0:
        return [False] * (GRID * GRID)
    prepared = prep(geom)
    cells = []
    for j in range(GRID):
        cy = maxy - (j + 0.5) * h / GRID  # image row order (top-down)
        for i in range(GRID):
            cx = minx + (i + 0.5) * w / GRID
            cells.append(prepared.contains(Point(cx, cy)))
    return cells


def image_occupancy(image_bytes: bytes, threshold: int = 128, subject_darker: bool = True) -> list[bool]:
    """Foreground occupancy of a rendered preview.

    Alpha-aware (transparent pixels are background), then cropped to the
    subject's bounding box before sampling, so the comparison is
    invariant to framing/padding — a photoreal render places the piece
    inside a scene, while the canonical grid covers the geometry bbox.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        alpha = rgba.getchannel("A")
        gray = rgba.convert("L")
        opaque = [a > 32 for a in alpha.getdata()]
        lum = list(gray.getdata())
        mask = [
            op and ((v < threshold) if subject_darker else (v >= threshold))
            for op, v in zip(opaque, lum)
        ]
        # A fully transparent background means alpha alone marks the subject.
        if not any(mask) and any(opaque):
            mask = opaque
        mask_img = Image.new("L", img.size)
        mask_img.putdata([255 if v else 0 for v in mask])
    else:
        gray = img.convert("L")
        mask_img = Image.new("L", img.size)
        mask_img.putdata([
            255 if ((v < threshold) if subject_darker else (v >= threshold)) else 0
            for v in gray.getdata()
        ])
    bbox = mask_img.getbbox()
    if bbox is None:
        return [False] * (GRID * GRID)
    sampled = mask_img.crop(bbox).resize((GRID, GRID), Image.BILINEAR)
    return [v >= 128 for v in sampled.getdata()]


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
