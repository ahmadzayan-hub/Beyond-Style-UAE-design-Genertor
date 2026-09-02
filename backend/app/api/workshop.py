"""Workshop OS API — staff only (admin role). State machine + production pack."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import models as m
from ..db.base import get_session
from ..services import workshop_service as ws
from .admin import require_admin

router = APIRouter(prefix="/api/workshop", tags=["workshop"], dependencies=[Depends(require_admin)])


class CreateOrder(BaseModel):
    version_id: str
    material: str = Field(pattern=r"^[a-z0-9\-]+$")
    notes: str | None = None
    actor: str = "workshop_admin"


class Transition(BaseModel):
    to_state: str
    actor: str = "workshop_staff"
    note: str | None = None
    receiver_name: str | None = None
    staff_number: str | None = None
    actual_received_date: date | None = None


def _order(session: Session, order_id: str) -> m.WorkshopOrder:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(404, "Order not found.")
    order = session.get(m.WorkshopOrder, oid)
    if order is None:
        raise HTTPException(404, "Order not found.")
    return order


def _view(o: m.WorkshopOrder) -> dict:
    return {
        "order_id": str(o.id), "state": o.state, "material": o.material,
        "design_version_id": str(o.design_version_id), "approval_hash": o.approval_hash,
        "rework_count": o.rework_count, "receiver_name": o.receiver_name,
        "staff_number": o.staff_number,
        "actual_received_date": o.actual_received_date.isoformat() if o.actual_received_date else None,
        "history": o.history or [], "allowed_next": sorted(ws.TRANSITIONS[o.state]),
        "created_at": o.created_at.isoformat(),
    }


@router.get("/states")
def states():
    return {"states": ws.STATES, "transitions": {k: sorted(v) for k, v in ws.TRANSITIONS.items()},
            "delivery_fields": list(ws.DELIVERY_FIELDS)}


@router.post("/orders", status_code=201)
def create_order(body: CreateOrder, session: Session = Depends(get_session)):
    try:
        order = ws.create_order(session, uuid.UUID(body.version_id), material=body.material,
                                actor=body.actor, notes=body.notes)
    except (KeyError, ValueError):
        raise HTTPException(404, "Version not found.")
    except ws.WorkshopError as exc:
        raise HTTPException(409, str(exc))
    return _view(order)


@router.get("/orders")
def list_orders(session: Session = Depends(get_session)):
    return {"orders": [_view(o) for o in ws.list_orders(session)]}


@router.get("/orders/{order_id}")
def get_order(order_id: str, session: Session = Depends(get_session)):
    return _view(_order(session, order_id))


@router.post("/orders/{order_id}/transition")
def transition(order_id: str, body: Transition, session: Session = Depends(get_session)):
    order = _order(session, order_id)
    try:
        ws.transition(session, order, body.to_state, actor=body.actor, note=body.note,
                      receiver_name=body.receiver_name, staff_number=body.staff_number,
                      actual_received_date=body.actual_received_date)
    except ws.WorkshopError as exc:
        raise HTTPException(409, str(exc))
    return _view(order)


@router.get("/orders/{order_id}/production-pack")
def get_production_pack(order_id: str, session: Session = Depends(get_session)):
    order = _order(session, order_id)
    try:
        return ws.production_pack(session, order)
    except Exception as exc:  # export path raises on lock/hash failure — surface, never fake
        raise HTTPException(409, f"Production pack unavailable: {type(exc).__name__}: {exc}")
