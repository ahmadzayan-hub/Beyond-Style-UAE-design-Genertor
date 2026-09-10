"""JEWELRY QA — the manufacturing gate report in plain language.

Wraps the deterministic validator (never re-decides it) and adds the
weight report and attachment facts, with AR/EN explanations a customer
can understand. Label: JEWELRY QA: PASS / FAIL."""
from __future__ import annotations

from shapely import wkt as shapely_wkt

from ..engines.generator import EXPECTED_LOOPS
from .materials import weight_report

EXPLAIN = {
    "DISCONNECTED_COMPONENT": ("A part of the design is not joined to the rest and would fall off after cutting.",
                               "جزء من التصميم غير متصل بالباقي وسيسقط بعد القص."),
    "FLOATING_ISLAND": ("A separate piece (often a dot) is floating with no metal joining it.",
                        "قطعة منفصلة (غالبًا نقطة) عائمة بلا معدن يربطها."),
    "THIN_STROKE": ("A stroke is thinner than the workshop can cut safely.", "هناك خط أرفع مما يمكن للورشة قصّه بأمان."),
    "GAP_TOO_SMALL": ("An opening is narrower than the cutting beam allows; it would fuse or tear.",
                      "هناك فتحة أضيق مما يسمح به شعاع القص؛ ستلتحم أو تتمزق."),
    "WEAK_BRIDGE": ("A neck between two parts is too narrow and could break.", "عنق بين جزأين ضيق جدًا وقد ينكسر."),
    "OPEN_PATH": ("A contour is not closed, so it cannot be cut.", "مسار غير مغلق ولا يمكن قصّه."),
    "UNSAFE_LOOP": ("The chain ring is missing, blocked, or its hole is too small for the chain.",
                    "حلقة السلسلة مفقودة أو مسدودة أو ثقبها أصغر من السلسلة."),
    "OVERSIZE": ("The piece is larger or more slender than this product allows.", "القطعة أكبر أو أنحف مما يسمح به هذا المنتج."),
    "TEXT_IDENTITY_UNVERIFIED": ("The letters could not be proven to match the confirmed text exactly.",
                                 "تعذر إثبات مطابقة الحروف للنص المؤكد تمامًا."),
}


def _explain(code: str) -> tuple[str, str]:
    return EXPLAIN.get(code, (code.replace("_", " ").capitalize() + ".", code))


def _calibration_status(rules_profile: str | None) -> str | None:
    """Honest provenance of the limits used: INDUSTRY_TYPICAL_UNCALIBRATED
    until a real coupon from Beyond Style's workshop pins the profile."""
    if not rules_profile:
        return None
    from ..config import load_workshop_profiles

    name = rules_profile.split("@")[0]
    for p in load_workshop_profiles()["profiles"]:
        if p.get("profile_name") == name:
            return p.get("calibration_status")
    return None


def jewelry_qa_report(version, *, material_id: str | None = None, thickness_mm: float | None = None,
                      target_weight_g: float | None = None) -> dict:
    validation = version.validation or {}
    violations = validation.get("violations") or []
    errors, warnings = [], []
    for v in violations:
        code = v.get("code")
        en, ar = _explain(code)
        entry = {"code": code, "severity": v.get("severity"), "detail": v.get("detail"),
                 "explanation_en": en, "explanation_ar": ar, "location_mm": v.get("location_mm"),
                 "proposed_fix": v.get("proposed_fix")}
        (warnings if v.get("severity") == "WARNING" else errors).append(entry)
    geom = shapely_wkt.loads(version.geometry_wkt) if version.geometry_wkt else None
    material_id = material_id or "silver-925"
    weight = weight_report(geom, material_id, thickness_mm, target_g=target_weight_g) if geom is not None else None
    recipe = version.recipe or {}
    loops = recipe.get("loops", "none")
    attachment = {
        "mode": loops,
        "expected_rings": EXPECTED_LOOPS.get(loops, 0),
        "real_geometry": loops != "none",
        "note_en": "Attachment rings are cut metal fused to the piece — not markers." if loops != "none"
        else "No attachment on this piece (bracelet plates/keychains add theirs at assembly).",
        "note_ar": "حلقات التعليق معدن مقصوص ملتحم بالقطعة — ليست علامات." if loops != "none"
        else "لا تعليق في هذه القطعة (تُضاف عند التجميع لبعض المنتجات).",
    }
    passed = bool(version.validation_passed) and not errors and bool(version.identity_verified)
    status = "PASS" if passed else "FAIL"
    summary_en = ("Ready for the workshop: every stroke, bridge, gap and ring passes the material's limits."
                  if passed else f"{len(errors)} issue(s) must be fixed before the workshop can cut this piece.")
    summary_ar = ("جاهز للورشة: كل خط وجسر وفتحة وحلقة ضمن حدود الخامة." if passed
                  else f"يجب إصلاح {len(errors)} مشكلة قبل أن تتمكن الورشة من قصّ القطعة.")
    return {
        "status": status, "label": f"JEWELRY QA: {status}",
        "summary_en": summary_en, "summary_ar": summary_ar,
        "text_identity_verified": bool(version.identity_verified),
        "rules_profile": validation.get("rules_profile"),
        "calibration_status": _calibration_status(validation.get("rules_profile")),
        "measurements": validation.get("measurements"),
        "errors": errors, "warnings": warnings,
        "attachment": attachment,
        "weight": weight,
        "material_note_en": (weight or {}).get("material", {}).get("label_en") if weight else None,
    }
