"""3D visualization payload — customer trust view, never manufacturing truth.

Serves the canonical 2D vector geometry (the single source of truth) plus
the real physical parameters the client needs to EXTRUDE it in the browser
(Three.js): thickness, real mm dimensions, ring bend radius, and a
deterministic weight estimate (area × thickness × density — plain rules
math, no AI). The 2D Design Graph remains canonical; the mesh exists only
client-side and nothing rendered in 3D can flow back into geometry.
"""
from __future__ import annotations

import math

from shapely import wkt as shapely_wkt

from ..config import DEFAULT_RULES
from ..db import models as m

#: g/cm³ — standard alloy densities (deterministic pricing/weight inputs).
MATERIAL_DENSITY_G_CM3 = {
    "silver-925": 10.36,
    "gold-18k-yellow": 15.5,
    "gold-18k-rose": 15.0,
    "gold-18k-white": 15.7,
    "platinum": 21.45,
}

WEIGHT_BASIS = "AREA_X_THICKNESS_X_DENSITY"
DISCLAIMER = "3D preview for visualization — the 2D vector design remains the manufacturing truth."


def _rings_of(geom) -> list[dict]:
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for poly in polys:
        out.append({
            "exterior": [[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords],
            "holes": [
                [[round(x, 3), round(y, 3)] for x, y in ring.coords]
                for ring in poly.interiors
            ],
        })
    return out


def mesh3d_payload(version: m.DesignVersion, product_type: str) -> dict:
    geom = shapely_wkt.loads(version.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds

    recipe = version.recipe or {}
    ring_spec = recipe.get("ring")
    if ring_spec:
        thickness = float(ring_spec.get("thickness_mm", 1.5))
    else:
        features = (version.validation or {}).get("features") or {}
        thickness = float(features.get("thickness_mm") or DEFAULT_RULES.material_thickness_mm)

    volume_mm3 = geom.area * thickness
    weights = {
        mat: round(volume_mm3 * d / 1000.0, 2)
        for mat, d in MATERIAL_DENSITY_G_CM3.items()
    }

    ring_info = None
    if ring_spec:
        size_eu = float(ring_spec.get("size_eu", 52))
        ring_info = {
            "size_eu": size_eu,
            "band_height_mm": float(ring_spec.get("band_height_mm", 7.5)),
            # EU size = inner circumference (mm) → bend radius for the
            # client-side cylindrical wrap of the flat strip.
            "inner_radius_mm": round(size_eu / (2 * math.pi), 3),
            "length_mm": round(maxx - minx, 3),
        }

    engrave = []
    if ring_spec and version.text_geometry_wkt:
        engrave = _rings_of(shapely_wkt.loads(version.text_geometry_wkt))

    return {
        "units": "mm",
        "basis": "CANONICAL_2D_VECTOR_EXTRUSION",
        "disclaimer": DISCLAIMER,
        "product_type": product_type,
        "version_number": version.version_number,
        "geometry_hash": version.geometry_hash,
        "width_mm": round(maxx - minx, 3),
        "height_mm": round(maxy - miny, 3),
        "thickness_mm": round(thickness, 3),
        "polygons": _rings_of(geom),
        "engrave_polygons": engrave,
        "ring": ring_info,
        "weight_estimate_g": weights,
        "weight_basis": WEIGHT_BASIS,
    }
