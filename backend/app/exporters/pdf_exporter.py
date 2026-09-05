"""PDF workshop export — true scale (1 mm = 72/25.4 pt), vector only.

The design is drawn as filled vector paths (even-odd) at exact millimetre
scale on a page sized to the piece plus margins, with a dimension
callout and a manifest block. Arabic text is NOT typeset by the PDF
library (it does not shape Arabic): the lettering on the page IS the
manufacturing vector, and the exact source text travels in the PDF
metadata (Unicode) and the manifest by codepoints + SHA-256.
"""
from __future__ import annotations

import io
import json

from reportlab.lib.pagesizes import landscape  # noqa: F401  (kept for callers)
from reportlab.pdfgen import canvas
from reportlab.pdfgen.pathobject import PDFPathObject
from shapely import wkt as shapely_wkt

from ..config import GENERATOR_VERSION, SCHEMA_VERSION
from ..schemas.jewellery_design import DesignCandidate, ImmutableSourceText

MM = 72.0 / 25.4
MARGIN_MM = 12.0
FOOTER_MM = 22.0


def export_pdf(candidate: DesignCandidate, source: ImmutableSourceText, version_id: str | None = None,
               geometry_hash: str | None = None) -> bytes:
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to export.")
    geom = shapely_wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    w_mm, h_mm = maxx - minx, maxy - miny
    page_w = (w_mm + 2 * MARGIN_MM) * MM
    page_h = (h_mm + 2 * MARGIN_MM + FOOTER_MM) * MM
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h), pageCompression=0)
    c.setTitle(f"Beyond Style workshop export {candidate.candidate_id}")
    c.setSubject(f"source_text_sha256={source.sha256}")
    c.setAuthor("Beyond Style UAE — deterministic vector export")
    c.setKeywords(f"design={candidate.design_id};candidate={candidate.candidate_id};"
                  f"version={version_id or ''};units=mm;text_sha256={source.sha256};"
                  f"codepoints={' '.join(f'U+{ord(ch):04X}' for ch in source.normalized_text)}")
    # geometry at exact scale, origin at (MARGIN, MARGIN + FOOTER)
    ox = (MARGIN_MM - minx) * MM
    oy = (MARGIN_MM + FOOTER_MM - miny) * MM
    path: PDFPathObject = c.beginPath()
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            coords = list(ring.coords)
            path.moveTo(ox + coords[0][0] * MM, oy + coords[0][1] * MM)
            for x, y in coords[1:]:
                path.lineTo(ox + x * MM, oy + y * MM)
            path.close()
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawPath(path, stroke=0, fill=1, fillMode=1)  # even-odd
    # dimension callout + manifest (Latin only; the Arabic is the vector)
    c.setFont("Helvetica", 8)
    y_text = (FOOTER_MM - 4) * MM
    lines = [
        f"BEYOND STYLE — WORKSHOP EXPORT  |  {w_mm:.2f} x {h_mm:.2f} mm  |  scale 1:1  |  units mm",
        f"design {candidate.design_id}  candidate {candidate.candidate_id}  version {version_id or '-'}",
        f"source_text_sha256 {source.sha256}",
        f"geometry_hash {geometry_hash or '-'}  font {candidate.recipe.font_id}  recipe {candidate.recipe.recipe_id}",
        f"schema {SCHEMA_VERSION}  generator {GENERATOR_VERSION}  codepoints "
        + " ".join(f"U+{ord(ch):04X}" for ch in source.normalized_text)[:180],
    ]
    for i, line in enumerate(lines):
        c.drawString(MARGIN_MM * MM, y_text - i * 10, line[:200])
    # dimension lines
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    x0, x1 = ox + minx * MM, ox + maxx * MM
    yb = oy + miny * MM - 4 * MM
    c.line(x0, yb, x1, yb)
    c.drawCentredString((x0 + x1) / 2, yb - 8, f"{w_mm:.2f} mm")
    xr = ox + maxx * MM + 4 * MM
    c.line(xr, oy + miny * MM, xr, oy + maxy * MM)
    c.drawString(xr + 3, (oy + (miny + maxy) / 2 * MM), f"{h_mm:.2f} mm")
    c.showPage()
    c.save()
    return buf.getvalue()


def manifest_for(candidate: DesignCandidate, source: ImmutableSourceText, fmt: str, content_sha256: str,
                 version_id: str | None, geometry_hash: str | None) -> dict:
    """Export manifest: everything a workshop or auditor needs to trust the
    file — text hash and codepoints, version, geometry hash, source metadata."""
    return {
        "format": fmt, "units": "mm", "content_sha256": content_sha256,
        "design_id": candidate.design_id, "candidate_id": candidate.candidate_id,
        "version_id": version_id, "geometry_hash": geometry_hash,
        "source_text": source.normalized_text, "source_text_sha256": source.sha256,
        "codepoints": [f"U+{ord(ch):04X}" for ch in source.normalized_text],
        "font_id": candidate.recipe.font_id, "recipe_id": candidate.recipe.recipe_id,
        "schema_version": SCHEMA_VERSION, "generator_version": GENERATOR_VERSION,
    }
