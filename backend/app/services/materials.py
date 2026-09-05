"""Material system + geometry-based weight report (MANUFACTURABILITY THIRD).

Weight is computed from the ACTUAL metal area (holes and counters already
subtracted by the polygon model) × thickness × density — never from a
bounding box."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MATERIALS_FILE = Path(__file__).resolve().parent.parent / "data" / "materials.json"


@lru_cache(maxsize=1)
def load_materials() -> dict:
    return json.loads(MATERIALS_FILE.read_text(encoding="utf-8"))["materials"]


def material(material_id: str) -> dict:
    mats = load_materials()
    if material_id not in mats:
        raise KeyError(f"Unknown material: {material_id}")
    return {"id": material_id, **mats[material_id]}


def weight_report(geom, material_id: str, thickness_mm: float | None = None,
                  target_g: float | None = None, tolerance_pct: float = 10.0) -> dict:
    """Area/volume/weight from the real geometry, target comparison and
    plain-language warnings."""
    m = material(material_id)
    t = thickness_mm or m["thickness_mm"]["nominal"]
    area_mm2 = float(geom.area) if geom is not None and not geom.is_empty else 0.0
    volume_mm3 = area_mm2 * t
    weight_g = volume_mm3 * m["density_g_cm3"] / 1000.0
    minx, miny, maxx, maxy = geom.bounds if area_mm2 else (0, 0, 0, 0)
    bbox_area = (maxx - minx) * (maxy - miny)
    warnings: list[dict] = []
    if not (m["thickness_mm"]["min"] <= t <= m["thickness_mm"]["max"]):
        warnings.append({"code": "THICKNESS_OUT_OF_RANGE",
                         "en": f"Thickness {t} mm is outside {m['label_en']}'s {m['thickness_mm']['min']}–{m['thickness_mm']['max']} mm range.",
                         "ar": f"السماكة {t} مم خارج نطاق {m['label_ar']} ({m['thickness_mm']['min']}–{m['thickness_mm']['max']} مم)."})
    if weight_g and weight_g < 0.3:
        warnings.append({"code": "UNREALISTICALLY_LIGHT", "en": "Estimated weight is under 0.3 g — check the geometry scale.",
                         "ar": "الوزن المقدّر أقل من 0.3 غ — تحقق من مقياس الرسم."})
    if weight_g > 80:
        warnings.append({"code": "UNREALISTICALLY_HEAVY", "en": "Estimated weight is over 80 g — not a wearable piece at this size/thickness.",
                         "ar": "الوزن المقدّر يتجاوز 80 غ — غير مناسب للارتداء بهذا الحجم/السماكة."})
    if not m.get("workshop_ready", True):
        warnings.append({"code": "VISUAL_PREVIEW_ONLY", "en": m.get("note", "Visual preview only."), "ar": m.get("note_ar", "معاينة بصرية فقط.")})
    out = {
        "material": {"id": m["id"], "label_en": m["label_en"], "label_ar": m["label_ar"], "density_g_cm3": m["density_g_cm3"],
                     "method": m["method"], "finishes": m["finishes"], "workshop_ready": m.get("workshop_ready", True)},
        "thickness_mm": t,
        "metal_area_mm2": round(area_mm2, 2),
        "bounding_box_area_mm2": round(bbox_area, 2),
        "fill_ratio": round(area_mm2 / bbox_area, 3) if bbox_area else 0.0,
        "volume_mm3": round(volume_mm3, 2),
        "estimated_weight_g": round(weight_g, 2),
        "basis": "ACTUAL_AREA_X_THICKNESS_X_DENSITY",
        "warnings": warnings,
    }
    if target_g:
        dev = (weight_g - target_g) / target_g * 100.0
        within = abs(dev) <= tolerance_pct
        out["target"] = {
            "target_weight_g": target_g, "tolerance_pct": tolerance_pct, "deviation_pct": round(dev, 1),
            "within_tolerance": within,
            "thickness_for_target_mm": round(target_g * 1000.0 / (area_mm2 * m["density_g_cm3"]), 2) if area_mm2 else None,
            "scale_for_target": round((target_g / weight_g) ** 0.5, 3) if weight_g else None,
        }
    return out
