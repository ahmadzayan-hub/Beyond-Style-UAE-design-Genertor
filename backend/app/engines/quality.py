"""Visual quality evaluation layer.

Every metric here is a deterministic GEOMETRIC HEURISTIC and is labelled
as such — none of these are ML-validated aesthetic judgements. The report
is attached to candidates for diagnostics/designer use; the customer UI
does not show raw formulas.
"""
from __future__ import annotations

from shapely import wkt as shapely_wkt

HEURISTIC_LABEL = "HEURISTIC / NOT ML-VALIDATED"


def evaluate(geometry_wkt: str, text_geometry_wkt: str | None, identity_verified: bool,
             validation_passed: bool, occupancy_hex: str | None = None,
             pool_min_iou: float | None = None) -> dict:
    """Returns a labelled quality report for one candidate."""
    geom = shapely_wkt.loads(geometry_wkt) if geometry_wkt else None
    text = shapely_wkt.loads(text_geometry_wkt) if text_geometry_wkt else None

    report: dict = {"label": HEURISTIC_LABEL}
    report["arabic_integrity"] = {
        "value": 1.0 if identity_verified else 0.0,
        "basis": "deterministic glyph identity proof (not heuristic)",
    }
    report["manufacturability"] = {
        "value": 1.0 if validation_passed else 0.0,
        "basis": "deterministic constraint validation (not heuristic)",
    }

    if geom is not None and not geom.is_empty:
        minx, miny, maxx, maxy = geom.bounds
        w, h = maxx - minx, maxy - miny
        bbox_area = w * h if w and h else 1.0
        cx, cy = geom.centroid.x, geom.centroid.y
        bx, by = (minx + maxx) / 2, (miny + maxy) / 2
        offset = (((cx - bx) / w) ** 2 + ((cy - by) / h) ** 2) ** 0.5 if w and h else 1.0
        report["visual_balance"] = {
            "value": round(max(0.0, 1.0 - offset * 2.5), 3),
            "basis": f"centroid vs bbox-center offset — {HEURISTIC_LABEL}",
        }
        holes = sum(len(p.interiors) for p in geom.geoms)
        report["wearability"] = {
            "value": round(max(0.0, min(1.0, 1.0 - max(w - 45, 0) / 45)) * (1.0 / (1 + 0.03 * holes)), 3),
            "basis": f"size envelope + snag-hole proxy — {HEURISTIC_LABEL}",
        }
    if text is not None and not text.is_empty and geom is not None and not geom.is_empty:
        # Readability proxy: how much of the silhouette the text occupies and
        # whether letter counters survived construction.
        text_ratio = text.area / geom.area if geom.area else 0
        text_holes = sum(len(p.interiors) for p in text.geoms)
        report["readability"] = {
            "value": round(min(1.0, 0.4 + 0.6 * min(text_ratio / 0.35, 1.0)) * (1.0 if text_holes >= 0 else 0.8), 3),
            "text_area_ratio": round(text_ratio, 3),
            "text_counter_holes": text_holes,
            "basis": f"text-to-silhouette ratio + counter survival — {HEURISTIC_LABEL}",
        }
    if occupancy_hex is not None and pool_min_iou is not None:
        report["originality"] = {
            "value": round(max(0.0, 1.0 - pool_min_iou), 3),
            "basis": f"1 − max occupancy-IoU vs other top candidates — {HEURISTIC_LABEL}",
        }
    return report
