"""Dimensioned agreement proof — the artifact the customer approves.

Beyond Style's manual workflow puts the real dimensions ON the drawing the
customer signs off (spec sheets with mm/cm callouts). This exporter does the
same deterministically: the canonical vector design, real-millimetre
dimension lines measured from the built geometry, and a spec block binding
text, font, product, version and hashes. It is a display/approval artifact —
the canonical single-silhouette SVG/DXF remain the manufacturing exports.

Deterministic by construction: same version → byte-identical SVG, so its
sha256 can be recorded on the approval as the exact picture that was agreed.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape

from shapely import affinity
from shapely import wkt as shapely_wkt

from ..schemas.jewellery_design import DesignCandidate, ImmutableSourceText
from .svg_exporter import PRECISION, RELIEF_COMPOSITIONS, geometry_to_path_d

# Layout constants (all mm — 1 SVG user unit = 1 mm).
_MARGIN = 2.0          # breathing room around the design silhouette
_DIM_GAP = 3.0         # gap between design box and a dimension line
_DIM_TEXT = 3.2        # dimension label font size
_INFO_ROW = 5.2        # spec block row height
_INFO_PAD = 4.0
_FONT_STACK = "Tajawal, 'Segoe UI', Arial, sans-serif"

_PRODUCT_AR = {
    "pendant": "قلادة (تعليقة)",
    "necklace": "عقد",
    "earring": "حلق",
    "drop_earring": "حلق متدلٍ",
    "single_letter_earring": "حلق حرف",
    "bracelet": "سوار",
    "cufflink": "كبك",
    "ring": "خاتم",
    "brooch": "بروش",
    "medallion": "ميدالية",
}


def _fmt(v: float) -> str:
    return f"{round(v, 1):g}"


def _dim_h(x1: float, x2: float, y: float, label: str) -> str:
    """Horizontal dimension line with arrowheads and centered label."""
    mid = (x1 + x2) / 2
    return (
        f'  <g stroke="#8a6d3b" stroke-width="0.25" fill="none">\n'
        f'    <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" marker-start="url(#arr)" marker-end="url(#arr)"/>\n'
        f'    <line x1="{x1}" y1="{y - 2}" x2="{x1}" y2="{y + 1}"/>\n'
        f'    <line x1="{x2}" y1="{y - 2}" x2="{x2}" y2="{y + 1}"/>\n'
        f"  </g>\n"
        f'  <text x="{mid}" y="{y + _DIM_TEXT + 0.8}" font-size="{_DIM_TEXT}" text-anchor="middle" '
        f'font-family="{_FONT_STACK}" fill="#5a4620" direction="ltr" unicode-bidi="embed">{label}</text>\n'
    )


def _dim_v(x: float, y1: float, y2: float, label: str) -> str:
    """Vertical dimension line; label rotated to read upward."""
    mid = (y1 + y2) / 2
    return (
        f'  <g stroke="#8a6d3b" stroke-width="0.25" fill="none">\n'
        f'    <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" marker-start="url(#arr)" marker-end="url(#arr)"/>\n'
        f'    <line x1="{x - 1}" y1="{y1}" x2="{x + 2}" y2="{y1}"/>\n'
        f'    <line x1="{x - 1}" y1="{y2}" x2="{x + 2}" y2="{y2}"/>\n'
        f"  </g>\n"
        f'  <text x="{x + _DIM_TEXT + 0.5}" y="{mid}" font-size="{_DIM_TEXT}" text-anchor="middle" '
        f'font-family="{_FONT_STACK}" fill="#5a4620" direction="ltr" unicode-bidi="embed" '
        f'transform="rotate(90 {x + _DIM_TEXT + 0.5} {mid})">{label}</text>\n'
    )


def export_agreement_proof_svg(
    candidate: DesignCandidate,
    source: ImmutableSourceText,
    *,
    version_number: int,
    geometry_hash: str,
    product_type: str = "pendant",
    material_label: str | None = None,
) -> str:
    if not candidate.geometry_wkt:
        raise ValueError("Candidate has no geometry to render.")

    geom = shapely_wkt.loads(candidate.geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    w = round(maxx - minx, PRECISION)
    h = round(maxy - miny, PRECISION)

    # Design frame: dimension lines live to the right and below the design.
    ox, oy = _MARGIN + 1.0, _MARGIN + 1.0
    local = affinity.translate(geom, xoff=-minx + ox, yoff=-miny + oy)
    design_bottom = oy + h
    base_d = geometry_to_path_d(local, flip_y=design_bottom + oy)

    text_layer = ""
    if candidate.recipe.composition in RELIEF_COMPOSITIONS and candidate.text_geometry_wkt:
        tg = shapely_wkt.loads(candidate.text_geometry_wkt)
        tl = affinity.translate(tg, xoff=-minx + ox, yoff=-miny + oy)
        text_layer = (
            f'  <path d="{geometry_to_path_d(tl, flip_y=design_bottom + oy)}" '
            f'fill="#f5efe2" fill-rule="evenodd" stroke="none"/>\n'
        )

    dim_y = design_bottom + oy + _DIM_GAP
    dim_x = ox + w + _DIM_GAP

    # Ring second face: draw the inner-face flat pattern as its own band
    # panel under the dimension line, labelled explicitly. (The layer is
    # mirrored for back-face engraving — shown as manufactured.)
    inner_block = ""
    inner_extra_h = 0.0
    if candidate.recipe.ring is not None and candidate.inner_text_geometry_wkt:
        inner_geom = shapely_wkt.loads(candidate.inner_text_geometry_wkt)
        iy_top = dim_y + _DIM_TEXT + 4.0
        band_local = affinity.translate(geom, xoff=-minx + ox, yoff=-miny + iy_top)
        inner_local = affinity.translate(inner_geom, xoff=-minx + ox, yoff=-miny + iy_top)
        inner_block = (
            f'  <text x="{ox + w}" y="{iy_top - 1.2}" font-size="3.0" text-anchor="start" '
            f'font-family="{_FONT_STACK}" fill="#5a4620" direction="rtl" unicode-bidi="embed">'
            "الوجه الداخلي (نقش من الخلف)</text>\n"
            f'  <path d="{geometry_to_path_d(band_local, flip_y=2 * iy_top + h)}" '
            f'fill="#1a1a1a" fill-rule="evenodd" stroke="none"/>\n'
            f'  <path d="{geometry_to_path_d(inner_local, flip_y=2 * iy_top + h)}" '
            f'fill="#f5efe2" fill-rule="evenodd" stroke="none"/>\n'
        )
        inner_extra_h = h + 6.5

    rows: list[tuple[str, str]] = [
        ("النص", source.normalized_text),
        ("المنتج", _PRODUCT_AR.get(product_type, product_type)),
        ("الخط", candidate.recipe.font_id),
        ("الأبعاد الحقيقية", f"{_fmt(w)} × {_fmt(h)} mm"),
        ("النسخة", f"v{version_number} · {geometry_hash[:12]}"),
    ]
    if material_label:
        rows.insert(2, ("الخامة", material_label))

    info_top = dim_y + _DIM_TEXT + 4.0 + inner_extra_h
    info_h = _INFO_PAD * 2 + _INFO_ROW * len(rows) + 9.6
    total_w = round(max(dim_x + _DIM_TEXT + 6.0, 78.0), PRECISION)
    total_h = round(info_top + info_h + _MARGIN, PRECISION)

    info_rows = ""
    for i, (k, v) in enumerate(rows):
        ry = info_top + _INFO_PAD + _INFO_ROW * (i + 1) - 1.5
        info_rows += (
            # RTL rows are anchored at their START (the right edge) and flow
            # leftwards; with direction="rtl", text-anchor="end" would put the
            # row's left end at the right margin and run it off the sheet.
            f'  <text x="{total_w - _INFO_PAD - 1}" y="{ry}" font-size="3.4" text-anchor="start" '
            f'font-family="{_FONT_STACK}" fill="#3d3325" direction="rtl" unicode-bidi="embed">'
            f'<tspan font-weight="bold">{escape(k)}: </tspan>{escape(v)}</text>\n'
        )
    footer_y = info_top + _INFO_PAD + _INFO_ROW * len(rows) + 3.5
    # Two centred lines: one line is wider than the 78 mm minimum sheet.
    footer = (
        f'  <text x="{total_w / 2}" y="{footer_y}" font-size="2.8" text-anchor="middle" '
        f'font-family="{_FONT_STACK}" fill="#8a6d3b" direction="rtl" unicode-bidi="embed">'
        "رسم مرجعي بالأبعاد الحقيقية بالمليمتر</text>\n"
        f'  <text x="{total_w / 2}" y="{footer_y + 3.6}" font-size="2.8" text-anchor="middle" '
        f'font-family="{_FONT_STACK}" fill="#8a6d3b" direction="rtl" unicode-bidi="embed">'
        "يُعتمد هذا التصميم قبل التصنيع</text>\n"
    )

    meta = {
        "agreement_proof": True,
        "units": "mm",
        "design_id": candidate.design_id,
        "candidate_id": candidate.candidate_id,
        "version_number": version_number,
        "geometry_hash": geometry_hash,
        "source_text": source.normalized_text,
        "source_text_sha256": source.sha256,
        "width_mm": w,
        "height_mm": h,
        "note": "dimensioned approval artifact; canonical geometry unchanged",
    }
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}mm" height="{total_h}mm" '
        f'viewBox="0 0 {total_w} {total_h}">\n'
        f"  <metadata>{escape(json.dumps(meta, ensure_ascii=False, sort_keys=True))}</metadata>\n"
        f'  <defs><marker id="arr" viewBox="0 0 6 6" refX="3" refY="3" markerWidth="4" '
        f'markerHeight="4" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 6 3 L 0 6 z" fill="#8a6d3b"/></marker></defs>\n'
        f'  <rect x="0" y="0" width="{total_w}" height="{total_h}" fill="#fdfaf4"/>\n'
        f'  <rect x="0.6" y="0.6" width="{total_w - 1.2}" height="{total_h - 1.2}" fill="none" '
        f'stroke="#c9a961" stroke-width="0.35"/>\n'
        f'  <path d="{base_d}" fill="#1a1a1a" fill-rule="evenodd" stroke="none"/>\n'
        f"{text_layer}"
        f"{_dim_h(ox, ox + w, dim_y, f'{_fmt(w)} mm')}"
        f"{_dim_v(dim_x, oy, design_bottom, f'{_fmt(h)} mm')}"
        f"{inner_block}"
        f'  <line x1="{_INFO_PAD}" y1="{info_top}" x2="{total_w - _INFO_PAD}" y2="{info_top}" '
        f'stroke="#c9a961" stroke-width="0.3"/>\n'
        f"{info_rows}"
        f"{footer}"
        f"</svg>\n"
    )
