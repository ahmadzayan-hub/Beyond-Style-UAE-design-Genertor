"""Workshop OS — order state machine + production pack.

State machine (charter): New → Design Review → Technical Check → Approved
→ Manufacturing → QC → Rework? → Ready → Delivered. Required states are
never skipped; Rework loops back to Manufacturing; Delivered demands the
receiver name, staff number and actual received date. Every transition is
an append-only audit event and also kept in the order's own history.

A workshop order can only be opened on an APPROVED_LOCKED design version
with an ACTIVE customer approval — the production pack it carries is the
customer-agreed artifact, hash-bound, never a draft.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import models as m
from . import design_service as svc

STATES = [
    "NEW", "DESIGN_REVIEW", "TECHNICAL_CHECK", "APPROVED", "MANUFACTURING",
    "QC", "REWORK", "READY", "DELIVERED",
]
#: Allowed forward moves. QC may fail into REWORK; REWORK returns to
#: MANUFACTURING. No state may be skipped.
TRANSITIONS = {
    "NEW": {"DESIGN_REVIEW"},
    "DESIGN_REVIEW": {"TECHNICAL_CHECK"},
    "TECHNICAL_CHECK": {"APPROVED"},
    "APPROVED": {"MANUFACTURING"},
    "MANUFACTURING": {"QC"},
    "QC": {"READY", "REWORK"},
    "REWORK": {"MANUFACTURING"},
    "READY": {"DELIVERED"},
    "DELIVERED": set(),
}
DELIVERY_FIELDS = ("receiver_name", "staff_number", "actual_received_date")


class WorkshopError(Exception):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def create_order(session: Session, version_id: uuid.UUID, *, material: str, actor: str,
                 notes: str | None = None) -> m.WorkshopOrder:
    version = session.get(m.DesignVersion, version_id)
    if version is None:
        raise KeyError("version not found")
    if version.status != "APPROVED_LOCKED":
        raise WorkshopError("Only an APPROVED_LOCKED version can enter the workshop.")
    approval = session.execute(
        select(m.CustomerApproval).where(
            m.CustomerApproval.design_version_id == version.id,
            m.CustomerApproval.status == "ACTIVE",
        )
    ).scalar_one_or_none()
    if approval is None:
        raise WorkshopError("No active customer approval for this version.")
    existing = session.execute(
        select(m.WorkshopOrder).where(m.WorkshopOrder.design_version_id == version.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise WorkshopError("A workshop order already exists for this version.")

    order = m.WorkshopOrder(
        design_version_id=version.id,
        approval_id=approval.id,
        approval_hash=approval.approval_hash,
        state="NEW",
        material=material,
        notes=notes,
        history=[{"state": "NEW", "actor": actor, "at": _utcnow().isoformat(), "note": notes}],
        created_by=actor,
    )
    session.add(order)
    session.flush()
    svc._emit(session, "WORKSHOP_ORDER_CREATED", design_id=version.design_id, version_id=version.id,
              actor=actor, actor_type="staff",
              metadata={"order_id": str(order.id), "approval_hash": approval.approval_hash,
                        "material": material})
    return order


def transition(session: Session, order: m.WorkshopOrder, to_state: str, *, actor: str,
               note: str | None = None, receiver_name: str | None = None,
               staff_number: str | None = None,
               actual_received_date: date | None = None) -> m.WorkshopOrder:
    if to_state not in STATES:
        raise WorkshopError(f"Unknown state {to_state}.")
    if to_state not in TRANSITIONS[order.state]:
        raise WorkshopError(f"Illegal transition {order.state} → {to_state}.")
    if to_state == "DELIVERED":
        missing = [f for f, v in (("receiver_name", receiver_name), ("staff_number", staff_number),
                                  ("actual_received_date", actual_received_date)) if not v]
        if missing:
            raise WorkshopError(f"Delivery requires {', '.join(DELIVERY_FIELDS)}; missing: {missing}.")
        order.receiver_name = receiver_name
        order.staff_number = staff_number
        order.actual_received_date = actual_received_date
        order.delivered_at = _utcnow()
    if to_state == "REWORK":
        order.rework_count = (order.rework_count or 0) + 1

    # Re-verify the approval lock at every step: a design edited after
    # approval must never be manufactured.
    version = session.get(m.DesignVersion, order.design_version_id)
    approval = session.get(m.CustomerApproval, order.approval_id)
    if version.status != "APPROVED_LOCKED" or approval.status != "ACTIVE" \
            or approval.approval_hash != order.approval_hash:
        raise WorkshopError("Approval no longer valid for this order — stop production.")

    previous = order.state
    order.state = to_state
    order.history = list(order.history or []) + [
        {"state": to_state, "from": previous, "actor": actor, "at": _utcnow().isoformat(), "note": note}
    ]
    session.flush()
    svc._emit(session, "WORKSHOP_STATE_CHANGED", design_id=version.design_id, version_id=version.id,
              actor=actor, actor_type="staff",
              metadata={"order_id": str(order.id), "from": previous, "to": to_state, "note": note})
    return order


def production_pack(session: Session, order: m.WorkshopOrder) -> dict:
    """Everything the bench needs, bound to the approved hash. Vector
    artifacts come from the authorized production export path (lock +
    hash re-verification); nothing here is regenerated or estimated
    beyond the labelled weight estimate."""
    from .mesh3d import mesh3d_payload

    version = session.get(m.DesignVersion, order.design_version_id)
    approval = session.get(m.CustomerApproval, order.approval_id)
    design = session.get(m.Design, version.design_id)
    req = session.get(m.DesignRequest, design.request_id)
    product_type = req.product_type if req else "pendant"

    svg, svg_rec = svc.export_version(session, version.id, "svg",
                                      idempotency_key=f"pack-svg-{order.id}", actor="workshop")
    dxf, dxf_rec = svc.export_version(session, version.id, "dxf",
                                      idempotency_key=f"pack-dxf-{order.id}", actor="workshop")
    mesh = mesh3d_payload(version, product_type)
    validation = version.validation or {}
    recipe = version.recipe or {}
    # Tolerances come from the rules the validator actually ran with (the
    # persisted validation run), never from a re-read of today's profile.
    run = session.execute(
        select(m.ManufacturingValidationRun)
        .where(m.ManufacturingValidationRun.version_id == version.id)
        .order_by(m.ManufacturingValidationRun.created_at.desc())
    ).scalars().first()
    rules = (run.rules_snapshot if run else None) or validation.get("rules_snapshot") or {}
    ring = recipe.get("ring")

    process = ["laser_cut_sheet", "finish", "polish"]
    if ring:
        process = ["cut_flat_strip", "engrave_outer_face"]
        if version.inner_text_geometry_wkt:
            process.append("engrave_inner_face_mirrored")
        process += ["roll_and_solder", "finish", "polish"]
    elif recipe.get("loops", "none") != "none":
        process.append("attach_bail_or_jump_rings")

    bom = [{"item": f"{order.material} sheet/strip", "thickness_mm": mesh["thickness_mm"],
            "estimated_metal_weight_g": mesh["weight_estimate_g"].get(order.material),
            "weight_basis": mesh["weight_basis"]}]
    from ..engines.generator import EXPECTED_LOOPS
    loops = EXPECTED_LOOPS.get(recipe.get("loops", "none"), 0)
    if loops:
        bom.append({"item": "jump_ring", "qty": loops, "note": "size per workshop standard"})

    warnings = [v for v in validation.get("violations", []) if v.get("severity") == "WARNING"]
    return {
        "order_id": str(order.id),
        "state": order.state,
        "approval_hash": approval.approval_hash,
        "approved_at": approval.approved_at.isoformat(),
        "exact_text": version.immutable_source_text,
        "source_text_sha256": version.source_text_sha256,
        "geometry_hash": version.geometry_hash,
        "version_number": version.version_number,
        "product_type": product_type,
        "material": order.material,
        "dimensions_mm": {"width": mesh["width_mm"], "height": mesh["height_mm"],
                          "thickness": mesh["thickness_mm"], "ring": mesh["ring"]},
        "process": process,
        "bom": bom,
        "tolerances": {k: rules.get(k) for k in ("kerf_mm", "min_stroke_mm", "min_gap_mm",
                                                  "min_bridge_mm", "min_counter_mm")},
        "rules_profile": (run.rules_profile if run else None) or validation.get("rules_profile"),
        "rules_version": run.rules_version if run else None,
        "warnings": warnings,
        "manufacturing_score": version.manufacturing_score,
        "font_id": version.font_id,
        "artifacts": {
            "svg": {"content": svg or None, "sha256": svg_rec.content_sha256, "export_id": str(svg_rec.id)},
            "dxf": {"content": dxf or None, "sha256": dxf_rec.content_sha256, "export_id": str(dxf_rec.id)},
        },
        "history": order.history,
    }


def list_orders(session: Session) -> list[m.WorkshopOrder]:
    return session.execute(select(m.WorkshopOrder).order_by(m.WorkshopOrder.created_at.desc())).scalars().all()
