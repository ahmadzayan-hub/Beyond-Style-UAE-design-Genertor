"""Relational source-of-truth entities (P0 persistence slice).

Immutability of historical versions and approvals is enforced BOTH here
(service layer) and at the database by triggers created in the initial
Alembic migration — see docs/adr/0001-immutable-versioning-approval.md.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
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
    # Optional customer identity (claimed after login) — secure retrieval of
    # a customer's own requests across devices. Anonymous requests keep
    # working exactly as before.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)

    candidates: Mapped[list["DesignCandidateRow"]] = relationship(back_populates="request")


class Customer(TimestampMixin, Base):
    """A customer identified by a verified contact (email or phone). Only a
    salted sha256 of the normalised contact is stored, plus a masked form
    for display — the platform never needs the raw contact after delivery."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    contact_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    contact_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    contact_masked: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerLoginCode(TimestampMixin, Base):
    __tablename__ = "customer_login_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(40), nullable=False)


class CustomerSession(TimestampMixin, Base):
    __tablename__ = "customer_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    # Engraved-band second face (ring inner engraving); None for all
    # silhouette products and single-face rings.
    inner_text_geometry_wkt: Mapped[str | None] = mapped_column(Text)
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
    inner_text_geometry_wkt: Mapped[str | None] = mapped_column(Text)
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


class ApprovalLink(TimestampMixin, Base):
    """Single-use, expiring secure approval link for ONE exact version.

    The customer opens `/approve/{token}` without a session, sees the exact
    text + dimensioned agreement proof of that version, and approves. Only
    the sha256 of the token is stored; the link is bound to the geometry
    hash it was issued for, so a later edit invalidates it."""

    __tablename__ = "approval_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    design_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customer_approvals.id"))


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


class ReferenceDNARow(TimestampMixin, Base):
    """Structured DesignDNA + embedding for a reference asset (labelled
    source: vlm or deterministic_fallback). Vector retrieval is served by
    the embeddings module (pgvector-shaped interface)."""

    __tablename__ = "reference_dna"
    __table_args__ = (UniqueConstraint("reference_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    reference_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_assets.id"), nullable=False
    )
    design_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_requests.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    analyzer_model: Mapped[str] = mapped_column(String(80), nullable=False)
    dna: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[list] = mapped_column(JSONB, nullable=False)
    encoder_version: Mapped[str] = mapped_column(String(32), nullable=False)


