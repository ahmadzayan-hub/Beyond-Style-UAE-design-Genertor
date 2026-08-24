"""Perceptual similarity between candidate geometries.

Deterministic occupancy-grid comparison: each design silhouette is
normalized to its bounding box and sampled on a fixed grid; similarity is
the IoU of occupied cells. This is a *comparison aid only* — grids/hashes
never become design truth (the canonical vector geometry is untouched).

Used before Top-10 selection so near-duplicates cannot coexist in the
final customer proofs.
"""
from __future__ import annotations

from shapely import wkt as shapely_wkt
from shapely.prepared import prep

GRID = 32  # fixed for determinism
#: IoU above this = perceptual near-duplicate (empirically: same recipe
#: with only stroke/spacing tweaks lands 0.90+; different compositions
#: land well below 0.80).
NEAR_DUP_IOU = 0.86


def occupancy_grid(geom) -> list[bool]:
    """Sample the geometry on a GRID×GRID lattice over its bbox."""
    if isinstance(geom, str):
        geom = shapely_wkt.loads(geom)
    minx, miny, maxx, maxy = geom.bounds
    w, h = maxx - minx, maxy - miny
    if w <= 0 or h <= 0:
        return [False] * (GRID * GRID)
    from shapely.geometry import Point

    prepared = prep(geom)
    cells = []
    for j in range(GRID):
        cy = miny + (j + 0.5) * h / GRID
        for i in range(GRID):
            cx = minx + (i + 0.5) * w / GRID
            cells.append(prepared.contains(Point(cx, cy)))
    return cells


def grid_to_hex(cells: list[bool]) -> str:
    """Compact hex encoding of the occupancy grid (stored in features)."""
    value = 0
    for bit in cells:
        value = (value << 1) | int(bit)
    return f"{value:0{GRID * GRID // 4}x}"


def hex_to_grid(hexstr: str) -> list[bool]:
    value = int(hexstr, 16)
    n = GRID * GRID
    return [bool((value >> (n - 1 - i)) & 1) for i in range(n)]


def iou(a: list[bool], b: list[bool]) -> float:
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    return inter / union if union else 0.0


def is_near_duplicate(hex_a: str, hex_b: str, threshold: float = NEAR_DUP_IOU) -> bool:
    return iou(hex_to_grid(hex_a), hex_to_grid(hex_b)) >= threshold
