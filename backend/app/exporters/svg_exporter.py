"""SVG export in real millimetres, vector-only, with traceability metadata.

The SVG viewBox is in mm units and width/height carry explicit mm units.
No raster elements. Metadata embeds schema/generator versions, design and
candidate ids, the immutable source text and its hash.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape

from shapely import wkt as shapely_wkt

from ..config import GENERATOR_VERSION, SCHEMA_VERSION
from ..schemas.jewellery_design import DesignCandidate, ImmutableSourceText

PRECISION = 4


def _ring_to_path(coords, flip_y: float) -> str:
    pts = [f"{round(x, PRECISION)},{round(flip_y - y, PRECISION)}" for x, y in coords]
    return "M " + " L ".join(pts) + " Z"


def geometry_to_path_d(geom, flip_y: float) -> str:
    """MultiPolygon → single path with even-odd holes. Y axis flipped so the
    design is upright in SVG's y-down coordinate system."""
    parts = []
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for poly in polys:
        parts.append(_ring_to_path(poly.exterior.coords, flip_y))
        for ring in poly.interiors:
            parts.append(_ring_to_path(ring.coords, flip_y))
    return " ".join(parts)


def export_svg(candidate: DesignCandidate, source: ImmutableSourceText) -> str:
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to export.")
    geom = shapely_wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    margin = 1.0
    w = round(maxx - minx + 2 * margin, PRECISION)
    h = round(maxy - miny + 2 * margin, PRECISION)
    # Shift so geometry sits at margin offset; flip y within local frame.
    from shapely import affinity

    local = affinity.translate(geom, xoff=-minx + margin, yoff=-miny + margin)
    d = geometry_to_path_d(local, flip_y=h)

    meta = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "design_id": candidate.design_id,
        "candidate_id": candidate.candidate_id,
        "recipe_id": candidate.recipe.recipe_id,
        "font_id": candidate.recipe.font_id,
        "units": "mm",
        "source_text": source.normalized_text,
        "source_text_sha256": source.sha256,
        "production_export_allowed": bool(
            candidate.validation and candidate.validation.production_export_allowed
        ),
        "rules_profile": candidate.validation.rules_profile if candidate.validation else None,
    }
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}">\n'
        f"  <metadata>{escape(json.dumps(meta, ensure_ascii=False))}</metadata>\n"
        f'  <path d="{d}" fill="#1a1a1a" fill-rule="evenodd" stroke="none"/>\n'
        f"</svg>\n"
    )
