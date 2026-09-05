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
    # Engraved-band (ring) mode — marks on solid metal, not cut-outs.
    ENGRAVING_STROKE_TOO_THIN = "ENGRAVING_STROKE_TOO_THIN"
    ENGRAVING_MARGIN_TOO_SMALL = "ENGRAVING_MARGIN_TOO_SMALL"
    ENGRAVING_TEXT_OVERFLOW = "ENGRAVING_TEXT_OVERFLOW"
    RING_SIZE_OUT_OF_RANGE = "RING_SIZE_OUT_OF_RANGE"


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
    composition: str  # bare | baseline_bar | underline_bar | plate_oval | plate_rect | frame_circle | frame_rect | top_bar
    letter_spacing_mm: float = 0.0
    x_scale: float = 1.0
    y_scale: float = 1.0
    stroke_delta_mm: float = 0.0  # buffer applied to glyph outlines
    dot_strategy: str = "bridge"  # bridge | keep (keep => must be connected by composition)
    connector_height_mm: float = 1.2
    loops: str = "top"  # none | top | left_right | upper_left_right
    frame_margin_mm: float = 2.0
    target_height_mm: float = 18.0
    # Glyph Variant Library axes (deterministic, data-driven).
    ot_feature_set: str = "default"  # OpenType stylistic set (font-dependent)
    dot_style: str = "round"  # round | diamond | square | petal
    swash: str = "none"  # none | underline_flourish | tail_sweep | double_flourish
    kashida_count: int = 0  # baseline elongation units before final letter
    # Long-text composition.
    #: Explicit variable-font coordinates, e.g. {"wght": 600}. Empty means
    #: the font's default instance — which is what every pre-axis design
    #: used, so an empty dict must never change an existing geometry hash.
    font_axes: dict[str, float] = Field(default_factory=dict)
    #: Engraved ring band spec ({"size_eu", "band_height_mm", "thickness_mm",
    #: "border"}). None = silhouette product; like an empty `font_axes`, a
    #: None ring is omitted from candidate identity so pre-ring designs keep
    #: their hashes.
    ring: Optional[dict] = None
    #: Vector Composition Engine spec for multi-name pieces
    #: ({"layout", "variant", "envelope_mm"}). None = single-text
    #: construction; like `ring`, omitted from candidate identity when None.
    multi_name: Optional[dict] = None
    max_lines: int = 1  # 1 = single line; >1 = stacked multi-line
    line_spacing_ratio: float = 0.22
    # Curated archetype metadata (Design DNA, products, text-length fit,
    # rights provenance). Informational — geometry uses the fields above.
    dna: Optional[dict] = None


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
    occupancy_hex: Optional[str] = None  # perceptual grid (comparison only)


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
    score_breakdown: Optional[dict] = None
    ranking_config_version: Optional[str] = None
    diversity_rank: Optional[int] = None
    geometry_wkt: str = ""  # canonical vector geometry (WKT MultiPolygon, mm)
    text_geometry_wkt: str = ""  # text-only geometry for proof rendering
    #: Ring inner-face engraving (second line of the source text), mirrored
    #: in the flat pattern so it reads correctly after rolling. Empty for
    #: silhouette products and single-face rings.
    inner_text_geometry_wkt: str = ""
    quality_report: Optional[dict] = None  # labelled heuristic quality layer


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
