"""PNG export — a RASTER of the master vector at a declared scale.

Never manufacturing truth (the SVG/DXF/PDF vectors are): it exists for
customer sharing, print previews and workshop wall sheets. The file is
rendered straight from the canonical mm polygons (even-odd, holes kept)
at `px_per_mm`, with a 1 px safety margin, and carries its scale, version
and geometry hash in PNG text chunks so the raster can be audited.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, PngImagePlugin
from shapely import wkt as shapely_wkt
from shapely.geometry import MultiPolygon

from ..schemas.jewellery_design import DesignCandidate, ImmutableSourceText

DEFAULT_PX_PER_MM = 20      # 508 dpi — crisp for print previews, small files
MARGIN_PX = 4
SUPERSAMPLE = 4
INK = (26, 26, 26, 255)
PAPER = (255, 255, 255, 0)  # transparent background


def _as_multi(geom) -> MultiPolygon:
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    return geom


def export_png(candidate: DesignCandidate, source: ImmutableSourceText, version_id: str | None = None,
               geometry_hash: str | None = None, px_per_mm: int = DEFAULT_PX_PER_MM) -> bytes:
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to export.")
    px_per_mm = max(4, min(int(px_per_mm), 100))
    geom = _as_multi(shapely_wkt.loads(candidate.geometry_wkt))
    minx, miny, maxx, maxy = geom.bounds
    w_px = int(round((maxx - minx) * px_per_mm)) + 2 * MARGIN_PX
    h_px = int(round((maxy - miny) * px_per_mm)) + 2 * MARGIN_PX
    # Supersample ×4 then box-downsample: edge pixels get fractional
    # coverage (anti-aliased), and the ink area measured from the alpha
    # channel matches the vector area instead of carrying a half-pixel
    # boundary bias from the integer polygon fill.
    ss = SUPERSAMPLE
    big = Image.new("RGBA", (w_px * ss, h_px * ss), PAPER)
    draw = ImageDraw.Draw(big)
    k = px_per_mm * ss

    def to_px(pt):
        x, y = pt
        return (MARGIN_PX * ss + (x - minx) * k, MARGIN_PX * ss + (maxy - y) * k)   # y up in mm → y down in px

    # Even-odd by construction: exterior in ink, each interior back to paper.
    for poly in geom.geoms:
        draw.polygon([to_px(p) for p in poly.exterior.coords], fill=INK)
        for ring in poly.interiors:
            draw.polygon([to_px(p) for p in ring.coords], fill=PAPER)
    img = big.resize((w_px, h_px), Image.BOX)

    meta = PngImagePlugin.PngInfo()
    meta.add_text("bs:units", "mm")
    meta.add_text("bs:px_per_mm", str(px_per_mm))
    meta.add_text("bs:margin_px", str(MARGIN_PX))
    meta.add_text("bs:width_mm", f"{maxx - minx:.3f}")
    meta.add_text("bs:height_mm", f"{maxy - miny:.3f}")
    meta.add_text("bs:source_text_sha256", source.sha256)
    if version_id:
        meta.add_text("bs:version_id", version_id)
    if geometry_hash:
        meta.add_text("bs:geometry_hash", geometry_hash)
    meta.add_text("bs:role", "PREVIEW_RASTER — not manufacturing truth; see SVG/DXF/PDF")
    buf = io.BytesIO()
    # dpi = px_per_mm × 25.4 so print tools place it at true size.
    img.save(buf, format="PNG", pnginfo=meta, dpi=(px_per_mm * 25.4, px_per_mm * 25.4))
    return buf.getvalue()


def reimport_png(png_bytes: bytes) -> dict:
    """Read the raster back: declared scale + measured ink area/extent in mm."""
    img = Image.open(io.BytesIO(png_bytes))
    info = dict(getattr(img, "text", {}) or {})
    ppm = float(info.get("bs:px_per_mm", DEFAULT_PX_PER_MM))
    margin = int(info.get("bs:margin_px", MARGIN_PX))
    alpha = img.convert("RGBA").getchannel("A")
    ink = alpha.point(lambda a: 255 if a > 127 else 0)
    bbox = ink.getbbox()
    if not bbox:
        return {"present": False, "px_per_mm": ppm}
    # Ink area = fractional coverage from the alpha histogram (anti-aliased
    # edges count partially), no per-pixel Python loop.
    hist = alpha.histogram()
    coverage_px = sum(i * n for i, n in enumerate(hist)) / 255.0
    return {
        "present": True,
        "px_per_mm": ppm,
        "area_mm2": coverage_px / (ppm * ppm),
        "width_mm": (bbox[2] - bbox[0]) / ppm,
        "height_mm": (bbox[3] - bbox[1]) / ppm,
        "declared_width_mm": float(info.get("bs:width_mm", 0) or 0),
        "declared_height_mm": float(info.get("bs:height_mm", 0) or 0),
        "geometry_hash": info.get("bs:geometry_hash"),
        "margin_px": margin,
    }


def compare_raster(master, raster: dict, geometry_hash: str | None = None) -> dict:
    """Raster fidelity: extent within one pixel, ink area within 1.5 % of
    the vector area (anti-aliasing-free even-odd fill), hash chunk matches."""
    master = _as_multi(master)
    checks = []
    if not raster.get("present"):
        return {"status": "FAIL", "label": "EXPORT FIDELITY: FAIL", "checks": [{"check": "geometry_present", "status": "FAIL"}],
                "note": "PNG is a preview raster, not manufacturing truth."}
    px = 1.0 / raster["px_per_mm"]
    mb = master.bounds
    mw, mh = mb[2] - mb[0], mb[3] - mb[1]
    dw, dh = abs(raster["width_mm"] - mw), abs(raster["height_mm"] - mh)
    checks.append({"check": "dimensions_mm", "status": "PASS" if max(dw, dh) <= 1.5 * px else "FAIL",
                   "master": [round(mw, 3), round(mh, 3)], "raster": [round(raster["width_mm"], 3), round(raster["height_mm"], 3)],
                   "tolerance_mm": round(1.5 * px, 4)})
    rel = abs(raster["area_mm2"] - master.area) / master.area if master.area else 1.0
    checks.append({"check": "area_mm2", "status": "PASS" if rel <= 0.015 else "FAIL",
                   "master": round(master.area, 3), "raster": round(raster["area_mm2"], 3), "relative_error": round(rel, 4)})
    if geometry_hash is not None:
        checks.append({"check": "geometry_hash_chunk", "status": "PASS" if raster.get("geometry_hash") == geometry_hash else "FAIL"})
    ok = all(c["status"] == "PASS" for c in checks)
    return {"status": "PASS" if ok else "FAIL", "label": f"EXPORT FIDELITY: {'PASS' if ok else 'FAIL'}", "checks": checks,
            "note": "PNG is a preview raster at a declared scale, not manufacturing truth."}
