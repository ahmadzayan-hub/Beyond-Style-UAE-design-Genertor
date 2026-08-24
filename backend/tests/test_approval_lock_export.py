"""Approval binding, immutable lock, export authorization, idempotency."""
import io
import threading

import ezdxf
import pytest
from sqlalchemy import select, text

from app.db import models as m
from app.db.base import session_factory
from app.exporters.dxf_exporter import ProductionExportBlocked
from app.services import design_service as svc
from tests.test_persistence_lifecycle import _full_flow


def _approve(session, version):
    return svc.approve_version(
        session, version.id,
        confirmed_text=version.immutable_source_text,
        source_text_sha256=version.source_text_sha256,
        geometry_hash=version.geometry_hash,
        approved_by="customer-1",
    )


def test_approve_exact_version_succeeds_and_locks(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    approval = _approve(db_session, v1)
    db_session.commit()
    db_session.refresh(v1)
    assert v1.status == "APPROVED_LOCKED"
    assert approval.status == "ACTIVE"
    assert len(approval.approval_hash) == 64
    assert approval.geometry_hash == v1.geometry_hash


def test_approval_with_wrong_text_or_hash_fails(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    with pytest.raises(svc.ApprovalRejected, match="does not match"):
        svc.approve_version(db_session, v1.id, "ميثه", v1.source_text_sha256,
                            v1.geometry_hash, "customer-1")
    with pytest.raises(svc.ApprovalRejected, match="hash mismatch"):
        svc.approve_version(db_session, v1.id, v1.immutable_source_text,
                            "0" * 64, v1.geometry_hash, "customer-1")
    with pytest.raises(svc.ApprovalRejected, match="Geometry hash"):
        svc.approve_version(db_session, v1.id, v1.immutable_source_text,
                            v1.source_text_sha256, "0" * 64, "customer-1")


def test_duplicate_approval_rejected(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    with pytest.raises(svc.ConflictError):
        _approve(db_session, v1)


def test_racing_approvals_only_one_wins(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    db_session.commit()
    results = []

    def worker():
        s = session_factory()()
        try:
            svc.approve_version(
                s, v1.id, v1.immutable_source_text,
                v1.source_text_sha256, v1.geometry_hash, "racer",
            )
            s.commit()
            results.append("ok")
        except (svc.ConflictError, Exception) as exc:
            s.rollback()
            results.append(type(exc).__name__)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 1, results


def test_approved_version_is_immutable(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    # Even a status rollback is refused by the DB trigger.
    with pytest.raises(Exception, match="illegal|immutable"):
        db_session.execute(
            text("UPDATE design_versions SET status = 'UNAPPROVED' WHERE id = :id"),
            {"id": str(v1.id)},
        )
        db_session.commit()
    db_session.rollback()
    # Approval hash can never be recycled/modified.
    with pytest.raises(Exception, match="immutable"):
        db_session.execute(
            text("UPDATE customer_approvals SET approval_hash = repeat('a', 64)"),
        )
        db_session.commit()
    db_session.rollback()


def test_edit_after_lock_creates_new_unapproved_version(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    v2 = svc.edit_version(db_session, v1.id, {"stroke_delta_mm": 0.4}, "post-lock edit", "designer")
    db_session.commit()
    db_session.refresh(v1)
    assert v1.status == "APPROVED_LOCKED"  # historical lock untouched
    assert v2.status == "UNAPPROVED" and v2.version_number == 2
    # New version cannot production-export without its own approval.
    with pytest.raises(ProductionExportBlocked):
        svc.export_version(db_session, v2.id, "dxf")


def test_text_change_invalidates_approvals(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    v2 = svc.change_source_text(db_session, v1.id, "مريم", confirmed=True, created_by="designer")
    db_session.commit()
    approval = db_session.execute(select(m.CustomerApproval)).scalars().one()
    assert approval.status == "INVALIDATED"
    assert v2.immutable_source_text == "مريم"
    types = [e.event_type for e in db_session.execute(select(m.DesignEvent)).scalars()]
    assert "APPROVAL_INVALIDATED" in types
    # Locked v1 still cannot be modified, and v2 cannot export unapproved.
    with pytest.raises(ProductionExportBlocked):
        svc.export_version(db_session, v2.id, "svg")


def test_unapproved_version_export_blocked(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    with pytest.raises(ProductionExportBlocked, match="not customer-approved"):
        svc.export_version(db_session, v1.id, "dxf")


def test_locked_version_exports_svg_dxf_with_records(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    svg, svg_rec = svc.export_version(db_session, v1.id, "svg")
    dxf, dxf_rec = svc.export_version(db_session, v1.id, "dxf")
    db_session.commit()
    assert svg.startswith("<svg") and "mm" in svg
    doc = ezdxf.read(io.StringIO(dxf))
    assert doc.header["$INSUNITS"] == 4
    assert dict(doc.header.custom_vars)["SOURCE_TEXT_SHA256"] == v1.source_text_sha256
    for rec in (svg_rec, dxf_rec):
        assert rec.kind == "production"
        assert len(rec.content_sha256) == 64
        assert rec.units == "mm"
        assert rec.width_mm > 0 and rec.height_mm > 0
        assert rec.validation_rules_version == v1.manufacturing_rules_version
    types = [e.event_type for e in db_session.execute(select(m.DesignEvent)).scalars()]
    assert types.count("PRODUCTION_EXPORT_CREATED") == 2


def test_export_idempotency_key(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    content1, rec1 = svc.export_version(db_session, v1.id, "dxf", idempotency_key="job-42")
    db_session.commit()
    content2, rec2 = svc.export_version(db_session, v1.id, "dxf", idempotency_key="job-42")
    assert rec2.id == rec1.id and content2 == ""  # replay, no new record
    exports = db_session.execute(select(m.ExportRecord)).scalars().all()
    assert len(exports) == 1
    # Same key for different export → conflict.
    with pytest.raises(svc.ConflictError):
        svc.export_version(db_session, v1.id, "svg", idempotency_key="job-42")


def test_export_hash_verification_guard(clean_tables, db_session):
    """If stored geometry no longer matches its hash, export must refuse.
    (Simulated via trigger bypass — superuser test-only path.)"""
    req, design, v1 = _full_flow(db_session)
    _approve(db_session, v1)
    db_session.commit()
    db_session.execute(text("SET session_replication_role = replica"))
    db_session.execute(
        text("UPDATE design_versions SET geometry_wkt = 'MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)))' WHERE id = :id"),
        {"id": str(v1.id)},
    )
    db_session.execute(text("SET session_replication_role = DEFAULT"))
    db_session.commit()
    db_session.expire_all()  # drop ORM cache so the tampered row is re-read
    with pytest.raises(ProductionExportBlocked, match="hash verification failed"):
        svc.export_version(db_session, v1.id, "dxf")
