"""Workshop manufacturing rules.

These are configurable per workshop. The values below are TEST/DEFAULT
development values ONLY — they are NOT real Beyond Style workshop
specifications and must be replaced by a verified workshop profile
before any commercial production use.
"""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"
GENERATOR_VERSION = "0.1.0"
ARABIC_ENGINE_VERSION = "0.1.0"
RANKING_CONFIG_VERSION = "0.1.0"

# PostgreSQL source of truth. No secrets committed — see backend/.env.example.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/beyondstyle",
)


class WorkshopRules(BaseModel):
    """All values in millimetres. Source: TEST_DEFAULTS (not production)."""

    profile_name: str = "TEST_DEFAULTS"
    is_production_profile: bool = False
    min_stroke_mm: float = Field(0.6, gt=0)
    min_gap_mm: float = Field(0.5, gt=0)
    min_bridge_mm: float = Field(0.8, gt=0)
    loop_inner_diameter_mm: float = Field(2.5, gt=0)
    loop_wall_mm: float = Field(0.9, gt=0)
    kerf_mm: float = Field(0.1, ge=0)
    material_thickness_mm: float = Field(1.2, gt=0)
    max_width_mm: float = Field(60.0, gt=0)
    max_height_mm: float = Field(60.0, gt=0)

    @property
    def effective_min_stroke_mm(self) -> float:
        # Kerf removes material from each side of a cut path.
        return self.min_stroke_mm + self.kerf_mm

    @property
    def effective_min_gap_mm(self) -> float:
        return max(self.min_gap_mm - self.kerf_mm, 0.1)

    @property
    def rules_version(self) -> str:
        """Profile name + content hash — provenance stamp for versions."""
        import hashlib

        digest = hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]
        return f"{self.profile_name}@{digest}"


DEFAULT_RULES = WorkshopRules()
