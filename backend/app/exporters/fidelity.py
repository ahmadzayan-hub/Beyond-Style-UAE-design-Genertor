"""Export Fidelity Gate — re-import what was written and compare it with
the master vector. Only a passing comparison may mark WORKSHOP READY."""
from __future__ import annotations

import re
import zlib

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

DIM_TOL_MM = 0.02
AREA_TOL = 0.005          # 0.5 % of the master area
SYMDIFF_TOL = 0.01        # 1 % symmetric-difference area
_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _as_multi(geom) -> MultiPolygon:
    if geom.is_empty:
        return MultiPolygon([])
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    return MultiPolygon([g for g in geom.geoms if g.geom_type == "Polygon"])


def _even_odd(rings: list[list[tuple[float, float]]]):
    """Rings → even-odd filled geometry (exterior/hole nesting by XOR)."""
    result = None
    for ring in sorted((r for r in rings if len(r) >= 3), key=lambda r: -Polygon(r).area):
        poly = Polygon(ring).buffer(0)
        result = poly if result is None else result.symmetric_difference(poly)
    return _as_multi(result) if result is not None else MultiPolygon([])


def reimport_svg(svg_text: str) -> MultiPolygon:
    """Our SVG writes absolute M/L/Z polylines in mm with the y axis flipped
    by the viewBox height."""
    m = re.search(r'viewBox="0 0 (%s) (%s)"' % (_NUM, _NUM), svg_text)
    if not m:
        raise ValueError("SVG has no mm viewBox")
    h = float(m.group(2))
    rings: list[list[tuple[float, float]]] = []
    for d in re.findall(r'<path d="([^"]+)"', svg_text):
        for sub in re.findall(r"M[^MZ]*Z", d):
            pts = [(float(x), h - float(y)) for x, y in re.findall(r"(%s),(%s)" % (_NUM, _NUM), sub)]
            if len(pts) >= 3:
                rings.append(pts)
        break  # the first path is the manufacturing silhouette (proof layers follow)
    return _even_odd(rings)


def reimport_dxf(dxf_text: str) -> MultiPolygon:
    import io

    import ezdxf

    doc = ezdxf.read(io.StringIO(dxf_text))
    if doc.header.get("$INSUNITS") != 4:
        raise ValueError("DXF is not in millimetres")
    rings = []
    for e in doc.modelspace():
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer in ("CUT", "HOLES"):
            rings.append([(p[0], p[1]) for p in e.get_points("xy")])
    return _even_odd(rings)


def reimport_pdf(pdf_bytes: bytes) -> MultiPolygon:
    """Parse our own (uncompressed or Flate) content stream: m/l/h ops in
    points → mm, relative to the page origin used at export."""
    text = pdf_bytes
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", text, re.S)
    ops = b""
    for s in streams:
        try:
            s = zlib.decompress(s)
        except zlib.error:
            pass
        if b" m\n" in s or b" m " in s or b" l\n" in s:
            ops += s + b"\n"
    rings: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for line in ops.decode("latin-1").splitlines():
        parts = line.strip().split()
        if len(parts) == 3 and parts[2] == "m":
            if len(cur) >= 3:
                rings.append(cur)
            cur = [(float(parts[0]), float(parts[1]))]
        elif len(parts) == 3 and parts[2] == "l":
            cur.append((float(parts[0]), float(parts[1])))
        elif parts and parts[0] == "h":
            if len(cur) >= 3:
                rings.append(cur)
            cur = []
    if len(cur) >= 3:
        rings.append(cur)
    mm = 25.4 / 72.0
    rings_mm = [[(x * mm, y * mm) for x, y in r] for r in rings]
    return _even_odd(rings_mm)


def compare(master, reimported, loop_centers: list[tuple[float, float]] | None = None) -> dict:
    """Dimensions, geometry count, holes, area, shape (symmetric difference),
    attachment holes. Translation-invariant (exports may place the origin
    differently); scale must match exactly."""
    master = _as_multi(master)
    re_ = _as_multi(reimported)
    checks = []
    ok = True
    if re_.is_empty:
        return {"status": "FAIL", "label": "EXPORT FIDELITY: FAIL", "checks": [{"check": "geometry_present", "status": "FAIL"}]}
    mb, rb = master.bounds, re_.bounds
    mw, mh = mb[2] - mb[0], mb[3] - mb[1]
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    dims_ok = abs(mw - rw) <= DIM_TOL_MM and abs(mh - rh) <= DIM_TOL_MM
    checks.append({"check": "dimensions_mm", "status": "PASS" if dims_ok else "FAIL",
                   "master": [round(mw, 3), round(mh, 3)], "export": [round(rw, 3), round(rh, 3)]})
    ok &= dims_ok
    # align by bounding-box origin for the shape comparison
    from shapely import affinity

    aligned = affinity.translate(re_, xoff=mb[0] - rb[0], yoff=mb[1] - rb[1])
    count_ok = len(master.geoms) == len(aligned.geoms)
    checks.append({"check": "component_count", "status": "PASS" if count_ok else "FAIL",
                   "master": len(master.geoms), "export": len(aligned.geoms)})
    ok &= count_ok
    mh_ = sum(len(p.interiors) for p in master.geoms)
    rh_ = sum(len(p.interiors) for p in aligned.geoms)
    holes_ok = mh_ == rh_
    checks.append({"check": "hole_count", "status": "PASS" if holes_ok else "FAIL", "master": mh_, "export": rh_})
    ok &= holes_ok
    area_ok = abs(master.area - aligned.area) <= AREA_TOL * max(master.area, 1e-9)
    checks.append({"check": "area_mm2", "status": "PASS" if area_ok else "FAIL",
                   "master": round(master.area, 3), "export": round(aligned.area, 3)})
    ok &= area_ok
    sym = master.symmetric_difference(aligned).area / max(master.area, 1e-9)
    shape_ok = sym <= SYMDIFF_TOL
    checks.append({"check": "shape_symmetric_difference", "status": "PASS" if shape_ok else "FAIL", "ratio": round(sym, 5)})
    ok &= shape_ok
    if loop_centers:
        holes = [Polygon(r) for p in aligned.geoms for r in p.interiors]
        att_ok = all(any(h.contains(Point(cx - 0 + (mb[0] - mb[0]), cy)) for h in holes) for cx, cy in loop_centers)
        checks.append({"check": "attachment_holes_present", "status": "PASS" if att_ok else "FAIL", "loops": len(loop_centers)})
        ok &= att_ok
    status = "PASS" if ok else "FAIL"
    return {"status": status, "label": f"EXPORT FIDELITY: {status}", "checks": checks}
