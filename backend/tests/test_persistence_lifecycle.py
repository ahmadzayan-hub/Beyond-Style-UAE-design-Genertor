"""PostgreSQL integration: migrations, persistence, versioning, immutability."""
import uuid

import pytest
from alembic import command
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app.db import models as m
from app.services import design_service as svc


def _full_flow(session, text_value="ميثة"):
    req = svc.create_request(session, text_value, "pendant")
    svc.confirm_request_text(session, req.id, text_value)
    result = svc.generate_and_persist_candidates(session, req.id)
    top = result["top"]
    design, version = svc.select_candidate(session, req.id, top[0].candidate_id)
    session.commit()
    return req, design, version


def test_migration_cycle(migrated_db):
    """Real Alembic downgrade base → upgrade head twice (integrity)."""
    command.downgrade(migrated_db, "base")
    command.upgrade(migrated_db, "head")


def test_request_and_candidates_persist(clean_tables, db_session):
    req, design, version = _full_flow(db_session)
    stored = db_session.get(m.DesignRequest, req.id)
    assert stored.source_text_normalized == "ميثة"
    assert stored.status == "CANDIDATES_GENERATED"
    count = db_session.execute(
        select(m.DesignCandidateRow).where(m.DesignCandidateRow.request_id == req.id)
    ).scalars().all()
    assert len(count) >= 30
    ranked = [c for c in count if c.diversity_rank is not None]
    assert len(ranked) == 10
    for c in count:
        assert c.ranking_config_version == "0.1.0"
        assert c.score_breakdown["dimensions"]["arabic_integrity"]["weight"] == 30.0
        # Heuristic dimensions are explicitly labelled.
        assert "HEURISTIC" in c.score_breakdown["dimensions"]["visual_quality"]["basis"]


def test_candidate_regeneration_is_idempotent(clean_tables, db_session):
    req = svc.create_request(db_session, "مريم", "pendant")
    svc.confirm_request_text(db_session, req.id, "مريم")
    svc.generate_and_persist_candidates(db_session, req.id)
    db_session.commit()
    n1 = len(db_session.execute(select(m.DesignCandidateRow)).scalars().all())
    svc.generate_and_persist_candidates(db_session, req.id)  # rerun
    db_session.commit()
    n2 = len(db_session.execute(select(m.DesignCandidateRow)).scalars().all())
    assert n1 == n2  # deterministic keys → no duplicates


def test_version_numbers_sequential_and_unique(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    v2 = svc.edit_version(db_session, v1.id, {"stroke_delta_mm": 0.35}, "thicken", "designer-a")
    v3 = svc.edit_version(db_session, v2.id, {"letter_spacing_mm": 0.4}, None, "designer-a")
    db_session.commit()
    assert (v1.version_number, v2.version_number, v3.version_number) == (1, 2, 3)
    assert v2.parent_version_id == v1.id and v3.parent_version_id == v2.id
    # Duplicate version number rejected by DB constraint.
    dup = m.DesignVersion(
        design_id=design.id, version_number=1, status="UNAPPROVED",
        immutable_source_text=v1.immutable_source_text,
        source_text_sha256=v1.source_text_sha256,
        geometry_wkt=v1.geometry_wkt, geometry_hash=v1.geometry_hash,
        schema_version="0.1.0", arabic_engine_version="0.1.0",
        font_id=v1.font_id, font_version=v1.font_version,
        recipe_id=v1.recipe_id, recipe_version=v1.recipe_version,
        recipe=v1.recipe, manufacturing_rules_version=v1.manufacturing_rules_version,
        validation=v1.validation, validation_passed=True, identity_verified=True,
        created_by="test",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_source_text_unchanged_across_geometry_edits(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session, "لؤي")
    v2 = svc.edit_version(db_session, v1.id, {"composition": "plate_rect"}, None, "designer")
    db_session.commit()
    assert v2.immutable_source_text == v1.immutable_source_text == "لؤي"
    assert v2.source_text_sha256 == v1.source_text_sha256
    assert v2.geometry_hash != v1.geometry_hash  # geometry did change


def test_edit_cannot_touch_source_text_fields(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    with pytest.raises(svc.ApprovalRejected):
        svc.edit_version(db_session, v1.id, {"immutable_source_text": "غير"}, None, "designer")


def test_historical_versions_cannot_be_overwritten(clean_tables, db_session):
    """DB trigger rejects UPDATEs to version content — even raw SQL."""
    req, design, v1 = _full_flow(db_session)
    with pytest.raises((OperationalError, ProgrammingError, Exception)) as exc:
        db_session.execute(
            text("UPDATE design_versions SET geometry_wkt = 'POLYGON EMPTY' WHERE id = :id"),
            {"id": str(v1.id)},
        )
        db_session.commit()
    assert "immutable" in str(exc.value)
    db_session.rollback()
    with pytest.raises(Exception) as exc2:
        db_session.execute(
            text("UPDATE design_versions SET immutable_source_text = 'هکر' WHERE id = :id"),
            {"id": str(v1.id)},
        )
        db_session.commit()
    assert "immutable" in str(exc2.value)
    db_session.rollback()


def test_versions_cannot_be_deleted(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    with pytest.raises(Exception) as exc:
        db_session.execute(
            text("DELETE FROM design_versions WHERE id = :id"), {"id": str(v1.id)}
        )
        db_session.commit()
    assert "append-only" in str(exc.value)
    db_session.rollback()


def test_audit_events_record_lifecycle(clean_tables, db_session):
    req, design, v1 = _full_flow(db_session)
    svc.approve_version(
        db_session, v1.id,
        confirmed_text=v1.immutable_source_text,
        source_text_sha256=v1.source_text_sha256,
        geometry_hash=v1.geometry_hash,
        approved_by="customer-1",
    )
    db_session.commit()
    types = [
        r.event_type
        for r in db_session.execute(
            select(m.DesignEvent).order_by(m.DesignEvent.created_at)
        ).scalars()
    ]
    for expected in [
        "REQUEST_CREATED", "TEXT_CONFIRMED", "CANDIDATES_GENERATED",
        "DESIGN_SELECTED", "VERSION_CREATED", "CUSTOMER_APPROVED", "VERSION_LOCKED",
    ]:
        assert expected in types, f"missing {expected} in {types}"
    # Events are append-only: update refused by trigger.
    ev = db_session.execute(select(m.DesignEvent)).scalars().first()
    with pytest.raises(Exception):
        db_session.execute(
            text("UPDATE design_events SET event_type = 'X' WHERE id = :id"),
            {"id": str(ev.id)},
        )
        db_session.commit()
    db_session.rollback()


def test_font_references_sync(clean_tables, db_session):
    added = svc.sync_font_references(db_session)
    db_session.commit()
    assert added == 3
    assert svc.sync_font_references(db_session) == 0  # idempotent
    rows = db_session.execute(select(m.FontReference)).scalars().all()
    for r in rows:
        assert len(r.file_sha256) == 64
        assert r.rights_status == "VERIFIED_OPEN_SOURCE"