class GoldenProductionCase(TimestampMixin, Base):
    """A REAL manufactured, delivered and customer-approved order kept as
    the highest-weight design memory tier.

    Two hard rules are enforced by the service layer on top of this table:
    1. `customer_source_text` is NEVER inferred from photos/OCR. Until an
       order record or an explicit customer confirmation supplies it,
       `source_text_status` stays PENDING_CUSTOMER_VERIFICATION and the
       case cannot be promoted to the GOLDEN_PRODUCTION memory tier.
    2. Retrieval returns DesignDNA + construction principles only.
       `canonical_geometry_hash`/`design_version_id` are lineage columns —
       they are never emitted as generation hints, so a proven case
       informs new original geometry instead of being cloned.
    """

    __tablename__ = "golden_production_cases"
    __table_args__ = (UniqueConstraint("case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- customer text truth (never OCR/vision-derived) ---
    customer_source_text: Mapped[str | None] = mapped_column(Text)
    source_text_status: Mapped[str] = mapped_column(
        String(40), default="PENDING_CUSTOMER_VERIFICATION", nullable=False
    )
    source_text_authority: Mapped[str] = mapped_column(
        String(48), default="NOT_ESTABLISHED", nullable=False
    )
    source_text_sha256: Mapped[str | None] = mapped_column(String(64))
    primary_names: Mapped[list | None] = mapped_column(JSONB)
    language: Mapped[str] = mapped_column(String(16), default="UNKNOWN", nullable=False)

    # --- classification ---
    product_type: Mapped[str] = mapped_column(String(48), nullable=False)
    layout_style: Mapped[str | None] = mapped_column(String(48))
    composition_type: Mapped[str | None] = mapped_column(String(48))
    construction: Mapped[list] = mapped_column(JSONB, nullable=False)
    construction_topology: Mapped[str | None] = mapped_column(String(96))
    attachment_topology: Mapped[str | None] = mapped_column(String(96))
    attachment_points: Mapped[list | None] = mapped_column(JSONB)
    chain_topology: Mapped[str | None] = mapped_column(String(96))

    # --- design lineage ---
    design_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("design_versions.id"))
    canonical_geometry_hash: Mapped[str | None] = mapped_column(String(64))
    lineage_status: Mapped[str] = mapped_column(String(48), nullable=False)

    # --- manufacturing facts ---
    material: Mapped[str | None] = mapped_column(String(64))
    finish: Mapped[str | None] = mapped_column(String(64))
    dimensions: Mapped[dict | None] = mapped_column(JSONB)
    stone_or_pearl_details: Mapped[dict | None] = mapped_column(JSONB)
    workshop_changes: Mapped[list | None] = mapped_column(JSONB)
    manufacturing_result: Mapped[str] = mapped_column(String(32), nullable=False)
    production_success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # --- customer outcome (anonymized before storage) ---
    customer_feedback: Mapped[str | None] = mapped_column(Text)
    customer_sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_approved: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # --- how the design was actually arrived at ---
    #: Ordered lifecycle steps, each naming the ACTOR (customer / shop /
    #: workshop) — a proven process is reusable memory in its own right.
    design_process: Mapped[list | None] = mapped_column(JSONB)
    #: Options put in front of the customer and which one she chose.
    variant_selection: Mapped[dict | None] = mapped_column(JSONB)

    # --- learning / retrieval ---
    memory_tier: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_tier: Mapped[str] = mapped_column(String(48), nullable=False)
    ranking_weight: Mapped[str] = mapped_column(String(16), nullable=False)
    design_fidelity_score: Mapped[float | None] = mapped_column(Float)
    stage_comparison: Mapped[dict | None] = mapped_column(JSONB)
    lessons_learned: Mapped[list | None] = mapped_column(JSONB)
    design_dna: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dna_embedding: Mapped[list] = mapped_column(JSONB, nullable=False)
    encoder_version: Mapped[str] = mapped_column(String(32), nullable=False)
    retrieval_keywords: Mapped[list] = mapped_column(JSONB, nullable=False)

    # --- rights / privacy ---
    rights_provenance: Mapped[str] = mapped_column(String(48), nullable=False)
    privacy_status: Mapped[str] = mapped_column(String(32), default="PRIVATE", nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)


class DesignReview(TimestampMixin, Base):
    """One human aesthetic review of one review item. APPEND-ONLY.

    A review is evidence of what a named person judged at a moment in time,
    so a later review never overwrites an earlier one — it is a new row, and
    the current verdict is the newest row for that item. `recipe_hash` pins
    the review to the exact technical recipe that was looked at, so a review
    cannot silently transfer to a different design.

    Human scores live here and ONLY here. Deterministic engineering scores
    and any AI advisory score are stored separately and never merged in.
    """

    __tablename__ = "design_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    #: Deterministic id of the reviewed (font, features, axes, product,
    #: composition, text) combination.
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    product: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    font_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feature_set: Mapped[str] = mapped_column(String(64), nullable=False)
    font_axes: Mapped[dict | None] = mapped_column(JSONB)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    review_mode: Mapped[str] = mapped_column(String(24), nullable=False)  # quick | deep
    #: 1-5 per aesthetic dimension. Absent in quick curation.
    scores: Mapped[dict | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    #: Engineering state at review time — recorded so a later reader can see
    #: what the reviewer was actually looking at.
    engineering_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CustomerValidationResponse(TimestampMixin, Base):
    """An anonymous customer's reaction to a proof, from the validation pack.

    Stored in its own table on purpose. Customer reactions answer a
    different question from an Art Director's review — would I buy this,
    versus is this well made — and averaging the two would destroy both.
    Nothing here is ever merged into `design_reviews`.

    Anonymous by construction: there is no name, contact or device field,
    only an opaque per-session token so one person's answers can be grouped
    without identifying them.
    """

    __tablename__ = "customer_validation_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: Opaque, self-generated; never linked to a customer record.
    respondent_token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    would_buy: Mapped[str] = mapped_column(String(16), nullable=False)  # yes | maybe | no
    premium_feel: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    readability: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    uniqueness: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    preferred_product: Mapped[str | None] = mapped_column(String(48))
    price_band: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text)


class AIGeneration(TimestampMixin, Base):
    """One AI image generation (DESIGN → IMAGE). Display artifact only:
    kind is always an ai_* value and the production export path refuses
    these rows — an AI raster can never become manufacturing geometry."""

    __tablename__ = "ai_generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    design_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_requests.id"), nullable=False, index=True
    )
    design_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_versions.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), default="ai_preview", nullable=False)
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    visual_brief: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(255))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    guard_status: Mapped[str] = mapped_column(String(32), nullable=False)
    guard_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False)


class AIJob(TimestampMixin, Base):
    """Async AI job queue — model work runs in a separate worker process,
    never inside the API. Honest terminal states include MODEL_UNAVAILABLE."""

    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # analyze | preview | t2i
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_s: Mapped[float] = mapped_column(Float, default=120.0, nullable=False)


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
    #: Export Fidelity Gate result (re-import vs master) and the manifest.
    fidelity: Mapped[dict | None] = mapped_column(JSONB)
    manifest: Mapped[dict | None] = mapped_column(JSONB)


class WorkshopOrder(TimestampMixin, Base):
    """Workshop OS order: one per approved design version. State machine
    New → Design Review → Technical Check → Approved → Manufacturing → QC
    → Rework? → Ready → Delivered (workshop_service enforces it)."""

    __tablename__ = "workshop_orders"
    __table_args__ = (UniqueConstraint("design_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    design_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("design_versions.id"), nullable=False)
    approval_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_approvals.id"), nullable=False)
    approval_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(24), default="NEW", nullable=False)
    material: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list | None] = mapped_column(JSONB)
    rework_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    receiver_name: Mapped[str | None] = mapped_column(String(120))
    staff_number: Mapped[str | None] = mapped_column(String(40))
    actual_received_date: Mapped[date | None] = mapped_column(Date)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
