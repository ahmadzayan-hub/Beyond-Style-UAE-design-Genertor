"""Relational source-of-truth entities (P0 persistence slice).

Immutability of historical versions and approvals is enforced BOTH here
(service layer) and at the database by triggers created in the initial
Alembic migration — see docs/adr/0001-immutable-versioning-approval.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class DesignRequest(TimestampMixin, Base):
    __tablename__ = "design_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    source_text_raw: Mapped[str] = mapped_column(Text, nullable=False)
    source_text_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    product_type: Mapped[str] = mapped_column(String(40), default="pendant", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    ranking_config_version: Mapped[str | None] = mapped_column(String(16))
    # Anonymous session ownership: sha256 of the secret token issued at
    # creation. All request-scoped access must present the matching token.
    session_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    candidates: Mapped[list["DesignCandidateRow"]] = relationship(back_populates="request")


class DesignCandidateRow(TimestampMixin, Base):
    __tablename__ = "design_candidates"
    __table_args__ = (UniqueConstraint("request_id", "candidate_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_requests.id"), nullable=False, index=True
    )
    candidate_key: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    recipe: Mapped[dict] = mapped_column(JSONB, nullable=False)
    features: Mapped[dict | None] = mapped_column(JSONB)
    validation: Mapped[dict | None] = mapped_column(JSONB)
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    ranking_config_version: Mapped[str] = mapped_column(String(16), nullable=False)
    diversity_rank: Mapped[int | None] = mapped_column(Integer)
    geometry_wkt: Mapped[str] = mapped_column(Text, nullable=False)
    text_geometry_wkt: Mapped[str | None] = mapped_column(Text)
    quality_report: Mapped[dict | None] = mapped_column(JSONB)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    request: Mapped[DesignRequest] = relationship(back_populates="candidates")


class Design(TimestampMixin, Base):
    __tablename__ = "designs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_requests.id"), nullable=False)
    selected_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_candidates.id"), nullable=False
    )
    current_version_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DesignVersion(TimestampMixin, Base):
    __tablename__ = "design_versions"
    __table_args__ = (UniqueConstraint("design_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    design_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("designs.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_versions.id"))
    status: Mapped[str] = mapped_column(String(24), default="UNAPPROVED", nullable=False)

    immutable_source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry_wkt: Mapped[str] = mapped_column(Text, nullable=False)
    text_geometry_wkt: Mapped[str | None] = mapped_column(Text)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    arabic_engine_version: Mapped[str] = mapped_column(String(16), nullable=False)
    font_id: Mapped[str] = mapped_column(String(64), nullable=False)
    font_version: Mapped[str] = mapped_column(String(64), nullable=False)  # file sha256
    recipe_id: Mapped[str] = mapped_column(String(64), nullable=False)
    recipe_version: Mapped[str] = mapped_column(String(16), nullable=False)
    recipe: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manufacturing_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    manufacturing_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    edit_metadata: Mapped[dict | None] = mapped_column(JSONB)


class CustomerApproval(TimestampMixin, Base):
    __tablename__ = "customer_approvals"
    __table_args__ = (UniqueConstraint("design_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    design_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_versions.id"), nullable=False
    )
    confirmed_text: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(120), nullable=False)
    approval_method: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)


class DesignEvent(TimestampMixin, Base):
    """Append-only audit log. Never updated, never the primary model."""

    __tablename__ = "design_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("design_requests.id"), index=True
    )
    design_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("designs.id"), index=True)
    version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_versions.id"))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), default="system", nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB)


class ReferenceAsset(TimestampMixin, Base):
    """Customer-uploaded reference image/screenshot. PRIVATE by default:
    content is served only to the owning session, never via public URL."""

    __tablename__ = "reference_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    design_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_requests.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), default="reference_image", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)  # verified, not client-claimed
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    ip_risk: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    privacy_status: Mapped[str] = mapped_column(String(24), default="PRIVATE", nullable=False)
    scan_status: Mapped[str] = mapped_column(String(24), default="PENDING_SCAN", nullable=False)
    analysis: Mapped[dict | None] = mapped_column(JSONB)  # safe design metadata only, never text truth
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CustomerBrief(TimestampMixin, Base):
    """Structured intake brief. OCR/vision never writes confirmed_text —
    only explicit customer confirmation does."""

    __tablename__ = "customer_briefs"
    __table_args__ = (UniqueConstraint("design_request_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    design_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_requests.id"), nullable=False
    )
    request_type: Mapped[str] = mapped_column(String(40), default="NEEDS_CLARIFICATION", nullable=False)
    customer_message: Mapped[str | None] = mapped_column(Text)
    confirmed_text: Mapped[str | None] = mapped_column(Text)  # set only via explicit confirmation
    language: Mapped[str | None] = mapped_column(String(8))
    product_type: Mapped[str | None] = mapped_column(String(40))
    material_preference: Mapped[str | None] = mapped_column(String(40))
    style_intent: Mapped[str | None] = mapped_column(String(40))
    reference_ids: Mapped[list | None] = mapped_column(JSONB)
    generation_hints: Mapped[dict | None] = mapped_column(JSONB)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deadline: Mapped[str | None] = mapped_column(String(40))
    delivery_emirate: Mapped[str | None] = mapped_column(String(40))
    missing_fields: Mapped[list | None] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)


class FontReference(TimestampMixin, Base):
    __tablename__ = "font_references"
    __table_args__ = (UniqueConstraint("font_id", "file_sha256"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    font_id: Mapped[str] = mapped_column(String(64), nullable=False)
    family: Mapped[str] = mapped_column(String(120), nullable=False)
    license: Mapped[str] = mapped_column(String(120), nullable=False)
    rights_status: Mapped[str] = mapped_column(String(32), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(16), nullable=False)


class ManufacturingValidationRun(TimestampMixin, Base):
    __tablename__ = "manufacturing_validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_versions.id"))
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_candidates.id"))
    rules_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    violations: Mapped[list | None] = mapped_column(JSONB)


class ExportRecord(TimestampMixin, Base):
    __tablename__ = "exports"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_versions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # production | preview
    format: Mapped[str] = mapped_column(String(8), nullable=False)  # svg | dxf
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width_mm: Mapped[float] = mapped_column(Float, nullable=False)
    height_mm: Mapped[float] = mapped_column(Float, nullable=False)
    units: Mapped[str] = mapped_column(String(8), default="mm", nullable=False)
    validation_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
