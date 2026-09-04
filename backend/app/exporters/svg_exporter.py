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


#: Compositions where the text sits on a solid plate — without relief
#: differentiation the proof would render as a featureless silhouette.
#: engraved_band: ring bands render the ENGRAVE layer on the solid strip.
RELIEF_COMPOSITIONS = {"plate_oval", "plate_rect", "engraved_band"}


def export_proof_svg(candidate: DesignCandidate, source: ImmutableSourceText) -> str:
    """High-fidelity customer/designer proof render.

    Faithful to the canonical vector geometry (same mm frame, same holes,
    counters, bridges, dots and loops). For relief compositions the raised
    text is drawn as a second differentiated layer so it stays visible on
    the solid plate. Display artifact only — production SVG/DXF remain the
    single-silhouette canonical exports."""
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to render.")
    from shapely import affinity

    geom = shapely_wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    margin = 1.0
    w = round(maxx - minx + 2 * margin, PRECISION)
    h = round(maxy - miny + 2 * margin, PRECISION)
    local = affinity.translate(geom, xoff=-minx + margin, yoff=-miny + margin)
    base_d = geometry_to_path_d(local, flip_y=h)

    text_layer = ""
    if candidate.recipe.composition in RELIEF_COMPOSITIONS and candidate.text_geometry_wkt:
        text_geom = shapely_wkt.loads(candidate.text_geometry_wkt)
        text_local = affinity.translate(text_geom, xoff=-minx + margin, yoff=-miny + margin)
        text_d = geometry_to_path_d(text_local, flip_y=h)
        text_layer = (
            f'  <path d="{text_d}" fill="#f5efe2" fill-rule="evenodd" stroke="none"/>\n'
        )

    meta = {
        "proof_render": True,
        "relief_differentiated": bool(text_layer),
        "design_id": candidate.design_id,
        "candidate_id": candidate.candidate_id,
        "units": "mm",
        "source_text_sha256": source.sha256,
        "note": "display proof; canonical geometry unchanged",
    }
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}">\n'
        f"  <metadata>{escape(json.dumps(meta, ensure_ascii=False))}</metadata>\n"
        f'  <path d="{base_d}" fill="#1a1a1a" fill-rule="evenodd" stroke="none"/>\n'
        f"{text_layer}"
        f"</svg>\n"
    )


#: Deterministic "real metal" presentation of the SAME vector geometry
#: (reference study: customers judge a finished-looking piece, not a black
#: silhouette). Pure SVG gradients + lighting filters — no raster, no AI,
#: no credentials; the path data is byte-identical to the flat proof, so
#: nothing here can drift from manufacturing truth.
MATERIAL_RENDER = {
    "silver-925":      {"label": "Silver 925",        "stops": ["#fbfbfa", "#d9dadc", "#a9abb0", "#e8e9eb", "#8f9297"]},
    "gold-18k-yellow": {"label": "18K yellow gold",   "stops": ["#fff3c4", "#f2c94c", "#c9962b", "#f7dc7a", "#a67c1e"]},
    "gold-18k-rose":   {"label": "18K rose gold",     "stops": ["#ffe4d6", "#e8a98a", "#c27a5a", "#f3c1a8", "#a0603f"]},
    "gold-18k-white":  {"label": "18K white gold",    "stops": ["#ffffff", "#e6e8ea", "#b8bcc2", "#f0f1f3", "#9da2a9"]},
    "platinum":        {"label": "Platinum",          "stops": ["#f6f7f8", "#dcdfe3", "#b0b5bb", "#e9ebee", "#969ba2"]},
}
STUDIO_BACKGROUND = "#f7f3ec"


