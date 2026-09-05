"""Version readiness ladder — derived from recorded facts, never declared.

Draft → Text Verified → Design Reviewed → Jewelry Verified → Customer
Ready → Customer Approved → Workshop Ready → Manufacturing Released.
Each rung reports reached/blocked with the reason in plain language.
Customer approval through this UI is INTERNAL (no secure customer link is
implemented) and is labelled as such."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from ..engines.text_integrity import certify

STATES = ["DRAFT", "TEXT_VERIFIED", "DESIGN_REVIEWED", "JEWELRY_VERIFIED", "CUSTOMER_READY",
          "CUSTOMER_APPROVED", "WORKSHOP_READY", "MANUFACTURING_RELEASED"]
LABELS_AR = {"DRAFT": "مسودة", "TEXT_VERIFIED": "النص مُتحقق", "DESIGN_REVIEWED": "روجع التصميم",
             "JEWELRY_VERIFIED": "فحص المجوهرات ناجح", "CUSTOMER_READY": "جاهز للعميل",
             "CUSTOMER_APPROVED": "اعتمده العميل", "WORKSHOP_READY": "جاهز للورشة",
             "MANUFACTURING_RELEASED": "أُفرج للتصنيع"}


def ladder(session: Session, version: m.DesignVersion) -> dict:
    from . import design_service as svc

    design = session.get(m.Design, version.design_id)
    req = session.get(m.DesignRequest, design.request_id) if design else None
    candidate, source = svc._version_to_candidate(version)
    integrity = certify(source.normalized_text, source.sha256, candidate.identity_proof, [],
                        carried_text=version.immutable_source_text)
    approval = session.execute(
        select(m.CustomerApproval).where(m.CustomerApproval.design_version_id == version.id,
                                         m.CustomerApproval.status == "ACTIVE")
    ).scalar_one_or_none()
    exports = session.execute(select(m.ExportRecord).where(m.ExportRecord.version_id == version.id)).scalars().all()
    fid_ok = {e.format: (e.fidelity or {}).get("status") == "PASS" for e in exports}
    order = session.execute(select(m.WorkshopOrder).where(m.WorkshopOrder.design_version_id == version.id)).scalar_one_or_none()
    # Designer review rows are keyed by the deterministic review-item id of
    # the combination (font, feature set, axes, product, composition, text);
    # derive it from this version's recipe so a recorded human review of the
    # same combination counts, and a version never reviewed simply has none.
    from .review_workflow import item_id as review_item_id

    recipe = candidate.recipe
    product = (req.product_type if req and req.product_type else None) or (design.product_type if design else "pendant")
    reviewed = session.execute(
        select(m.DesignReview).where(m.DesignReview.item_id == review_item_id(
            recipe.font_id, recipe.ot_feature_set, recipe.font_axes, product, recipe.composition,
            version.immutable_source_text))
    ).first() is not None

    rungs = []
    def rung(state, reached, why_en, why_ar, extra=None):
        rungs.append({"state": state, "label_ar": LABELS_AR[state], "reached": bool(reached),
                      "reason_en": why_en, "reason_ar": why_ar, **(extra or {})})
        return bool(reached)

    ok = rung("DRAFT", True, "Version exists.", "النسخة موجودة.")
    text_ok = bool(req and req.confirmed) and integrity["status"] == "PASS"
    ok = rung("TEXT_VERIFIED", ok and text_ok,
              "Exact text confirmed by the customer and TEXT INTEGRITY: PASS." if text_ok else
              "The text has not been confirmed, or integrity failed.",
              "أكّد العميل النص بالضبط وسلامة النص: ناجحة." if text_ok else "لم يُؤكد النص أو فشلت سلامته.",
              {"text_integrity": integrity["label"]})
    ok = rung("DESIGN_REVIEWED", ok and (reviewed or bool(version.validation_passed)),
              "Recorded designer review." if reviewed else "No designer review recorded — automatic checks only (internal).",
              "روجع من مصمم." if reviewed else "لا توجد مراجعة مصمم مسجلة — فحوص آلية فقط (داخلي).",
              {"designer_review_recorded": reviewed})
    jq = bool(version.validation_passed) and bool(version.identity_verified)
    ok = rung("JEWELRY_VERIFIED", ok and jq, "JEWELRY QA: PASS." if jq else "JEWELRY QA: FAIL — see the QA report.",
              "فحص المجوهرات: ناجح." if jq else "فحص المجوهرات: فاشل — راجع تقرير الفحص.")
    ok = rung("CUSTOMER_READY", ok, "Dimensioned agreement proof available." if ok else "Blocked by an earlier step.",
              "إثبات الاتفاق بالأبعاد متاح." if ok else "متوقف بسبب خطوة سابقة.")
    appr = approval is not None and approval.geometry_hash == version.geometry_hash
    secure = appr and approval.approval_method == "SECURE_LINK"
    channel = ("SECURE_LINK" if secure else "INTERNAL_UI") if appr else None
    ok = rung("CUSTOMER_APPROVED", ok and appr,
              (f"Approved {approval.approved_at.isoformat()} by {approval.approved_by} through the secure customer link."
               if secure else
               f"Approved {approval.approved_at.isoformat()} by {approval.approved_by} via {approval.approval_method} "
               f"(INTERNAL approval — recorded in the studio UI, not through a customer link).") if appr
              else "No active approval bound to this version.",
              ("اعتماد العميل عبر الرابط الآمن." if secure else "اعتماد داخلي مسجّل من واجهة الاستوديو (ليس عبر رابط العميل).") if appr
              else "لا يوجد اعتماد نشط لهذه النسخة.",
              {"approval_hash": approval.approval_hash if appr else None, "approval_channel": channel})
    ws = ok and fid_ok.get("svg") and fid_ok.get("dxf")
    ok = rung("WORKSHOP_READY", ws,
              "SVG and DXF exported and EXPORT FIDELITY: PASS." if ws else
              "Needs SVG and DXF exports that pass the fidelity gate" + (f" (have: {', '.join(sorted(fid_ok))})." if fid_ok else "."),
              "صُدّر SVG وDXF واجتازا بوابة المطابقة." if ws else "يلزم تصدير SVG وDXF بنجاح عبر بوابة المطابقة.",
              {"exports": {e.format: (e.fidelity or {}).get("status") for e in exports}})
    rel = ok and order is not None and order.state in ("APPROVED", "MANUFACTURING", "QC", "REWORK", "READY", "DELIVERED")
    rung("MANUFACTURING_RELEASED", rel,
         f"Workshop order in state {order.state}." if order else "No workshop order.",
         f"طلب الورشة في حالة {order.state}." if order else "لا يوجد طلب ورشة.")
    current = [r["state"] for r in rungs if r["reached"]][-1]
    return {"current_state": current, "current_label_ar": LABELS_AR[current], "rungs": rungs,
            "approval_channel_note": "INTERNAL_UI approvals are recorded in the studio; SECURE_LINK approvals come from the single-use customer link (POST /api/versions/{id}/approval-link)."}
