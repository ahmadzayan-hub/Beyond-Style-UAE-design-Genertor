"""Workshop calibration kit — turn INDUSTRY_TYPICAL limits into measured ones.

The manufacturing rules (min stroke / gap / bridge / counter, engraving
line width) decide what a customer may approve. Until they are measured on
Beyond Style's own laser/engraver and metals they are labelled
INDUSTRY_TYPICAL_UNCALIBRATED. This module makes calibration a one-hour
workshop task:

  1. `build_coupon(profile)` → a flat test plate with GRADED features in
     real mm (bars, slots, bridges, counters, engraved lines), plus a
     manifest naming every feature and its nominal size. The workshop cuts
     and engraves it once.
  2. The operator records which features came out clean (results JSON).
  3. `calibrate(profile, manifest, results)` → the smallest clean size per
     feature class, plus a safety margin, becomes the new limit; the profile
     is stamped WORKSHOP_CALIBRATED with provenance (coupon hash, results
     hash, operator, date). Nothing is promoted without a results file.

Features are identified by tick marks engraved next to each one (1 tick =
first size, 2 ticks = second …) so no text shaping is needed on the coupon.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

#: Graded nominal sizes (mm), smallest → largest. Each class straddles the
#: industry-typical value so the coupon can both confirm and tighten it.
GRADES = {
    "stroke": [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 1.00],
    "gap": [0.25, 0.30, 0.40, 0.50, 0.60, 0.80],
    "bridge": [0.40, 0.50, 0.60, 0.80, 1.00, 1.20],
    "counter": [0.30, 0.40, 0.50, 0.60, 0.80, 1.00],
    "engrave_line": [0.10, 0.15, 0.20, 0.30, 0.40, 0.60],
}
#: Applied on top of the smallest CLEAN size: manufacturing varies run to
#: run, so the limit must sit above the best observed result.
SAFETY_MARGIN = 0.15
#: Map feature class → workshop rule field.
RULE_FIELD = {
    "stroke": "min_stroke_mm",
    "gap": "min_gap_mm",
    "bridge": "min_bridge_mm",
    "counter": "min_counter_mm",
}
ENGRAVE_RULE_FIELD = "min_engrave_line_mm"

_BAR_LEN = 8.0
_ROW_GAP = 3.0
_COL_W = 12.0


def _ticks(x: float, y: float, n: int) -> list[Polygon]:
    """n engraved tick marks (0.25 × 1.2 mm) starting at (x, y)."""
    return [box(x + i * 0.6, y, x + i * 0.6 + 0.25, y + 1.2) for i in range(n)]


def build_coupon(profile: dict) -> dict:
    """Returns {"cut": MultiPolygon, "engrave": MultiPolygon, "manifest": {...}}.
    The plate is CUT; bars/bridges are CUT islands, slots/counters are CUT
    holes, engraved lines are ENGRAVE marks. Units mm."""
    plate_w = _COL_W * 7 + 6
    plate_h = 5 * (_BAR_LEN + _ROW_GAP + 3.0) + 8
    plate = box(0, 0, plate_w, plate_h)
    holes: list[Polygon] = []
    islands: list[Polygon] = []
    engrave: list[Polygon] = []
    manifest: dict[str, dict] = {}
    y = 4.0

    # Row 1 — stroke bars: free-standing bars of graded width inside a slot.
    for i, w in enumerate(GRADES["stroke"]):
        x = 3 + i * _COL_W
        slot = box(x, y, x + 6.0, y + _BAR_LEN)          # pocket cut out …
        bar = box(x + 3.0 - w / 2, y, x + 3.0 + w / 2, y + _BAR_LEN)  # … leaving the bar
        holes.append(slot); islands.append(bar)
        engrave += _ticks(x, y + _BAR_LEN + 0.6, i + 1)
        manifest[f"stroke-{i + 1}"] = {"class": "stroke", "nominal_mm": w, "ticks": i + 1}
    y += _BAR_LEN + _ROW_GAP + 3.0

    # Row 2 — gaps: two solid tabs separated by a graded slot.
    for i, g in enumerate(GRADES["gap"]):
        x = 3 + i * _COL_W
        holes.append(box(x + 3.0 - g / 2, y, x + 3.0 + g / 2, y + _BAR_LEN))
        engrave += _ticks(x, y + _BAR_LEN + 0.6, i + 1)
        manifest[f"gap-{i + 1}"] = {"class": "gap", "nominal_mm": g, "ticks": i + 1}
    y += _BAR_LEN + _ROW_GAP + 3.0

    # Row 3 — bridges: a 2 mm square island held by a graded bridge.
    for i, b in enumerate(GRADES["bridge"]):
        x = 3 + i * _COL_W
        pocket = box(x, y, x + 7.0, y + _BAR_LEN)
        island = box(x + 2.5, y + 3.0, x + 4.5, y + 5.0)
        bridge = box(x + 3.5 - b / 2, y, x + 3.5 + b / 2, y + 3.0)
        holes.append(pocket); islands += [island, bridge]
        engrave += _ticks(x, y + _BAR_LEN + 0.6, i + 1)
        manifest[f"bridge-{i + 1}"] = {"class": "bridge", "nominal_mm": b, "ticks": i + 1}
    y += _BAR_LEN + _ROW_GAP + 3.0

    # Row 4 — counters: round-ish holes of graded diameter.
    for i, d in enumerate(GRADES["counter"]):
        x = 3 + i * _COL_W
        from shapely.geometry import Point

        holes.append(Point(x + 3.0, y + 3.0).buffer(d / 2, resolution=16))
        engrave += _ticks(x, y + _BAR_LEN + 0.6, i + 1)
        manifest[f"counter-{i + 1}"] = {"class": "counter", "nominal_mm": d, "ticks": i + 1}
    y += _BAR_LEN + _ROW_GAP + 3.0

    # Row 5 — engraved lines of graded width.
    for i, w in enumerate(GRADES["engrave_line"]):
        x = 3 + i * _COL_W
        engrave.append(box(x, y + 2.0, x + 6.0, y + 2.0 + w))
        engrave += _ticks(x, y + _BAR_LEN + 0.6, i + 1)
        manifest[f"engrave_line-{i + 1}"] = {"class": "engrave_line", "nominal_mm": w, "ticks": i + 1}

    cut = plate.difference(unary_union(holes))
    cut = unary_union([cut] + islands)
    cut = cut if cut.geom_type == "MultiPolygon" else MultiPolygon([cut])
    eng = MultiPolygon(engrave)
    manifest_meta = {
        "profile_name": profile["profile_name"],
        "material_thickness_mm": profile.get("material_thickness_mm"),
        "plate_mm": [round(plate_w, 2), round(plate_h, 2)],
        "grades": GRADES,
        "features": manifest,
    }
    return {"cut": cut, "engrave": eng, "manifest": manifest_meta}


def coupon_sha256(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def calibrate(profile: dict, manifest: dict, results: dict, operator: str, when: date | None = None) -> dict:
    """Derive measured limits from a results file.

    results = {"clean": ["stroke-3", "stroke-4", ...], "operator": ...}
    A feature class with NO clean result keeps its previous limit and is
    reported as UNRESOLVED (the coupon must be re-cut at larger sizes) —
    the profile is then NOT promoted to production.
    """
    features = manifest["features"]
    clean = set(results.get("clean", []))
    unknown = sorted(clean - set(features))
    if unknown:
        raise ValueError(f"Results reference features not on this coupon: {unknown}")

    new_profile = dict(profile)
    report: dict[str, dict] = {}
    unresolved = []
    for cls, grades in GRADES.items():
        clean_sizes = sorted(
            f["nominal_mm"] for fid, f in features.items() if f["class"] == cls and fid in clean
        )
        if not clean_sizes:
            unresolved.append(cls)
            report[cls] = {"status": "UNRESOLVED", "clean_sizes": []}
            continue
        smallest = clean_sizes[0]
        limit = round(smallest * (1 + SAFETY_MARGIN), 2)
        field = RULE_FIELD.get(cls, ENGRAVE_RULE_FIELD)
        report[cls] = {
            "status": "MEASURED",
            "smallest_clean_mm": smallest,
            "limit_mm": limit,
            "previous_mm": profile.get(field),
            "field": field,
        }
        new_profile[field] = limit

    promoted = not unresolved
    new_profile["calibration_status"] = (
        f"WORKSHOP_CALIBRATED_{(when or date.today()).isoformat()}" if promoted
        else "CALIBRATION_INCOMPLETE"
    )
    new_profile["is_production_profile"] = promoted
    new_profile["calibration"] = {
        "coupon_sha256": coupon_sha256(manifest),
        "results_sha256": hashlib.sha256(json.dumps(results, sort_keys=True).encode()).hexdigest(),
        "operator": operator,
        "date": (when or date.today()).isoformat(),
        "safety_margin": SAFETY_MARGIN,
        "unresolved": unresolved,
    }
    return {"profile": new_profile, "report": report, "promoted": promoted}


# ---------------------------------------------------------------- persistence

def profiles_path():
    from ..config import workshop_profiles_path

    return workshop_profiles_path()


def write_profile(product: str, material: str, new_profile: dict) -> dict:
    """Replace one product×material profile with its calibrated version and
    bump profiles_version (minor). Returns {path, profiles_version}. The
    running process keeps the rules it loaded at start-up (DEFAULT_RULES);
    a restart picks the new file up — the caller reports that honestly."""
    import json

    path = profiles_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    replaced = False
    for i, p in enumerate(data["profiles"]):
        if p["product"] == product and p["material"] == material:
            data["profiles"][i] = new_profile
            replaced = True
    if not replaced:
        raise KeyError(f"no profile for {product}/{material}")
    major, minor, _patch = data["profiles_version"].split(".")
    data["profiles_version"] = f"{major}.{int(minor) + 1}.0"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"path": str(path), "profiles_version": data["profiles_version"]}


def coupon_svg(cut, engrave, w: float, h: float, manifest: dict) -> str:
    """Dimensioned calibration coupon as SVG (mm), same renderer for the CLI
    and the admin API."""
    import json

    from ..exporters.svg_exporter import geometry_to_path_d

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
        f'<metadata>{json.dumps({"calibration_coupon": True, "profile": manifest["profile_name"], "units": "mm"})}</metadata>\n'
        f'<path d="{geometry_to_path_d(cut, flip_y=h)}" fill="#1a1a1a" fill-rule="evenodd"/>\n'
        f'<path d="{geometry_to_path_d(engrave, flip_y=h)}" fill="#f5efe2" fill-rule="evenodd"/>\n'
        "</svg>\n"
    )


def coupon_dxf(cut, engrave) -> str:
    import io

    import ezdxf

    doc = ezdxf.new("R2010", setup=False)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("CUT", color=1); doc.layers.add("HOLES", color=5); doc.layers.add("ENGRAVE", color=3)
    msp = doc.modelspace()
    for poly in cut.geoms:
        msp.add_lwpolyline(list(poly.exterior.coords), close=True, dxfattribs={"layer": "CUT"})
        for ring in poly.interiors:
            msp.add_lwpolyline(list(ring.coords), close=True, dxfattribs={"layer": "HOLES"})
    for poly in engrave.geoms:
        msp.add_lwpolyline(list(poly.exterior.coords), close=True, dxfattribs={"layer": "ENGRAVE"})
    buf = io.StringIO(); doc.write(buf); return buf.getvalue()
