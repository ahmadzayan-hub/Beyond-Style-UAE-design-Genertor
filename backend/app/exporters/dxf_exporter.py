"""DXF export for workshop handoff.

- R2010 DXF, $INSUNITS = 4 (millimetres), $MEASUREMENT = 1 (metric).
- Closed LWPOLYLINEs on layer CUT (exteriors) and HOLES (interiors).
- Traceability metadata (design/candidate ids, source-text hash, versions)
  stored as DXF custom header variables — machine-readable, no raster.

Export refuses candidates whose validation did not allow production export
(BLOCK_PRODUCTION_EXPORT behaviour), unless explicitly exporting a preview.
"""
from __future__ import annotations

import io

import ezdxf
from shapely import wkt as shapely_wkt

from ..config import GENERATOR_VERSION, SCHEMA_VERSION
from ..schemas.jewellery_design import DesignCandidate, ImmutableSourceText


class ProductionExportBlocked(Exception):
    pass


def export_dxf(
    candidate: DesignCandidate,
    source: ImmutableSourceText,
    allow_preview: bool = False,
) -> str:
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to export.")
    validation = candidate.validation
    if not (validation and validation.production_export_allowed):
        if not allow_preview:
            raise ProductionExportBlocked(
                "BLOCK_PRODUCTION_EXPORT: candidate failed validation "
                "or identity/rights checks."
            )
    if not source.confirmed:
        raise ProductionExportBlocked(
            "BLOCK_PRODUCTION_EXPORT: source text not customer-confirmed."
        )

    geom = shapely_wkt.loads(candidate.geometry_wkt)
    doc = ezdxf.new("R2010", setup=False)
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric
    doc.header.custom_vars.append("SCHEMA_VERSION", SCHEMA_VERSION)
    doc.header.custom_vars.append("GENERATOR_VERSION", GENERATOR_VERSION)
    doc.header.custom_vars.append("DESIGN_ID", candidate.design_id)
    doc.header.custom_vars.append("CANDIDATE_ID", candidate.candidate_id)
    doc.header.custom_vars.append("RECIPE_ID", candidate.recipe.recipe_id)
    doc.header.custom_vars.append("SOURCE_TEXT_SHA256", source.sha256)
    doc.header.custom_vars.append("FONT_ID", candidate.recipe.font_id)
    doc.header.custom_vars.append(
        "FONT_AXES",
        ",".join(f"{t}={v:g}" for t, v in sorted(candidate.recipe.font_axes.items())) or "default",
    )
    doc.header.custom_vars.append("OT_FEATURE_SET", candidate.recipe.ot_feature_set)
    doc.header.custom_vars.append("UNITS", "mm")
    doc.header.custom_vars.append(
        "RULES_PROFILE", validation.rules_profile if validation else "none"
    )

    doc.layers.add("CUT", color=1)
    doc.layers.add("HOLES", color=5)
    msp = doc.modelspace()

    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for poly in polys:
        msp.add_lwpolyline(
            list(poly.exterior.coords), close=True, dxfattribs={"layer": "CUT"}
        )
        for ring in poly.interiors:
            msp.add_lwpolyline(
                list(ring.coords), close=True, dxfattribs={"layer": "HOLES"}
            )

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue()