def export_material_proof_svg(candidate: DesignCandidate, source: ImmutableSourceText,
                              material: str) -> str:
    """Customer-facing material render: metal gradient, bevel highlight and a
    soft drop shadow on a neutral studio ground. Display artifact only —
    same mm frame and path data as `export_proof_svg`."""
    if material not in MATERIAL_RENDER:
        raise ValueError(f"Unknown material: {material}")
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to render.")
    from shapely import affinity

    geom = shapely_wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    margin = 1.0
    w = round(maxx - minx + 2 * margin, PRECISION)
    h = round(maxy - miny + 2 * margin, PRECISION)
    local = affinity.translate(geom, xoff=-minx + margin, yoff=-miny + margin)
    base_d = geometry_to_path_d(local, flip_y=h)
    height_mm = maxy - miny
    blur = round(max(0.12, min(0.45, height_mm * 0.02)), 3)   # bevel radius scales with the piece
    stops = MATERIAL_RENDER[material]["stops"]
    offsets = ("0%", "28%", "52%", "74%", "100%")
    gradient = "".join(
        f'<stop offset="{o}" stop-color="{c}"/>' for o, c in zip(offsets, stops)
    )

    text_layer = ""
    if candidate.recipe.composition in RELIEF_COMPOSITIONS and candidate.text_geometry_wkt:
        text_geom = shapely_wkt.loads(candidate.text_geometry_wkt)
        text_local = affinity.translate(text_geom, xoff=-minx + margin, yoff=-miny + margin)
        text_d = geometry_to_path_d(text_local, flip_y=h)
        text_layer = (
            f'  <path d="{text_d}" fill="url(#metal-hi)" fill-rule="evenodd" stroke="none" '
            f'filter="url(#bevel)"/>\n'
        )

    meta = {
        "proof_render": True,
        "material_render": material,
        "design_id": candidate.design_id,
        "candidate_id": candidate.candidate_id,
        "units": "mm",
        "source_text_sha256": source.sha256,
        "note": "display render (vector gradients/lighting only); canonical geometry unchanged",
    }
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
        f'viewBox="0 0 {w} {h}">\n'
        f"  <metadata>{escape(json.dumps(meta, ensure_ascii=False))}</metadata>\n"
        "  <defs>\n"
        f'    <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1">{gradient}</linearGradient>\n'
        f'    <linearGradient id="metal-hi" x1="1" y1="0" x2="0" y2="1">{gradient}</linearGradient>\n'
        f'    <filter id="bevel" x="-10%" y="-10%" width="120%" height="120%" color-interpolation-filters="sRGB">\n'
        f'      <feGaussianBlur in="SourceAlpha" stdDeviation="{blur}" result="blur"/>\n'
        f'      <feSpecularLighting in="blur" surfaceScale="{round(blur * 6, 3)}" specularConstant="0.75" '
        f'specularExponent="20" lighting-color="#ffffff" result="spec">'
        f'<feDistantLight azimuth="225" elevation="48"/></feSpecularLighting>\n'
        f'      <feComposite in="spec" in2="SourceAlpha" operator="in" result="spec-in"/>\n'
        f'      <feComposite in="SourceGraphic" in2="spec-in" operator="arithmetic" k1="0" k2="1" k3="0.85" k4="0"/>\n'
        "    </filter>\n"
        f'    <filter id="shadow" x="-15%" y="-15%" width="130%" height="140%">'
        f'<feDropShadow dx="{round(blur, 3)}" dy="{round(blur * 2, 3)}" stdDeviation="{round(blur * 2.5, 3)}" '
        f'flood-color="#3b2f1e" flood-opacity="0.35"/></filter>\n'
        "  </defs>\n"
        f'  <rect width="{w}" height="{h}" fill="{STUDIO_BACKGROUND}"/>\n'
        f'  <path d="{base_d}" fill="url(#metal)" fill-rule="evenodd" stroke="none" '
        f'filter="url(#shadow)"/>\n'
        f'  <path d="{base_d}" fill="url(#metal)" fill-rule="evenodd" stroke="none" '
        f'filter="url(#bevel)"/>\n'
        f"{text_layer}"
        f"</svg>\n"
    )


def _font_sha(font_id: str) -> str:
    from ..fonts.registry import get_registry

    return get_registry().get(font_id).computed_sha256


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
        # Everything needed to reconstruct this exact geometry later: the
        # font binary, the variation coordinates and the OT feature set.
        "font_axes": dict(candidate.recipe.font_axes),
        "ot_feature_set": candidate.recipe.ot_feature_set,
        "font_binary_sha256": _font_sha(candidate.recipe.font_id),
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
