"""Versioned canonical JewelleryDesignSchema (P0 backend slice).

Core invariant: `ImmutableSourceText` is stored and hashed separately from
all visual geometry. Every candidate carries a glyph identity map that
traces each rendered glyph back to codepoint indices of the immutable
source text. Geometry may be transformed; the source text may not.
"""
from __future__ import annotations

import hashlib
import unicodedata
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from ..config import SCHEMA_VERSION, WorkshopRules


class FontRightsStatus(str, Enum):
    VERIFIED_OPEN_SOURCE = "VERIFIED_OPEN_SOURCE"
    COMMERCIAL_LICENSED = "COMMERCIAL_LICENSED"
    CUSTOMER_OWNED = "CUSTOMER_OWNED"
    INTERNAL_ONLY = "INTERNAL_ONLY"
    UNKNOWN_RIGHTS = "UNKNOWN_RIGHTS"


#: Rights statuses allowed to reach commercial production export.
COMMERCIAL_OK = {
    FontRightsStatus.VERIFIED_OPEN_SOURCE,
    FontRightsStatus.COMMERCIAL_LICENSED,
    FontRightsStatus.CUSTOMER_OWNED,
}


class ImmutableSourceText(BaseModel):
    """The customer-confirmed text. Never modified after confirmation."""

    raw_text: str
    normalized_text: str
    normalization_form: str = "NFC"
    sha256: str
    confirmed: bool = False

    model_config = {"frozen": True}

    @classmethod
    def create(cls, raw_text: str, confirmed: bool = False) -> "ImmutableSourceText":
        normalized = unicodedata.normalize("NFC", raw_text)
        return cls(
            raw_text=raw_text,
            normalized_text=normalized,
            sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            confirmed=confirmed,
        )


class GlyphIdentity(BaseModel):
    """Maps one positioned glyph back to the immutable source text."""

    glyph_id: int
    glyph_name: str
    cluster_start: int  # codepoint index into normalized_text
    cluster_end: int  # exclusive
    source_codepoints: list[str]  # the exact characters this glyph renders
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0
    x_advance_mm: float = 0.0


class ShapedRun(BaseModel):
    """Result of deterministic shaping of one directional run."""

    text_slice: str
    direction: str  # "rtl" | "ltr"
    script: str
    font_id: str
    glyphs: list[GlyphIdentity]


class TextIdentityProof(BaseModel):
    """Evidence that shaped glyphs cover the source text exactly."""

    verified: bool
    covered_codepoint_indices: list[int]
    uncovered_codepoint_indices: list[int]
    notdef_glyph_count: int
    detail: str = ""


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"  # blocks production
    WARNING = "WARNING"


class ViolationCode(str, Enum):
    DISCONNECTED_COMPONENT = "DISCONNECTED_COMPONENT"
    FLOATING_ISLAND = "FLOATING_ISLAND"
    THIN_STROKE = "THIN_STROKE"
    GAP_TOO_SMALL = "GAP_TOO_SMALL"
    WEAK_BRIDGE = "WEAK_BRIDGE"
    OPEN_PATH = "OPEN_PATH"
    UNSAFE_LOOP = "UNSAFE_LOOP"
    OVERSIZE = "OVERSIZE"
    EMPTY_GEOMETRY = "EMPTY_GEOMETRY"
    TEXT_IDENTITY_UNVERIFIED = "TEXT_IDENTITY_UNVERIFIED"
    FONT_RIGHTS_BLOCK = "FONT_RIGHTS_BLOCK"


class ProposedFix(BaseModel):
    """Deterministic fix proposal. NOT applied automatically."""

    action: str  # e.g. "add_bridge", "thicken", "widen_gap"
    detail: str
    params: dict = Field(default_factory=dict)


class Violation(BaseModel):
    code: ViolationCode
    severity: ValidationSeverity
    detail: str
    location_mm: Optional[tuple[float, float]] = None
    proposed_fix: Optional[ProposedFix] = None


class ValidationReport(BaseModel):
    passed: bool
    production_export_allowed: bool
    violations: list[Violation] = Field(default_factory=list)
    rules_profile: str
    checked_component_count: int = 0
    hole_count: int = 0


class RecipeParams(BaseModel):
    """Structured parametric design parameters (never raster)."""

    recipe_id: str
    name: str
    font_id: str
    composition: str  # bare | baseline_bar | underline_bar | plate_oval | plate_rect | frame_circle
    letter_spacing_mm: float = 0.0
    x_scale: float = 1.0
    y_scale: float = 1.0
    stroke_delta_mm: float = 0.0  # buffer applied to glyph outlines
    dot_strategy: str = "bridge"  # bridge | keep (keep => must be connected by composition)
    connector_height_mm: float = 1.2
    loops: str = "top"  # none | top | left_right
    frame_margin_mm: float = 2.0
    target_height_mm: float = 18.0


class CandidateFeatures(BaseModel):
    """Deterministic feature vector used for diversity scoring."""

    width_mm: float
    height_mm: float
    aspect_ratio: float
    fill_ratio: float  # area / bbox area
    hole_count: int
    complexity: float  # perimeter^2 / area (normalized shape complexity)
    stroke_delta_mm: float
    composition_class: int
    font_index: int
    loops_class: int


class DesignCandidate(BaseModel):
    candidate_id: str
    design_id: str
    schema_version: str = SCHEMA_VERSION
    source_text_sha256: str  # traceability link to ImmutableSourceText
    recipe: RecipeParams
    shaped_runs: list[ShapedRun]
    identity_proof: TextIdentityProof
    validation: Optional[ValidationReport] = None
    features: Optional[CandidateFeatures] = None
    score: float = 0.0
    diversity_rank: Optional[int] = None
    geometry_wkt: str = ""  # canonical vector geometry (WKT MultiPolygon, mm)


class DesignState(str, Enum):
    DRAFT = "DRAFT"
    TEXT_CONFIRMED = "TEXT_CONFIRMED"
    CANDIDATES_GENERATED = "CANDIDATES_GENERATED"


class JewelleryDesign(BaseModel):
    """Root aggregate for the P0 slice."""

    design_id: str
    schema_version: str = SCHEMA_VERSION
    state: DesignState = DesignState.DRAFT
    source_text: ImmutableSourceText
    rules: WorkshopRules
    product_type: str = "pendant"
    candidates: list[DesignCandidate] = Field(default_factory=list)
    top_candidate_ids: list[str] = Field(default_factory=list)
